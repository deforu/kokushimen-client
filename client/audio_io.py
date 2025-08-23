import asyncio
import math
from typing import AsyncIterator, Optional


RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 1サンプルのバイト数（int16=16ビット整数のこと）
FRAME_MS = 20
FRAME_BYTES = int(RATE * (FRAME_MS / 1000.0)) * SAMPLE_WIDTH * CHANNELS  # 1フレーム(20ms)のバイト数。16000Hz×0.02秒×2バイト×1ch=640


class ToneGeneratorSource:
    """テスト用の擬似入力。1秒のビープ音→400msの無音を出力。

    実マイクがなくても疎通確認できる。
    ビープ音: 一定の周波数で鳴らす単純な音。
    無音: 音がまったく入っていないデータ。
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

    注意: sounddevice は NumPy（数値計算用のPythonライブラリ）への依存があるため、
    例えば Raspberry Pi Zero 2 W では導入が重い可能性があります。
    代替として pyalsaaudio（ALSA=Linuxの音声仕組みに直接アクセスするライブラリ）の
    採用も検討可能。ここでは import を遅延し、実際にこのクラスを使ったときだけ
    依存するようにしています（=不要な環境ではインストール不要）。

    デバイス指定（Windowsの内蔵マイクなどを選ぶ）:
    - 環境変数 `SD_INPUT_DEVICE` を設定する。
      - 数値を指定: そのインデックスのデバイスを使用（例: `SD_INPUT_DEVICE=1`）。
      - 文字列を指定: デバイス名の部分一致で最初に見つかった入力デバイスを使用
        （例: `SD_INPUT_DEVICE=Microphone` や `SD_INPUT_DEVICE=Realtek`）。
    - 一覧表示: `SD_LIST_DEVICES=1` を設定すると、起動時にデバイス一覧を表示。
    """

    def __init__(self, device: Optional[int | str] = None):
        import os
        import sounddevice as sd  # type: ignore

        self.sd = sd
        env_device = os.getenv("SD_INPUT_DEVICE")
        self.device = device if device is not None else env_device
        # 文字列デバイス指定（名前の部分一致）をインデックスへ解決
        if isinstance(self.device, str):
            name_key = self.device
            name_sub = name_key.casefold()
            exact = os.getenv("SD_MATCH_EXACT", "1") == "1"
            try:
                # 数値として解釈できるならそのまま使う
                self.device = int(self.device)
            except ValueError:
                try:
                    devices = sd.query_devices()
                except Exception:
                    devices = []
                # まずは厳密一致、なければ部分一致でフォールバック
                match_idx = None
                for idx, info in enumerate(devices):
                    try:
                        if info.get("max_input_channels", 0) > 0:
                            name = str(info.get("name", ""))
                            if name == name_key:
                                match_idx = idx
                                break
                    except Exception:
                        continue
                if match_idx is None:
                    for idx, info in enumerate(devices):
                        try:
                            if info.get("max_input_channels", 0) > 0:
                                name = str(info.get("name", ""))
                                if name_sub in name.casefold():
                                    match_idx = idx
                                    break
                        except Exception:
                            continue
                self.device = match_idx  # 見つからなければ None のまま

        # 任意: デバイス一覧の表示
        if os.getenv("SD_LIST_DEVICES") == "1":
            try:
                print("[sounddevice] devices:")
                for idx, info in enumerate(self.sd.query_devices()):
                    print(f"  [{idx}] in={info.get('max_input_channels',0)} out={info.get('max_output_channels',0)} name={info.get('name')}")
                print(f"[sounddevice] selected input device: {self.device}")
            except Exception:
                pass

        # 指定があって解決できなかった場合は、既定デバイスへフォールバックせずエラーにする
        if (device is not None or env_device is not None) and self.device is None:
            raise RuntimeError(
                "SD_INPUT_DEVICE の指定に一致する入力デバイスが見つかりません（既定デバイスへはフォールバックしません）。"
            )

        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=50)
        self._stream = None

    async def __aenter__(self):
        def callback(indata, frames, time, status):  # RawInputStream: indata は bytes ライク
            try:
                # そのまま bytes へ（演算なし。bytes=生のバイト列データ）
                self._queue.put_nowait(bytes(indata))
            except Exception:
                # キュー（順番待ちの箱）が満杯のときは捨てる（オーバーフロー対策）
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
    """NumPy を使わずに RMS を計算（int16 PCM）。

    RMS（平均二乗平方根）: 音の大きさを表す代表的な指標。値が大きいほど音量が大きい。
    実環境のマイクでは直流成分（DCオフセット）が乗ることがあるため、
    平均値を差し引いた分散から標準偏差を求める方法に変更（DCの影響を低減）。
    """
    if not frame:
        return 0.0
    count = len(frame) // 2
    if count <= 0:
        return 0.0
    # 1パスで合計と二乗和を集計
    sum_s = 0
    sum_sq = 0
    for i in range(0, len(frame), 2):
        s = int.from_bytes(frame[i : i + 2], byteorder="little", signed=True)
        sum_s += s
        sum_sq += s * s
    mean = sum_s / count
    # 分散 = E[x^2] - (E[x])^2
    mean_square = sum_sq / count
    var = max(0.0, mean_square - mean * mean)
    return math.sqrt(var) / 32768.0


class SilenceDetector:
    """RMS ベース無音検出（閾値・連続時間で判定）。

    閾値: 「これより小さい値は無音とみなす」という線引きとなる値。
    一定時間以上（min_silence_ms）連続して小さいと「無音区間の終わり」と判断する。
    """

    def __init__(self, threshold: float = 0.01, min_silence_ms: int = 400):
        self.threshold = threshold
        self.min_silence_ms = min_silence_ms
        self._sil_ms = 0
        self._last_rms = 0.0

    def update(self, frame: bytes) -> bool:
        r = rms_int16(frame)
        self._last_rms = r
        if r < self.threshold:
            self._sil_ms += FRAME_MS
        else:
            self._sil_ms = 0
        return self._sil_ms >= self.min_silence_ms

    def reset(self):
        self._sil_ms = 0


class AlsaaudioSource:
    """pyalsaaudio(alsaaudio) を用いた軽量入力。

    注意: Linux/ALSA 環境のみ。ALSA（Advanced Linux Sound Architecture）とは
    Linux の標準的な音声入出力の仕組みのこと。import は遅延し、利用時のみ依存。
    20ms 固定フレームで RAW bytes（生のバイト列）を返す。
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
            # read() は (length, data) を返す（length=読み取れたサンプル数、data=生データ）
            length, data = pcm.read()
            if length <= 0:
                await asyncio.sleep(FRAME_MS / 1000.0)
                continue
            yield data
