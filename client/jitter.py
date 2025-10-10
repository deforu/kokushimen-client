# jitter.py の内容をまるごと以下に置き換えてください

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
        # max_frames はもう使いませんが、互換性のために残しておきます
        self.max_frames = max(1, max_buffer_ms // FRAME_MS)
        self._lock = asyncio.Lock()

    # ★★★ 修正済みの push_chunk (クラスの内側) ★★★
    async def push_chunk(self, chunk: bytes):
        """
        大きな音声チャンクを受け取り、20msのフレームに分割して
        キュー（self.queue）に追加する。
        """
        for i in range(0, len(chunk), FRAME_BYTES):
            frame = chunk[i : i + FRAME_BYTES]

            if len(frame) == 0:
                continue # 空のフレームは無視
            
            # フレームが FRAME_BYTES (640) より短い場合、
            # 足りない分を無音 (b'\x00') で埋める (パディング)
            if len(frame) < FRAME_BYTES:
                padding_needed = FRAME_BYTES - len(frame)
                frame += b"\x00" * padding_needed
            
            async with self._lock:
                self.queue.append(frame)
                
                # ★ オーバーフロー処理は削除済み ★
                # (サーバーが再生完了を待つため、クライアント側で
                #  フレームを捨てる必要がなくなった)


    # ★★★ pop_frame (クラスの内側・変更なし) ★★★
    async def pop_frame(self) -> Optional[bytes]:
        async with self._lock:
            if not self.queue:
                return None
            # プリバッファが溜まるまで待つ
            if len(self.queue) < self.prebuffer_frames:
                return None
            return self.queue.popleft()


# ★★★ playback_loop (クラスの外側・変更なし) ★★★
# jitter.py の playback_loop 関数を以下に置き換えてください

async def playback_loop(jb: JitterBuffer, write_frame: Callable[[bytes], asyncio.Future]):
    """
    20msごとにフレームを取り出し、出力関数に渡す。
    （★ 再生間隔を正確に保つように修正済み）
    """
    
    # audio_io から FRAME_MS をインポート
    # (jitter.py の先頭に `from .audio_io import FRAME_MS` があるか確認してください)
    from .audio_io import FRAME_MS
    
    while True:
        # ループの開始時間を記録
        loop_start_time = asyncio.get_event_loop().time()

        frame = await jb.pop_frame()
        if frame is None:
            # プリバッファ中か、再生が追いついた
            await asyncio.sleep(FRAME_MS / 1000.0)
            continue
        
        # 音声フレームを書き込む
        await write_frame(frame)
        
        # 処理にかかった時間（フレーム取得＋書き込み）を計算
        time_taken = asyncio.get_event_loop().time() - loop_start_time
        
        # 20ms から 処理にかかった時間を引いた分だけスリープする
        sleep_duration = (FRAME_MS / 1000.0) - time_taken
        
        if sleep_duration < 0:
            # 処理が20msを超えた場合 (PCがビジー)
            sleep_duration = 0 
            print("⚠️ [playback_loop] 再生が遅延しています！")
        
        await asyncio.sleep(sleep_duration)