import asyncio
import os
from typing import Callable

from .audio_io import ToneGeneratorSource, AlsaaudioSource, SoundDeviceSource
from .player import NullPlayer, SoundDevicePlayer, JitteredOutput
from . import ws_client
from .mute import MuteController


# サーバーPCのIPアドレスやポートを指定。環境変数があればそれを優先。
SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1")
SERVER_PORT = os.getenv("SERVER_PORT", "8000")
SERVER_BASE_URL = f"ws://{SERVER_IP}:{SERVER_PORT}/ws"
AUTH_TOKEN = os.getenv("SERVER_AUTH_TOKEN", "dev-token")


async def main():
    # 接続先の確認ログ（トラブルシューティング用）
    print(f"[client] Connecting to server at {SERVER_BASE_URL}/{{mic_id}}")

    # ------------------------------------------------------------------
    # 入力ソースの準備 (マイク入力 or テスト用トーンジェネレータ)
    # ------------------------------------------------------------------
    # 入力方式は環境変数 INPUT_BACKEND で選択: "tone"|"sounddevice"|"alsa"
    input_backend = os.getenv("INPUT_BACKEND", "tone")
    sd_other = None  # sounddeviceの場合の2つ目のマイク

    if input_backend == "sounddevice":
        dev_self = os.getenv("SD_INPUT_DEVICE_SELF") or os.getenv("SD_INPUT_DEVICE")
        dev_other = os.getenv("SD_INPUT_DEVICE_OTHER")
        sd_self = SoundDeviceSource(device=dev_self)
        if dev_other:
            sd_other = SoundDeviceSource(device=dev_other)

        async def frames_self():
            async with sd_self as s:
                async for f in s.frames(): yield f
        async def frames_other():
            if sd_other: 
                async with sd_other as s:
                    async for f in s.frames(): yield f
            else: # 無限に待機するジェネレータ
                while True: await asyncio.sleep(3600)

    elif input_backend == "alsa":
        # (ALSAのロジックは変更なし)
        alsa_self = AlsaaudioSource()
        alsa_other = AlsaaudioSource()
        async def frames_self():
            async with alsa_self as s:
                async for f in s.frames(): yield f
        async def frames_other():
            async with alsa_other as s:
                async for f in s.frames(): yield f
    else: # "tone"
        gen_self = ToneGeneratorSource(freq=440.0)
        gen_other = ToneGeneratorSource(freq=660.0)
        async def frames_self():
            async for f in gen_self.frames(): yield f
        async def frames_other():
            async for f in gen_other.frames(): yield f

    # ------------------------------------------------------------------
    # 出力先の準備 (スピーカー or NullPlayer)
    # ------------------------------------------------------------------
    use_sounddevice = os.getenv("USE_SD", "0") == "1"
    mute = MuteController()
    
    # 実行するタスクのリスト
    tasks = []
    # 接続先URLを動的に生成
    ws_uri_self = f"{SERVER_BASE_URL}/self"
    ws_uri_other = f"{SERVER_BASE_URL}/other"

    # メインの処理（再生デバイスの有無で分岐）
    if use_sounddevice:
        out_dev = os.getenv("SD_OUTPUT_DEVICE") or os.getenv("SD_INPUT_DEVICE_SELF")
        async with SoundDevicePlayer(device=out_dev) as player:
            jot = JitteredOutput(player._stream.write)
            async with jot:
                async def on_pcm_chunk(chunk: bytes):
                    await jot.on_chunk(chunk)

                # タスクを定義
                tasks.append(ws_client.sender_task(ws_uri_self, AUTH_TOKEN, "self", frames_self, mute=mute))
                tasks.append(ws_client.playback_task(ws_uri_self, AUTH_TOKEN, on_pcm_chunk, mute=mute))
                # 2つ目のマイクが有効なら送信タスクを追加
                if (input_backend == "sounddevice" and sd_other) or input_backend != "sounddevice":
                    tasks.append(ws_client.sender_task(ws_uri_other, AUTH_TOKEN, "other", frames_other, mute=mute))
                
                await asyncio.gather(*tasks)
    else:
        player = NullPlayer()
        async def on_pcm_chunk(chunk: bytes):
            await player.play(chunk)

        # タスクを定義
        tasks.append(ws_client.sender_task(ws_uri_self, AUTH_TOKEN, "self", frames_self, mute=mute))
        tasks.append(ws_client.playback_task(ws_uri_self, AUTH_TOKEN, on_pcm_chunk, mute=mute))
        # 2つ目のマイクが有効なら送信タスクを追加
        if (input_backend == "sounddevice" and sd_other) or input_backend != "sounddevice":
            tasks.append(ws_client.sender_task(ws_uri_other, AUTH_TOKEN, "other", frames_other, mute=mute))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())