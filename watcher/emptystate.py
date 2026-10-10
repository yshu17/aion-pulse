"""Empty state of a feed (UI/UX item 12): a picture, a line saying what will appear here and a muted hint,
centred over the empty text area. «Loading» states animate their dots so the program looks alive."""

import tkinter as tk

from watcher import theme
from watcher.ui_icons import IconSet

DOTS_MS = 400


class EmptyState:
    """Overlay for a tk.Text: show(…) while the text has no rows, hide() as soon as it gets one."""

    def __init__(self, text: tk.Text, icons: IconSet) -> None:
        self.text = text
        self.icons = icons
        self.frame = tk.Frame(text, background=theme.SURFACE)
        self.picture = tk.Label(self.frame, background=theme.SURFACE)
        self.picture.pack()
        self.title = tk.Label(self.frame, background=theme.SURFACE, foreground=theme.TEXT, font=theme.font("body"))
        self.title.pack(pady=(theme.SPACE[2], 0))
        self.hint = tk.Label(self.frame, background=theme.SURFACE, foreground=theme.MUTED, font=theme.font("caption"),
                             justify="center")
        self.hint.pack(pady=(theme.SPACE[1], 0))
        self.shown = False
        self._title = ""
        self._dots = 0
        self._after: str | None = None

    def show(self, icon: str, title: str, hint: str = "", loading: bool = False) -> None:
        """icon: a Phosphor name with a 32 px picture (magnifying-glass, chat-circle-dots, hourglass-medium)."""
        self._stop_dots()
        self.picture.configure(image=self.icons.get(icon, "muted", 32) or "")
        self._title = title
        self.title.configure(text=title)
        self.hint.configure(text=hint)
        if not self.shown:
            self.frame.place(relx=0.5, rely=0.45, anchor="center")
            self.shown = True
        if loading:
            self._dots = 0
            self._tick_dots()

    def hide(self) -> None:
        self._stop_dots()
        if self.shown:
            self.frame.place_forget()
            self.shown = False

    def _tick_dots(self) -> None:
        self._dots = (self._dots + 1) % 4
        self.title.configure(text=self._title.rstrip("…") + "." * self._dots)
        self._after = self.text.after(DOTS_MS, self._tick_dots)

    def _stop_dots(self) -> None:
        if self._after is not None:
            self.text.after_cancel(self._after)
            self._after = None
