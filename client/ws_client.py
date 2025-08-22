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

                # 音量ゲート（大きい音でゲート開→一定時間だけ送信）: VADの代替。GATE_ON=1 で有効。
                gate_on = os.getenv("GATE_ON") == "1"
                try:
                    gate_hold_ms = int(os.getenv("GATE_HOLD_MS", "2000"))  # 大きい音後に送り続ける時間
                except ValueError:
                    gate_hold_ms = 2000
                try:
                    gate_open_thr = float(os.getenv("GATE_RMS_OPEN", "0.06"))  # ゲートを開くRMS閾値
                except ValueError:
                    gate_open_thr = 0.06
                gate_send_stop_on_close = os.getenv("GATE_SEND_STOP_ON_CLOSE", "1") == "1"
                gate_remain_ms = 0  # >0 の間は送信、それ以外は送らない
                gate_was_open = False
                gate_debug = os.getenv("GATE_DEBUG") == "1"

                # ゲート使用時はサイクル送信は無効化（排他的）。
                # サイクルを併用したい場合は GATE_ON を 0 にしてください。
                # 送信/無送信を交互に行うテスト用サイクル（ms単位）。両方>0で有効。
                try:
                    cycle_active_ms = int(os.getenv("SEND_CYCLE_ACTIVE_MS", "0"))
                except ValueError:
                    cycle_active_ms = 0
                try:
                    cycle_silent_ms = int(os.getenv("SEND_CYCLE_SILENT_MS", "0"))
                except ValueError:
                    cycle_silent_ms = 0
                cycle_enabled = (cycle_active_ms > 0 and cycle_silent_ms > 0) and (not gate_on)
                cycle_in_active = True
                cycle_elapsed = 0
                cycle_send_stop = os.getenv("SEND_CYCLE_SEND_STOP", "0") == "1"  # 0=送らない（既定）

                async for frame in frame_iter():
                    if not isinstance(frame, (bytes, bytearray)):
                        continue
                    # ミュート中はキューを捨てて送信しない（入力バッファのクリア=溜まった音を破棄）
                    if mute and mute.is_muted():
                        if vad:
                            vad.reset()
                        elapsed_ms = 0
                        continue
                    # 1) 音量ゲートが有効な場合の送信制御
                    if gate_on:
                        # RMS を計算
                        r = rms_int16(frame)
                        # 閾値超えでゲート延長
                        if r >= gate_open_thr:
                            gate_remain_ms = max(gate_remain_ms, gate_hold_ms)
                            if gate_debug:
                                print(f"[GATE] open trig rms={r:.4f} thr={gate_open_thr} hold={gate_hold_ms}ms")
                        if gate_remain_ms > 0:
                            # 送信（ゲート開）
                            await ws.send(frame)
                            elapsed_ms += FRAME_MS
                            frame_count += 1
                            gate_remain_ms = max(0, gate_remain_ms - FRAME_MS)
                            gate_was_open = True
                        else:
                            # 送信しない（ゲート閉）: 必要なら stop を一度だけ送る
                            if gate_was_open:
                                if gate_debug:
                                    print("[GATE] close; send stop")
                                if gate_send_stop_on_close:
                                    await ws.send(json.dumps({"type": "stop"}))
                                gate_was_open = False
                            # VADやカウンタはリセット
                            if vad:
                                vad.reset()
                            elapsed_ms = 0
                        # ゲート使用時は以降の処理をスキップ
                        continue

                    # 2) テスト用サイクル: アクティブ期間は送信、サイレント期間は送信しない
                    if cycle_enabled:
                        if cycle_in_active:
                            await ws.send(frame)
                            elapsed_ms += FRAME_MS
                            frame_count += 1
                            cycle_elapsed += FRAME_MS
                            if cycle_elapsed >= cycle_active_ms:
                                # アクティブ→サイレントへ遷移
                                cycle_in_active = False
                                cycle_elapsed = 0
                                if cycle_send_stop:
                                    await ws.send(json.dumps({"type": "stop"}))
                                # VADや連続時間はリセット
                                if vad:
                                    vad.reset()
                                elapsed_ms = 0
                                continue
                        else:
                            # サイレント期間: 送信しない（フレームは破棄）
                            cycle_elapsed += FRAME_MS
                            if vad:
                                vad.reset()
                            elapsed_ms = 0
                            if cycle_elapsed >= cycle_silent_ms:
                                cycle_in_active = True
                                cycle_elapsed = 0
                            continue
                    else:
                        # サイクル無効時は通常どおり送信
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
