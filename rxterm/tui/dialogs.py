"""Mouse-friendly pop-up dialogs: pick a stock, set a price alert."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList
from textual.widgets.option_list import Option

from .. import universe


class TickerPicker(ModalScreen[str | None]):
    """Click a stock from the list (type to filter if you like). Esc or Cancel closes."""

    DEFAULT_CSS = """
    TickerPicker { align: center middle; background: rgba(0,0,0,0.6); }
    #picker { width: 70; height: 32; border: round #ff9e1b; background: #0b0d10; padding: 0 1; }
    #picker-title { color: #ff9e1b; text-style: bold; height: 1; margin: 0 0 1 0; }
    #picker-filter { height: 3; margin-bottom: 1; }
    #picker-list { height: 1fr; border: round #3a3f47; }
    #picker-buttons { height: 3; align: right middle; }
    """

    def __init__(self, title: str = "Choose a stock", exclude: list[str] | None = None):
        super().__init__()
        self.title_text = title
        self.exclude = set(exclude or [])

    def compose(self) -> ComposeResult:
        with Vertical(id="picker"):
            yield Label(self.title_text, id="picker-title")
            yield Input(placeholder="Filter (optional) — or just scroll and click", id="picker-filter")
            yield OptionList(id="picker-list")
            with Horizontal(id="picker-buttons"):
                yield Button("Cancel", id="picker-cancel")

    def on_mount(self) -> None:
        self._fill("")
        self.query_one("#picker-list").focus()

    def _fill(self, q: str) -> None:
        q = q.strip().upper()
        ol = self.query_one("#picker-list", OptionList)
        ol.clear_options()
        secs = list(universe.equities()) + [universe.UNIVERSE[t] for t in universe.BENCHMARKS]
        for s in secs:
            if s.ticker in self.exclude:
                continue
            if q and q not in s.ticker and q not in s.name.upper():
                continue
            ol.add_option(Option(f"{s.ticker:<6} {s.name}  ·  {s.segment}", id=s.ticker))

    @on(Input.Changed, "#picker-filter")
    def _filter(self, event: Input.Changed) -> None:
        self._fill(event.value)

    @on(Input.Submitted, "#picker-filter")
    def _enter(self, event: Input.Submitted) -> None:
        ol = self.query_one("#picker-list", OptionList)
        if ol.option_count:
            self.dismiss(ol.get_option_at_index(0).id)

    @on(OptionList.OptionSelected, "#picker-list")
    def _picked(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    @on(Button.Pressed, "#picker-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)


class AlertDialog(ModalScreen[tuple[str, float] | None]):
    """Set a price alert with the mouse: quick-fill buttons, then 'Alert above' / 'Alert below'."""

    DEFAULT_CSS = """
    AlertDialog { align: center middle; background: rgba(0,0,0,0.6); }
    #alert { width: 84; height: auto; border: round #ff9e1b; background: #0b0d10; padding: 1 2; }
    #alert-title { color: #ff9e1b; text-style: bold; margin-bottom: 1; }
    #alert-price { margin-bottom: 1; }
    .row { height: 3; margin-bottom: 1; }
    .row Button { margin-right: 1; min-width: 9; }
    #alert-error { color: #ff4d4f; height: 1; }
    """

    def __init__(self, ticker: str, last: float | None):
        super().__init__()
        self.ticker = ticker
        self.last = last

    def compose(self) -> ComposeResult:
        with Vertical(id="alert"):
            now = f"  (now {self.last:,.2f})" if self.last else ""
            yield Label(f"Price alert for {self.ticker}{now}", id="alert-title")
            yield Input(value=f"{self.last:.2f}" if self.last else "", placeholder="Price", id="alert-price")
            with Horizontal(classes="row"):
                for pct in (-10, -5, -2, 2, 5, 10):
                    yield Button(f"{pct:+d}%", id=f"pct{pct:+d}".replace("+", "p").replace("-", "m"))
            with Horizontal(classes="row"):
                yield Button("Alert above ▲", id="above", variant="success")
                yield Button("Alert below ▼", id="below", variant="error")
                yield Button("Cancel", id="cancel")
            yield Label("", id="alert-error")

    @on(Button.Pressed)
    def _press(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        price_in = self.query_one("#alert-price", Input)
        if bid.startswith("pct"):
            pct = int(bid[4:]) * (-1 if bid[3] == "m" else 1)
            if self.last:
                price_in.value = f"{self.last * (1 + pct / 100):.2f}"
            return
        if bid == "cancel":
            self.dismiss(None)
            return
        try:
            level = float(price_in.value.replace(",", "").strip())
        except ValueError:
            self.query_one("#alert-error", Label).update("Enter a price, or use the % buttons.")
            return
        self.dismiss((">" if bid == "above" else "<", level))

    def key_escape(self) -> None:
        self.dismiss(None)
