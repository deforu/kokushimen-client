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

                # 発話中かどうかを管理する状態フラグ
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
                            # 無音状態から発話状態へ遷移
                            speaking = True
                            if debug: print(f"[VAD] Speech started on {stream_id}.")
                            await ws.send(frame)
                        else:
                            # 無音継続中は何もしない
                            if debug and frame_count % max(1, debug_every) == 0:
                                print(f"[VAD] Silent... rms={rms_int16(frame):.4f} thr={vad.threshold}")
                            continue
                    else:  # 発話中の処理
                        await ws.send(frame)
                        if not is_loud_enough:
                            # 発話中に無音フレームを検出
                            if vad and vad.update(frame):
                                # 無音が規定時間続いたので、発話終了と判断
                                if debug: print(f"[VAD] Speech ended on {stream_id}. Sending stop.")
                                await ws.send(json.dumps({"type": "stop"}))
                                speaking = False
                                vad.reset()
                        else:
                            # 発話が継続しているので、無音カウンターをリセット
                            if vad: vad.reset()

                    frame_count += 1

                # フレームが尽きた場合、発話中だったら最後のstopを送る
                if speaking:
                    await ws.send(json.dumps({"type": "stop"}))
                backoff = 0.5
        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(10.0, backoff * 1.7)


async def playback_task(uri: str, token: str, on_pcm_chunk: Callable[[bytes], asyncio.Future], mute: Optional[MuteController] = None):
    headers = {"Authorization": f"Bearer {token}"}
    backoff = 0.5
    while True:
        try:
            # websockets 15.x は extra_headers ではなく additional_headers を使用
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
                        # 最初のバイト受信でミュート開始（TTS=Text-To-Speech=合成音声の再生が始まったとみなす）
                        if mute and not in_tts:
                            mute.set_muted(True)
                            in_tts = True
                        await on_pcm_chunk(bytes(msg))
                    else:
                        # JSON テキスト
                        try:
                            data = json.loads(msg)
                        except Exception:
                            data = {}
                        # tts_done（合成音声の終了通知）でミュート解除
                        if data.get("type") == "tts_done":
                            if mute:
                                mute.set_muted(False)
                            in_tts = False
                backoff = 0.5
        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(10.0, backoff * 1.7)
