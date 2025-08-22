import asyncio


class MuteController:
    """再生中のミュート制御（録音側は読み捨て、送信を止める）。

    ミュート: 音を一時的に無効化すること（相手に聞こえない状態にする）。
    再生中に別の音（TTS=合成音声 など）が鳴る間だけ、自分のマイク送信を止める用途。
    """

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
