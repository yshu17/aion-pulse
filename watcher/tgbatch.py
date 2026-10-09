"""Packs chat lines into Telegram messages without going over the group rate limit.

Telegram lets a bot post about 20 messages a minute to one group. The batcher:
  * normally sends 2 chat lines per Telegram message, as soon as the second line arrives;
  * switches to 4 lines per message once the last minute already holds `warn_at` (18) messages;
  * goes back to 2 lines when the last minute holds fewer than `relax_below` (10) messages;
  * never sends more than `limit` (20) messages in any 60 s window — lines wait in the queue;
  * sends a lone line after `flush_after` seconds if no second line comes;
  * when the queue backs up (limit reached), packs more lines per message, up to 4096 characters,
    so nothing is lost and the queue catches up.
Pure logic, no network: the sender calls add() for new lines and poll() on every tick.
"""

from collections import deque

TELEGRAM_MAX_CHARS = 4096


class ChatBatcher:
    def __init__(
        self,
        normal: int = 2,
        compact: int = 4,
        limit: int = 20,
        warn_at: int = 18,
        relax_below: int = 10,
        window_sec: float = 60.0,
        flush_after: float = 3.0,
        max_chars: int = TELEGRAM_MAX_CHARS,
        max_queue: int = 500,
    ) -> None:
        self.normal = normal
        self.compact_size = compact
        self.limit = limit
        self.warn_at = warn_at
        self.relax_below = relax_below
        self.window_sec = window_sec
        self.flush_after = flush_after
        self.max_chars = max_chars
        self.max_queue = max_queue
        self.compact = False
        self.dropped = 0  # lines lost because the queue was full
        self._queue: deque[tuple[float, str]] = deque()
        self._sent: deque[float] = deque()

    @property
    def batch_size(self) -> int:
        return self.compact_size if self.compact else self.normal

    @property
    def queued(self) -> int:
        return len(self._queue)

    def sent_last_window(self, now: float) -> int:
        self._prune(now)
        return len(self._sent)

    def add(self, line: str, now: float) -> None:
        if len(self._queue) >= self.max_queue:
            self._queue.popleft()
            self.dropped += 1
        self._queue.append((now, line))

    def poll(self, now: float) -> list[str]:
        """Telegram messages to send right now (each is chat lines joined by newlines)."""
        out: list[str] = []
        self._prune(now)
        self._update_mode()
        while self._queue and len(self._sent) < self.limit:
            size = self.batch_size
            oldest = self._queue[0][0]
            if len(self._queue) < size and now - oldest < self.flush_after:
                break  # wait a little for more lines to fill the message
            out.append(self._take(size, backlog=len(self._sent) >= self.limit - 1))
            self._sent.append(now)
            self._update_mode()
        return out

    def next_slot_in(self, now: float) -> float:
        """Seconds until another message may be sent (0 if a slot is free)."""
        self._prune(now)
        if len(self._sent) < self.limit:
            return 0.0
        return max(0.0, self._sent[0] + self.window_sec - now)

    # --- internals ----------------------------------------------------------------------
    def _prune(self, now: float) -> None:
        while self._sent and now - self._sent[0] >= self.window_sec:
            self._sent.popleft()

    def _update_mode(self) -> None:
        count = len(self._sent)
        if count >= self.warn_at:
            self.compact = True
        elif count < self.relax_below:
            self.compact = False

    def _take(self, size: int, backlog: bool) -> str:
        """Join the next lines. The last free slot of the minute takes as many as fit 4096 chars."""
        lines: list[str] = []
        length = 0
        while self._queue:
            line = self._queue[0][1][: self.max_chars]
            extra = len(line) + (1 if lines else 0)
            if lines and (length + extra > self.max_chars or (not backlog and len(lines) >= size)):
                break
            lines.append(line)
            length += extra
            self._queue.popleft()
        return "\n".join(lines)
