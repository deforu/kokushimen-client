import asyncio
import os
from typing import Callable

from .audio_io import ToneGeneratorSource, AlsaaudioSource, SoundDeviceSource
from .player import NullPlayer, SoundDevicePlayer, JitteredOutput
from . import ws_client
from .mute import MuteController


# 接続先URLはマイクIDを含む形にする（サーバ仕様に合わせる）
# サーバーPCのIPアドレスを指定（例: 192.168.1.10）。環境変数 SERVER_IP があればそれを優先。
# 同一PCでサーバーを起動している場合は 127.0.0.1 を使用します。
SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1")
SERVER_WS_SELF = os.getenv("SERVER_WS_SELF", f"ws://{SERVER_IP}:8000/ws/self")
SERVER_WS_OTHER = os.getenv("SERVER_WS_OTHER", f"ws://{SERVER_IP}:8000/ws/other")
# 再生用はどちらかのIDに紐づける（ここでは self）
SERVER_WS_PLAYBACK = os.getenv("SERVER_WS_PLAYBACK", SERVER_WS_SELF)
AUTH_TOKEN = os.getenv("SERVER_AUTH_TOKEN", "dev-token")


async def main():
    # 接続先の確認ログ（トラブルシューティング用）
    print(f"[client] SERVER_IP={SERVER_IP}")
    print(f"[client] WS_SELF={SERVER_WS_SELF}")
    print(f"[client] WS_OTHER={SERVER_WS_OTHER}")
    print(f"[client] WS_PLAYBACK={SERVER_WS_PLAYBACK}")
    # テスト用: トーンジェネレータ（一定の周波数で鳴る音）を 2 系統に流す
    # 入力方式は環境変数 INPUT_BACKEND で選択: "tone"|"sounddevice"|"alsa"
    # - tone: 実マイクなし。プログラム内で作った音を使う（疎通確認に最適）
    # - sounddevice: PCのマイク入力（sounddevice ライブラリが必要）
    # - alsa: LinuxのALSA経由の入力（軽量）
    input_backend = os.getenv("INPUT_BACKEND", "tone")  # 既定は tone
    if input_backend == "sounddevice":
        # デバイス指定（self/other 別々に）。other 未指定時は起動しない（既定デバイスへはフォールバックしない）。
        dev_self = os.getenv("SD_INPUT_DEVICE_SELF") or os.getenv("SD_INPUT_DEVICE")
        dev_other = os.getenv("SD_INPUT_DEVICE_OTHER")
        sd_self = SoundDeviceSource(device=dev_self)
        sd_other = None
        if dev_other:
            sd_other = SoundDeviceSource(device=dev_other)
        async def frames_self():
            async with sd_self as s:
                async for f in s.frames():
                    yield f
        async def frames_other():
            if sd_other is None:
                return
            async with sd_other as s:
                async for f in s.frames():
                    yield f
    elif input_backend == "alsa":
        alsa_self = AlsaaudioSource()
        alsa_other = AlsaaudioSource()
        async def frames_self():
            async with alsa_self as s:
                async for f in s.frames():
                    yield f
        async def frames_other():
            async with alsa_other as s:
                async for f in s.frames():
                    yield f
    else:
        gen_self = ToneGeneratorSource(freq=440.0)
        gen_other = ToneGeneratorSource(freq=660.0)
        async def frames_self():
            async for f in gen_self.frames():
                yield f
        async def frames_other():
            async for f in gen_other.frames():
                yield f

    # プレイヤ（再生側）。sounddevice が使えない環境では NullPlayer（待つだけ）を使用。
    use_sounddevice = os.getenv("USE_SD", "0") == "1"
    mute = MuteController()
    if use_sounddevice:
        # 出力デバイス指定（未指定なら None → 既定デバイス）
        out_dev = os.getenv("SD_OUTPUT_DEVICE") or os.getenv("SD_INPUT_DEVICE_SELF")
        async with SoundDevicePlayer(device=out_dev) as player:
            # jitter（到着のバラツキ）を緩和するため、20ms単位に整える
            jot = JitteredOutput(player._stream.write)
            async with jot:
                async def on_pcm_chunk(chunk: bytes):
                    await jot.on_chunk(chunk)

                tasks = [
                    ws_client.sender_task(SERVER_WS_SELF, AUTH_TOKEN, "self", frames_self, mute=mute),
                    ws_client.playback_task(SERVER_WS_PLAYBACK, AUTH_TOKEN, on_pcm_chunk, mute=mute),
                ]
                if sd_other is not None:
                    tasks.insert(1, ws_client.sender_task(SERVER_WS_OTHER, AUTH_TOKEN, "other", frames_other, mute=mute))
                await asyncio.gather(*tasks)
    else:
        player = NullPlayer()
        # jitter対策はなし。受け取った間隔のまま sleep するだけ（動作確認用）
        async def on_pcm_chunk(chunk: bytes):
            await player.play(chunk)

        tasks = [
            ws_client.sender_task(SERVER_WS_SELF, AUTH_TOKEN, "self", frames_self, mute=mute),
            ws_client.playback_task(SERVER_WS_PLAYBACK, AUTH_TOKEN, on_pcm_chunk, mute=mute),
        ]
        if input_backend == "sounddevice" and 'sd_other' in locals() and sd_other is not None:
            tasks.insert(1, ws_client.sender_task(SERVER_WS_OTHER, AUTH_TOKEN, "other", frames_other, mute=mute))
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
