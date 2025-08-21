import asyncio
import json
from typing import Optional, Callable

import websockets

from .audio_io import FRAME_BYTES, FRAME_MS, SilenceDetector
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
            async with websockets.connect(uri, extra_headers=headers, ping_interval=30) as ws:
                hello = {
                    "type": "hello",
                    "role": "sender",
                    "stream_id": stream_id,
                    "spec": {"codec": "PCM_S16LE", "rate": 16000, "channels": 1, "frame_ms": 20},
                }
                await ws.send(json.dumps(hello))
                vad = SilenceDetector() if use_vad else None
                
                async for frame in frame_iter():
                    if not isinstance(frame, (bytes, bytearray)):
                        continue
                    # ミュート中はキューを捨てて送信しない（入力バッファのクリアに相当）
                    if mute and mute.is_muted():
                        if vad:
                            vad.reset()
                        continue
                    # バイナリ送信（20ms）
                    await ws.send(frame)
                    # 無音>=400ms で stop 通知
                    if vad and vad.update(frame):
                        await ws.send(json.dumps({"type": "stop"}))
                        vad._sil_ms = 0
                # フレームが尽きた場合も区切り
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
            async with websockets.connect(uri, extra_headers=headers, ping_interval=30, max_size=None) as ws:
                await ws.send(json.dumps({"type": "hello", "role": "playback"}))
                in_tts = False
                while True:
                    msg = await ws.recv()
                    if isinstance(msg, (bytes, bytearray)):
                        # 最初のバイト受信でミュート開始
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
                        # tts_done でミュート解除
                        if data.get("type") == "tts_done":
                            if mute:
                                mute.set_muted(False)
                            in_tts = False
                backoff = 0.5
        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(10.0, backoff * 1.7)
