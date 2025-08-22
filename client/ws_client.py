import asyncio
import json
from typing import Optional, Callable

import websockets
import os

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
            # websockets 15.x は extra_headers ではなく additional_headers を使用
            async with websockets.connect(uri, additional_headers=headers, ping_interval=30) as ws:
                # helloメッセージは仕様にないため送らない
                # VAD感度は環境変数で調整可能: VAD_THRESHOLD(既定0.02), VAD_MIN_SIL_MS(既定400)
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
                # 連続送信を強制的に区切るための上限時間（ms）。0以下で無効。
                try:
                    force_stop_ms = int(os.getenv("VAD_FORCE_STOP_MS", "0"))
                except ValueError:
                    force_stop_ms = 0
                elapsed_ms = 0
                
                debug = os.getenv("VAD_DEBUG") == "1"
                debug_every = int(os.getenv("VAD_DEBUG_EVERY", "20"))  # 20フレーム=約0.4秒ごと
                frame_count = 0

                async for frame in frame_iter():
                    if not isinstance(frame, (bytes, bytearray)):
                        continue
                    # ミュート中はキューを捨てて送信しない（入力バッファのクリア=溜まった音を破棄）
                    if mute and mute.is_muted():
                        if vad:
                            vad.reset()
                        elapsed_ms = 0
                        continue
                    # バイナリ送信（20ms=640バイトの生データ）
                    await ws.send(frame)
                    elapsed_ms += FRAME_MS
                    frame_count += 1
                    if debug and vad and frame_count % max(1, debug_every) == 0:
                        print(f"[VAD] rms={vad._last_rms:.4f} sil_ms={vad._sil_ms} thr={vad.threshold} min={vad.min_silence_ms}")
                    # 無音>=400ms で stop 通知（サーバに「一区切り」と知らせる制御メッセージ）
                    if vad and vad.update(frame):
                        await ws.send(json.dumps({"type": "stop"}))
                        vad._sil_ms = 0
                        elapsed_ms = 0
                        continue
                    # 保険: 指定時間以上連続送信が続いたら強制的に区切る
                    if force_stop_ms > 0 and elapsed_ms >= force_stop_ms:
                        await ws.send(json.dumps({"type": "stop"}))
                        elapsed_ms = 0
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
            # websockets 15.x は extra_headers ではなく additional_headers を使用
            async with websockets.connect(uri, additional_headers=headers, ping_interval=30, max_size=None) as ws:
                # helloメッセージは仕様にないため送らない
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
