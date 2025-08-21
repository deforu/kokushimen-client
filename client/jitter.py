import asyncio
from collections import deque
from typing import Deque, Optional, Callable

from .audio_io import FRAME_BYTES, FRAME_MS


class JitterBuffer:
    """200ms チャンク入力 → 20ms フレームに分割して供給。

    - prebuffer_ms だけ貯めてから出力開始
    - max_buffer_ms を超えたら古いフレームからドロップ
    """

    def __init__(self, prebuffer_ms: int = 200, max_buffer_ms: int = 600):
        self.queue: Deque[bytes] = deque()
        self.prebuffer_frames = max(0, prebuffer_ms // FRAME_MS)
        self.max_frames = max(1, max_buffer_ms // FRAME_MS)
        self._lock = asyncio.Lock()

    async def push_chunk(self, chunk: bytes):
        # 200ms(6400)を20ms(640)へ分解
        for i in range(0, len(chunk), FRAME_BYTES):
            frame = chunk[i : i + FRAME_BYTES]
            if len(frame) < FRAME_BYTES:
                break
            async with self._lock:
                self.queue.append(frame)
                # オーバーフロー時は古いものからドロップ
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
    """20msごとにフレームを取り出し、出力関数に渡す。"""
    while True:
        frame = await jb.pop_frame()
        if frame is None:
            await asyncio.sleep(FRAME_MS / 1000.0)
            continue
        await write_frame(frame)
        await asyncio.sleep(FRAME_MS / 1000.0)

