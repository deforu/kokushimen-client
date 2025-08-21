import asyncio
import json
import math
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse


app = FastAPI()


PLAYBACK_CLIENTS: Set[WebSocket] = set()


def _pcm_s16le_sine(duration_sec: float = 1.0, rate: int = 16000, freq: float = 440.0) -> bytes:
    total = int(duration_sec * rate)
    # 200ms チャンク（= 3200 サンプル = 6400 bytes）で返す呼び元の都合に合わせ
    # ここでは一括生成しておき、送信側で分割する。
    frames = bytearray()
    for n in range(total):
        # -0.8..0.8 の範囲でサイン波
        v = 0.8 * math.sin(2 * math.pi * freq * (n / rate))
        # int16 に量子化
        s = int(max(-1.0, min(1.0, v)) * 32767)
        frames.extend(int.to_bytes(s & 0xFFFF, 2, byteorder="little", signed=False))
    return bytes(frames)


async def _broadcast_tts_mock():
    if not PLAYBACK_CLIENTS:
        return
    pcm = _pcm_s16le_sine(1.0)
    frame_bytes = 6400  # 200ms
    # 事前に final_asr を送出（テキストはダミー）
    asr_msg = json.dumps({"type": "final_asr", "text": "(mock) 了解しました。", "utter_id": "mock-utt"})
    for ws in list(PLAYBACK_CLIENTS):
        try:
            await ws.send_text(asr_msg)
        except Exception:
            pass
    # 200ms ごとに分割送信
    for i in range(0, len(pcm), frame_bytes):
        chunk = pcm[i : i + frame_bytes]
        send_tasks = []
        for ws in list(PLAYBACK_CLIENTS):
            send_tasks.append(ws.send_bytes(chunk))
        if send_tasks:
            try:
                await asyncio.gather(*send_tasks, return_exceptions=True)
            except Exception:
                pass
        await asyncio.sleep(0.2)
    # 終了通知
    done_msg = json.dumps({"type": "tts_done", "utter_id": "mock-utt"})
    for ws in list(PLAYBACK_CLIENTS):
        try:
            await ws.send_text(done_msg)
        except Exception:
            pass


@app.websocket("/ws")
async def ws_handler(websocket: WebSocket):
    # 簡易認証（存在チェックのみ）
    auth = websocket.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        await websocket.close(code=4401)
        return
    await websocket.accept()

    role = None
    stream_id = None
    try:
        while True:
            message = await websocket.receive()
            mtype = message.get("type")
            if mtype != "websocket.receive":
                continue
            if "text" in message:
                try:
                    data = json.loads(message["text"]) if message["text"] else {}
                except json.JSONDecodeError:
                    data = {}
                msg_type = data.get("type")
                if msg_type == "hello":
                    role = data.get("role")
                    stream_id = data.get("stream_id")
                    if role == "playback":
                        PLAYBACK_CLIENTS.add(websocket)
                    # 簡易応答
                    await websocket.send_text(json.dumps({"type": "hello", "accepted": True, "role": role}))
                elif msg_type == "stop":
                    # 区切り受信→擬似ASR/TTSをプレイバックへブロードキャスト
                    await _broadcast_tts_mock()
                else:
                    # no-op
                    pass
            elif "bytes" in message:
                # 音声バイナリ（20ms=640 bytes）を受信。モックでは使用しない。
                _ = message["bytes"]
            else:
                # その他は無視
                pass
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in PLAYBACK_CLIENTS:
            PLAYBACK_CLIENTS.discard(websocket)


@app.get("/")
async def index():
    return {"status": "ok", "ws": "/ws"}

