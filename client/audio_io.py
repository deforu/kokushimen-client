import asyncio
import math
from typing import AsyncIterator, Optional


RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes (int16)
FRAME_MS = 20
FRAME_BYTES = int(RATE * (FRAME_MS / 1000.0)) * SAMPLE_WIDTH * CHANNELS  # 640


class ToneGeneratorSource:
    """テスト用の擬似入力。1秒のビープ音→400msの無音を出力。

    実マイクがなくても疎通確認できる。
    """

    def __init__(self, freq: float = 440.0, duration_beep_s: float = 1.0, duration_silence_s: float = 0.4):
        self.freq = freq
        self.duration_beep_s = duration_beep_s
        self.duration_silence_s = duration_silence_s

    async def frames(self) -> AsyncIterator[bytes]:
        # ビープ音
        total_beep = int(self.duration_beep_s * RATE)
        pos = 0
        while pos < total_beep:
            samples = []
            n_samples = FRAME_BYTES // SAMPLE_WIDTH
            for i in range(n_samples):
                n = pos + i
                v = 0.6 * math.sin(2 * math.pi * self.freq * (n / RATE))
                s = int(max(-1.0, min(1.0, v)) * 32767)
                samples.append(int.to_bytes(s & 0xFFFF, 2, byteorder="little", signed=False))
            pos += n_samples
            yield b"".join(samples)
            await asyncio.sleep(FRAME_MS / 1000.0)
        # 無音
        total_sil = int(self.duration_silence_s * RATE)
        sil_bytes = b"\x00" * FRAME_BYTES
        emitted = 0
        while emitted < total_sil:
            yield sil_bytes
            emitted += FRAME_BYTES // SAMPLE_WIDTH
            await asyncio.sleep(FRAME_MS / 1000.0)


class SoundDeviceSource:
    """sounddevice を使った実マイク入力（任意）。

    注意: sounddevice は NumPy 依存があるため、Pi Zero 2 W では
    代替として pyalsaaudio の採用も検討可能。ここでは import を遅延し、
    インスタンス化した場合のみ依存します。
    """

    def __init__(self, device: Optional[int] = None):
        import sounddevice as sd  # type: ignore

        self.sd = sd
        self.device = device
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=50)
        self._stream = None

    async def __aenter__(self):
        def callback(indata, frames, time, status):  # indata: NumPy 配列
            try:
                # そのまま bytes へ（演算なし）
                self._queue.put_nowait(indata.tobytes())
            except Exception:
                # キュー満杯時はドロップ
                pass

        self._stream = self.sd.RawInputStream(
            samplerate=RATE,
            dtype="int16",
            channels=CHANNELS,
            blocksize=int(RATE * (FRAME_MS / 1000.0)),
            device=self.device,
            callback=callback,
        )
        self._stream.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    async def frames(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._queue.get()
            yield chunk


def rms_int16(frame: bytes) -> float:
    """NumPy を使わずに RMS を計算（int16 PCM）。"""
    # frame は 16bit little-endian
    if not frame:
        return 0.0
    # 2バイトずつ符号付き整数に解釈
    total = 0
    count = len(frame) // 2
    for i in range(0, len(frame), 2):
        s = int.from_bytes(frame[i : i + 2], byteorder="little", signed=True)
        total += s * s
    mean_square = total / max(1, count)
    return math.sqrt(mean_square) / 32768.0


class SilenceDetector:
    """RMS ベース無音検出（閾値・連続時間で判定）。"""

    def __init__(self, threshold: float = 0.01, min_silence_ms: int = 400):
        self.threshold = threshold
        self.min_silence_ms = min_silence_ms
        self._sil_ms = 0

    def update(self, frame: bytes) -> bool:
        r = rms_int16(frame)
        if r < self.threshold:
            self._sil_ms += FRAME_MS
        else:
            self._sil_ms = 0
        return self._sil_ms >= self.min_silence_ms

    def reset(self):
        self._sil_ms = 0


class AlsaaudioSource:
    """pyalsaaudio(alsaaudio) を用いた軽量入力。

    注意: Linux/ALSA 環境のみ。import は遅延し、利用時のみ依存。
    20ms 固定フレームで RAW bytes を返す。
    """

    def __init__(self, device: Optional[str] = None):
        self.device = device
        self._pcm = None

    async def __aenter__(self):
        import alsaaudio  # type: ignore

        pcm = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, device=self.device)
        pcm.setchannels(CHANNELS)
        pcm.setrate(RATE)
        pcm.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        pcm.setperiodsize(int(RATE * (FRAME_MS / 1000.0)))
        self._pcm = pcm
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._pcm is not None:
            try:
                self._pcm.close()
            except Exception:
                pass
            self._pcm = None

    async def frames(self) -> AsyncIterator[bytes]:
        import alsaaudio  # type: ignore

        assert self._pcm is not None
        pcm = self._pcm
        while True:
            # read() は (length, data) を返す
            length, data = pcm.read()
            if length <= 0:
                await asyncio.sleep(FRAME_MS / 1000.0)
                continue
            yield data
