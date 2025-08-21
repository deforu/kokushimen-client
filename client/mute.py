import asyncio


class MuteController:
    """再生中のミュート制御（録音側は読み捨て、送信を止める）。"""

    def __init__(self):
        self._muted = asyncio.Event()
        self._muted.clear()

    def is_muted(self) -> bool:
        return self._muted.is_set()

    async def wait_unmuted(self):
        while self._muted.is_set():
            await asyncio.sleep(0.005)

    def set_muted(self, value: bool):
        if value:
            self._muted.set()
        else:
            self._muted.clear()

