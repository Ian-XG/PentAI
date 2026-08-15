from typing import Callable, Optional
from .tui_core import TurnQueue

class TurnController:
    def __init__(self, start_turn: Callable[[str], None]) -> None:
        self._start_turn = start_turn
        self.queue = TurnQueue()
        self.busy = False
        self.stopped = False
        self._awaiting_confirm: Optional[Callable[[bool], None]] = None

    @property
    def awaiting_confirm(self) -> bool:
        return self._awaiting_confirm is not None

    def submit(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self._awaiting_confirm is not None:
            cb, self._awaiting_confirm = self._awaiting_confirm, None
            cb(text.lower() in ("y", "yes"))
            return
        if self.busy:
            self.queue.enqueue(text)
            return
        self._begin(text)

    def _begin(self, text: str) -> None:
        self.busy = True
        self.stopped = False
        self._start_turn(text)

    def finish(self) -> None:
        self.busy = False
        nxt = self.queue.pop()
        if nxt is not None:
            self._begin(nxt)

    def stop(self) -> None:
        if self.busy:
            self.stopped = True
        if self._awaiting_confirm is not None:
            cb, self._awaiting_confirm = self._awaiting_confirm, None
            cb(False)

    def request_confirm(self, on_answer: Callable[[bool], None]) -> None:
        if self.stopped:
            # stop() runs on the main loop thread and can win a race against
            # the worker thread's call_soon_threadsafe-scheduled request: if
            # Escape is processed before that callback runs, stop() finds
            # _awaiting_confirm still None and has nothing to resolve, then
            # THIS arrives after - decline immediately instead of leaving the
            # worker thread's confirm blocked on an answer that will never come.
            on_answer(False)
            return
        self._awaiting_confirm = on_answer
