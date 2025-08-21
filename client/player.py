import asyncio
from typing import Optional, Callable

from .audio_io import FRAME_BYTES, FRAME_MS, RATE, CHANNELS
from .jitter import JitterBuffer, playback_loop


class NullPlayer:
    async def play(self, chunk: bytes):
        # 200ms/チャンク想定。実時間同期のために sleep。
        await asyncio.sleep(0.2)


class SoundDevicePlayer:
    """sounddevice による出力（任意）。

    import を遅延し、利用時のみ依存します。
    """

    def __init__(self, device: Optional[int] = None):
        import sounddevice as sd  # type: ignore

        self.sd = sd
        self.device = device
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
        # 受信は 200ms チャンク想定。stream.write は同期 I/O なのでスレッド実行。
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._stream.write, chunk)


class JitteredOutput:
    """200msチャンク受信→20msに整流して出力するラッパ。"""

    def __init__(self, writer: Callable[[bytes], None], prebuffer_ms: int = 200, max_buffer_ms: int = 600):
        self.jb = JitterBuffer(prebuffer_ms=prebuffer_ms, max_buffer_ms=max_buffer_ms)
        self._writer_sync = writer
        self._task = None

    async def __aenter__(self):
        async def write_frame(frame: bytes):
            # 同期writerをスレッドで実行
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
