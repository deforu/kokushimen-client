import asyncio
import json
from typing import Optional, Callable

import websockets
import os

from .audio_io import FRAME_BYTES, FRAME_MS, SilenceDetector, rms_int16
from .mute import MuteController


async def sender_task(
    uri: str,
    token: str,
    stream_id: str,
    frame_iter,
    use_vad: bool = True,
    mute: Optional[MuteController] = None,
):
    """
    (★ この関数はオリジナルのまま、変更ありません)
    """
    headers = {"Authorization": f"Bearer {token}"}
    backoff = 0.5
    while True:
        try:
            async with websockets.connect(uri, additional_headers=headers, ping_interval=30) as ws:
                if use_vad:
                    try:
                        thr = float(os.getenv("VAD_THRESHOLD", "0.02"))
                    except ValueError:
                        thr = 0.02
                    try:
                        min_ms = int(os.getenv("VAD_MIN_SIL_MS", "400"))
                    except ValueError:
                        min_ms = 400
                    vad = SilenceDetector(threshold=thr, min_silence_ms=min_ms)
                else:
                    vad = None
                
                debug = os.getenv("VAD_DEBUG") == "1"
                frame_count = 0
                debug_every = int(os.getenv("VAD_DEBUG_EVERY", "20"))

                speaking = False

                async for frame in frame_iter():
                    if not isinstance(frame, (bytes, bytearray)):
                        continue
                    
                    if mute and mute.is_muted():
                        speaking = False
                        if vad: vad.reset()
                        continue

                    is_loud_enough = rms_int16(frame) >= vad.threshold if vad else True

                    if not speaking:
                        if is_loud_enough:
                            speaking = True
                            if debug: print(f"[VAD] Speech started on {stream_id}.")
                            await ws.send(frame)
                        else:
                            if debug and frame_count % max(1, debug_every) == 0:
                                print(f"[VAD] Silent... rms={rms_int16(frame):.4f} thr={vad.threshold}")
                            continue
                    else:
                        await ws.send(frame)
                        if not is_loud_enough:
                            if vad and vad.update(frame):
                                if debug: print(f"[VAD] Speech ended on {stream_id}. Sending stop.")
                                await ws.send(json.dumps({"type": "stop"}))
                                speaking = False
                                vad.reset()
                        else:
                            if vad: vad.reset()

                    frame_count += 1

                if speaking:
                    await ws.send(json.dumps({"type": "stop"}))
                backoff = 0.5
        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(10.0, backoff * 1.7)


async def playback_task(
    uri: str, 
    token: str, 
    on_pcm_chunk: Callable[[bytes], asyncio.Future], 
    mute: Optional[MuteController] = None
):
    """
    (★ この関数は修正済みです)
    """
    headers = {"Authorization": f"Bearer {token}"}
    backoff = 0.5
    while True:
        try:
            async with websockets.connect(uri, additional_headers=headers, ping_interval=30, max_size=None) as ws:
                # サーバ仕様に合わせて hello を送る（role=playback）
                try:
                    await ws.send(json.dumps({"type": "hello", "role": "playback"}))
                except Exception:
                    pass
                
                in_tts = False
                while True:
                    msg = await ws.recv()
                    
                    if isinstance(msg, (bytes, bytearray)):
                        # --- 音声データ受信時の処理 (変更なし) ---
                        if mute and not in_tts:
                            mute.set_muted(True)
                            in_tts = True
                        await on_pcm_chunk(bytes(msg))
                    
                    else:
                        # --- JSON テキスト受信時の処理 (★ここを修正) ---
                        try:
                            data = json.loads(msg)
                        except Exception:
                            data = {}
                        
                        msg_type = data.get("type")

                        if msg_type == "ai_text":
                            # ★目標達成: Geminiからのテキストをターミナルに表示
                            ai_text = data.get("text", "(テキストなし)")
                            print(f"\n💬 [Gemini 応答]: {ai_text}\n")
                        
                        elif msg_type == "emotion":
                            # ★NEW: 感情分析結果を表示
                            emotion = data.get("emotion", "不明")
                            emotion_emoji = {
                                "喜び": "😊",
                                "怒り": "😠",
                                "悲しみ": "😢",
                                "平常": "😐"
                            }
                            emoji = emotion_emoji.get(emotion, "❓")
                            print(f"{emoji} [感情分析]: {emotion}")
                        
                        elif msg_type == "tts_done":
                            # tts_done（合成音声の終了通知）でミュート解除
                            if mute:
                                mute.set_muted(False)
                            in_tts = False
                            print("ℹ️  [client] 音声再生完了、ミュート解除。")
                        
                        else:
                            # 不明なJSONメッセージ
                            print(f"ℹ️  [client] サーバーから不明なJSONを受信: {msg}")

                backoff = 0.5
        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(10.0, backoff * 1.7)