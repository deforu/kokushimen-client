import asyncio
import os
from typing import Callable
from pathlib import Path

from .audio_io import ToneGeneratorSource, AlsaaudioSource, SoundDeviceSource
from .player import NullPlayer, SoundDevicePlayer, JitteredOutput
from . import ws_client
from .mute import MuteController
from .emotion_led import EmotionLED


# .envファイルから環境変数を読み込む
def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

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
    # - tone: 実マイクなし。プログラム内で作った音を使う（疎通確認に最適）
    # - sounddevice: PCのマイク入力（sounddevice ライブラリが必要）
    # - alsa: LinuxのALSA経由の入力（軽量）
    input_backend = os.getenv("INPUT_BACKEND", "sounddevice")  # 既定は sounddevice
    sd_self = None
    sd_other = None

    if input_backend == "sounddevice":
        # デバイス指定（self/other 別々に）。
        dev_self = os.getenv("SD_INPUT_DEVICE_SELF") or os.getenv("SD_INPUT_DEVICE")
        dev_other = os.getenv("SD_INPUT_DEVICE_OTHER")
        try:
            sd_self = SoundDeviceSource(device=dev_self)
            if dev_other:
                sd_other = SoundDeviceSource(device=dev_other)
        except Exception as e:
            print(f"[client] sounddevice 入力を初期化できませんでした（{e}）。tone にフォールバックします。")
            input_backend = "tone" # Fallback to tone

    if input_backend == "sounddevice" and sd_self is not None:
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
    else: # "tone" or fallback
        gen_self = ToneGeneratorSource(freq=440.0)
        gen_other = ToneGeneratorSource(freq=660.0)
        async def frames_self():
            async for f in gen_self.frames(): yield f
        async def frames_other():
            async for f in gen_other.frames(): yield f

    # ------------------------------------------------------------------
    # 出力先の準備 (スピーカー or NullPlayer)
    # ------------------------------------------------------------------
    use_sounddevice = os.getenv("USE_SD", "1") == "1"  # 既定で再生有効
    mute = MuteController()
    
    # LED制御の初期化
    led = EmotionLED()
    
    # 実行するタスクのリスト
    tasks = []
    # 接続先URLを動的に生成
    ws_uri_self_sender = f"{SERVER_BASE_URL}/self?role=sender"
    ws_uri_self_playback = f"{SERVER_BASE_URL}/self?role=playback"
    ws_uri_other_sender = f"{SERVER_BASE_URL}/other?role=sender"

    # メインの処理（再生デバイスの有無で分岐）
    try:
        if use_sounddevice:
            out_dev = os.getenv("SD_OUTPUT_DEVICE") or os.getenv("SD_INPUT_DEVICE_SELF")
            try:
                async with SoundDevicePlayer(device=out_dev) as player:
                    jot = JitteredOutput(player._stream.write)
                    async with jot:
                        async def on_pcm_chunk(chunk: bytes):
                            await jot.on_chunk(chunk)

                        # タスクを定義
                        tasks.append(ws_client.sender_task(ws_uri_self_sender, AUTH_TOKEN, "self", frames_self, mute=mute))
                        tasks.append(ws_client.playback_task(ws_uri_self_playback, AUTH_TOKEN, on_pcm_chunk, mute=mute, led=led))
                        # 2つ目のマイクが有効なら送信タスクを追加
                        if (input_backend == "sounddevice" and sd_other) or input_backend != "sounddevice":
                            tasks.append(ws_client.sender_task(ws_uri_other_sender, AUTH_TOKEN, "other", frames_other, mute=mute))
                        
                        await asyncio.gather(*tasks)
            except Exception as e:
                print(f"[client] sounddevice 出力を初期化できませんでした（{e}）。NullPlayer にフォールバックします。")
                use_sounddevice = False # Set flag to false and drop into the 'else' block below.
        
        if not use_sounddevice: # This block will now be used for both default and fallback cases.
            player = NullPlayer()
            async def on_pcm_chunk(chunk: bytes):
                await player.play(chunk)

            # タスクを定義
            tasks.append(ws_client.sender_task(ws_uri_self_sender, AUTH_TOKEN, "self", frames_self, mute=mute))
            tasks.append(ws_client.playback_task(ws_uri_self_playback, AUTH_TOKEN, on_pcm_chunk, mute=mute, led=led))
            # 2つ目のマイクが有効なら送信タスクを追加
            if (input_backend == "sounddevice" and sd_other) or input_backend != "sounddevice":
                tasks.append(ws_client.sender_task(ws_uri_other_sender, AUTH_TOKEN, "other", frames_other, mute=mute))

            await asyncio.gather(*tasks)
    finally:
        # 終了時にLEDをクリーンアップ
        led.cleanup()


if __name__ == "__main__":
    asyncio.run(main())