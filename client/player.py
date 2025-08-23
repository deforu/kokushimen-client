import asyncio
from typing import Optional, Callable

from .audio_io import FRAME_BYTES, FRAME_MS, RATE, CHANNELS
from .jitter import JitterBuffer, playback_loop


class NullPlayer:
    async def play(self, chunk: bytes):
        # 200ms/チャンク想定。実時間と同じ速度で進めるために sleep（待ち時間）する。
        await asyncio.sleep(0.2)


class SoundDevicePlayer:
    """sounddevice による出力（任意）。

    import（読み込み）を遅延し、実際に使うときだけライブラリに依存する作り。
    こうすることで、不要な環境では追加インストールが要らず、起動も軽くできる。

    出力デバイス指定:
    - 環境変数 `SD_OUTPUT_DEVICE` で指定可能（数値インデックス or 名称の部分一致）。
    - `SD_LIST_DEVICES=1` で入出力デバイス一覧を表示。
    """

    def __init__(self, device: Optional[int | str] = None):
        import os
        import sounddevice as sd  # type: ignore

        self.sd = sd
        env_device = os.getenv("SD_OUTPUT_DEVICE")
        self.device: Optional[int | str] = device if device is not None else env_device

        # 文字列指定なら出力デバイスのインデックスに解決
        if isinstance(self.device, str):
            name_key = self.device
            name_sub = name_key.casefold()
            try:
                self.device = int(self.device)
            except ValueError:
                try:
                    devices = self.sd.query_devices()
                except Exception:
                    devices = []
                match_idx = None
                # 厳密一致優先
                for idx, info in enumerate(devices):
                    try:
                        if info.get("max_output_channels", 0) > 0:
                            name = str(info.get("name", ""))
                            if name == name_key:
                                match_idx = idx
                                break
                    except Exception:
                        continue
                # 見つからなければ部分一致
                if match_idx is None:
                    for idx, info in enumerate(devices):
                        try:
                            if info.get("max_output_channels", 0) > 0:
                                name = str(info.get("name", ""))
                                if name_sub in name.casefold():
                                    match_idx = idx
                                    break
                        except Exception:
                            continue
                self.device = match_idx

        if os.getenv("SD_LIST_DEVICES") == "1":
            try:
                print("[sounddevice] devices:")
                for idx, info in enumerate(self.sd.query_devices()):
                    print(f"  [{idx}] in={info.get('max_input_channels',0)} out={info.get('max_output_channels',0)} name={info.get('name')}")
                print(f"[sounddevice] selected output device: {self.device}")
            except Exception:
                pass

        # 出力デバイスが明示指定されているのに解決不可の場合はフォールバックせずエラー
        if (device is not None or env_device is not None) and self.device is None:
            raise RuntimeError(
                "SD_OUTPUT_DEVICE の指定に一致する出力デバイスが見つかりません（既定デバイスへはフォールバックしません）。"
            )

        self._stream = None

    async def __aenter__(self):
        self._stream = self.sd.RawOutputStream(
            samplerate=RATE,
            dtype="int16",
            channels=CHANNELS,
            blocksize=int(RATE * (FRAME_MS / 1000.0)),
            device=self.device,
        )
        self._stream.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    async def play(self, chunk: bytes):
        # 受信は 200ms チャンク想定。stream.write は同期 I/O（終わるまで待つ処理）なのでスレッドで実行。
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._stream.write, chunk)


class JitteredOutput:
    """200msチャンク受信→20msに整流して出力するラッパ。

    整流: バラバラの到着タイミングを一定の間隔（20ms）に揃えること。
    ラッパ: ある機能を包んで扱いやすくする小さな部品。
    """

    def __init__(self, writer: Callable[[bytes], None], prebuffer_ms: int = 200, max_buffer_ms: int = 600):
        self.jb = JitterBuffer(prebuffer_ms=prebuffer_ms, max_buffer_ms=max_buffer_ms)
        self._writer_sync = writer
        self._task = None

    async def __aenter__(self):
        async def write_frame(frame: bytes):
            # 同期writer（書き込み処理が終わるまで待つ関数）をスレッドで実行
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._writer_sync, frame)

        self._task = asyncio.create_task(playback_loop(self.jb, write_frame))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
            self._task = None

    async def on_chunk(self, chunk: bytes):
        await self.jb.push_chunk(chunk)
