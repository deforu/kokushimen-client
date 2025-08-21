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
    # テスト用: トーンジェネレータを 2 系統に流す
    input_backend = os.getenv("INPUT_BACKEND", "tone")  # tone|sounddevice|alsa
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

    # プレイヤ（sounddevice が使えない環境では NullPlayer）
    use_sounddevice = os.getenv("USE_SD", "0") == "1"
    mute = MuteController()
    if use_sounddevice:
        async with SoundDevicePlayer() as player:
            # jitter で20ms整流
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
        # jitterはそのままsleepするだけ（動作確認用）
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
