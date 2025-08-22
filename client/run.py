import asyncio
import os
from typing import Callable

from .audio_io import ToneGeneratorSource, AlsaaudioSource, SoundDeviceSource
from .player import NullPlayer, SoundDevicePlayer, JitteredOutput
from . import ws_client
from .mute import MuteController


SERVER_WS = os.getenv("SERVER_WS", "ws://127.0.0.1:8000/ws")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "dev-token")


async def main():
    # テスト用: トーンジェネレータ（一定の周波数で鳴る音）を 2 系統に流す
    # 入力方式は環境変数 INPUT_BACKEND で選択: "tone"|"sounddevice"|"alsa"
    # - tone: 実マイクなし。プログラム内で作った音を使う（疎通確認に最適）
    # - sounddevice: PCのマイク入力（sounddevice ライブラリが必要）
    # - alsa: LinuxのALSA経由の入力（軽量）
    input_backend = os.getenv("INPUT_BACKEND", "tone")  # 既定は tone
    if input_backend == "sounddevice":
        sd_self = SoundDeviceSource()
        sd_other = SoundDeviceSource()
        async def frames_self():
            async with sd_self as s:
                async for f in s.frames():
                    yield f
        async def frames_other():
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
        async with SoundDevicePlayer() as player:
            # jitter（到着のバラツキ）を緩和するため、20ms単位に整える
            jot = JitteredOutput(player._stream.write)
            async with jot:
                async def on_pcm_chunk(chunk: bytes):
                    await jot.on_chunk(chunk)

                tasks = [
                    ws_client.sender_task(SERVER_WS, AUTH_TOKEN, "self", frames_self, mute=mute),
                    ws_client.sender_task(SERVER_WS, AUTH_TOKEN, "other", frames_other, mute=mute),
                    ws_client.playback_task(SERVER_WS, AUTH_TOKEN, on_pcm_chunk, mute=mute),
                ]
                await asyncio.gather(*tasks)
    else:
        player = NullPlayer()
        # jitter対策はなし。受け取った間隔のまま sleep するだけ（動作確認用）
        async def on_pcm_chunk(chunk: bytes):
            await player.play(chunk)

        tasks = [
            ws_client.sender_task(SERVER_WS, AUTH_TOKEN, "self", frames_self, mute=mute),
            ws_client.sender_task(SERVER_WS, AUTH_TOKEN, "other", frames_other, mute=mute),
            ws_client.playback_task(SERVER_WS, AUTH_TOKEN, on_pcm_chunk, mute=mute),
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
