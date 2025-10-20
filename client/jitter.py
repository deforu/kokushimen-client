import asyncio
from collections import deque
from typing import Deque, Optional, Callable

from .audio_io import FRAME_BYTES, FRAME_MS


class JitterBuffer:
    """200ms チャンク入力 → 20ms フレームに分割して供給。

    ジッターバッファ（jitter buffer）: ネットワークで到着が前後する音声データを
    いったん溜めて順序よく一定の間隔で取り出すための小さな貯蔵庫のこと。

    - prebuffer_ms: 出力を安定させるため、まずこの時間分を貯めてから再生開始。
      （バッファ=一時的な保存場所）
    - max_buffer_ms: ここを超えるほど溜まったら古いフレームから捨てる（遅延を抑えるため）。
    """

    # 途切れ防止のため、バッファを 160ms に増やす
    def __init__(self, prebuffer_ms: int = 160, max_buffer_ms: int = 600):
        self.queue: Deque[bytes] = deque()
        self.prebuffer_frames = max(0, prebuffer_ms // FRAME_MS)
        self.max_frames = max(1, max_buffer_ms // FRAME_MS)
        self._lock = asyncio.Lock()
        
        # チャンク(音声データ)の終わりを知らせるイベントを追加
        self._chunk_ended = asyncio.Event()


    async def push_chunk(self, chunk: bytes):
        """
        大きな音声チャンクを受け取り、20msのフレームに分割して
        キュー（self.queue）に追加する。
        """
        async with self._lock:
            # 新しいチャンクが来たので「終わり」フラグをクリア
            self._chunk_ended.clear()

        for i in range(0, len(chunk), FRAME_BYTES):
            frame = chunk[i : i + FRAME_BYTES]

            if len(frame) == 0:
                continue

            if len(frame) < FRAME_BYTES:
                padding_needed = FRAME_BYTES - len(frame)
                frame += b"\x00" * padding_needed

            async with self._lock:
                self.queue.append(frame)

    # チャンクの終わりを知らせるためのメソッドを追加
    async def signal_end_of_chunk(self):
        """
        呼び出し元(JitteredOutput)がチャンクの終わりを知らせるためのメソッド。
        """
        async with self._lock:
            self._chunk_ended.set()


    async def pop_frame(self) -> Optional[bytes]:
        async with self._lock:
            if not self.queue:
                return None

            # 1. チャンクが終了しているか (短い音声への対応)
            # 2. プリバッファが溜まっているか (通常のストリーム)
            # どちらかの条件を満たせば再生を許可
            if self._chunk_ended.is_set() or len(self.queue) >= self.prebuffer_frames:
                return self.queue.popleft()

            return None


async def playback_loop(jb: JitterBuffer, write_frame: Callable[[bytes], asyncio.Future]):
    """
    20msごとにフレームを取り出し、出力関数に渡す。
    （再生速度を調整できるように修正済み）
    """
    from .audio_io import FRAME_MS

    # 再生速度 (1.0 = 通常, 1.25 = 25% 高速化)
    PLAYBACK_SPEED_FACTOR = 1.25
    
    # 速度を反映した、1フレームあたりの目標処理時間 (ms)
    TARGET_FRAME_MS = FRAME_MS / PLAYBACK_SPEED_FACTOR
    TARGET_FRAME_SEC = TARGET_FRAME_MS / 1000.0

    while True:
        loop_start_time = asyncio.get_event_loop().time()

        frame = await jb.pop_frame()
        if frame is None:
            await asyncio.sleep(TARGET_FRAME_SEC)
            continue

        await write_frame(frame)
        
        time_taken = asyncio.get_event_loop().time() - loop_start_time
        sleep_duration = TARGET_FRAME_SEC - time_taken
        
        if sleep_duration < 0:
            sleep_duration = 0 
            print(f"⚠️ [playback_loop] 再生が遅延しています (速度: {PLAYBACK_SPEED_FACTOR}x)！")
        
        await asyncio.sleep(sleep_duration)
