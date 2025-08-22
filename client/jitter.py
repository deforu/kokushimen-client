import asyncio
from collections import deque
from typing import Deque, Optional, Callable

from .audio_io import FRAME_BYTES, FRAME_MS


class JitterBuffer:
    """200ms チャンク入力 → 20ms フレームに分割して供給。

    ジッターバッファ（jitter buffer）: ネットワークで到着が前後する音声データを
    いったん溜めて順序よく一定間隔で取り出すための小さな貯蔵庫のこと。

    - prebuffer_ms: 出力を安定させるため、まずこの時間分を貯めてから再生開始。
      （バッファ=一時的な保存場所）
    - max_buffer_ms: ここを超えるほど溜まったら古いフレームから捨てる（遅延を抑えるため）。
    """

    def __init__(self, prebuffer_ms: int = 200, max_buffer_ms: int = 600):
        self.queue: Deque[bytes] = deque()
        self.prebuffer_frames = max(0, prebuffer_ms // FRAME_MS)
        self.max_frames = max(1, max_buffer_ms // FRAME_MS)
        self._lock = asyncio.Lock()

    async def push_chunk(self, chunk: bytes):
        # 200ms(6400バイト)を20ms(640バイト)へ分解（1/10に区切る計算）
        for i in range(0, len(chunk), FRAME_BYTES):
            frame = chunk[i : i + FRAME_BYTES]
            if len(frame) < FRAME_BYTES:
                break
            async with self._lock:
                self.queue.append(frame)
                # オーバーフロー（入れ物が一杯）時は古いものから捨てる
                while len(self.queue) > self.max_frames:
                    self.queue.popleft()

    async def pop_frame(self) -> Optional[bytes]:
        async with self._lock:
            if not self.queue:
                return None
            if len(self.queue) < self.prebuffer_frames:
                return None
            return self.queue.popleft()


async def playback_loop(jb: JitterBuffer, write_frame: Callable[[bytes], asyncio.Future]):
    """20msごとにフレームを取り出し、出力関数に渡す。

    20ms=人の会話で違和感の少ない単位時間。一定間隔で出すことで音が滑らかに聞こえる。
    """
    while True:
        frame = await jb.pop_frame()
        if frame is None:
            await asyncio.sleep(FRAME_MS / 1000.0)
            continue
        await write_frame(frame)
        await asyncio.sleep(FRAME_MS / 1000.0)
