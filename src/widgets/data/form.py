"""Form widget: text, numeric, checkbox, dropdown (FR-FORM-001..006). Layer L3."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date

from widgets.base_elements.events import KeyEvent
from widgets.base_elements.interactive import InteractiveWidget
from widgets.base_elements.widget_types import DEFAULT_STYLE, RGB, Style, WidgetId
from widgets.render.buffer import Canvas

KINDS = ("text", "int", "float", "checkbox", "dropdown", "date", "textarea")
Validator = Callable[[object], "str | None"]


@dataclass(slots=True)
class Field:
    name: str
    kind: str = "text"
    label: str = ""
    value: object = None
    required: bool = False
    minimum: float | None = None
    maximum: float | None = None
    max_length: int | None = None
    options: Sequence[str] = ()
    validators: Sequence[Validator] = ()
    error: str | None = None
    text: str = ""
    open: bool = False
    _choice: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"field kind must be one of {KINDS}")
        if self.kind == "dropdown" and not self.options:
            raise ValueError("dropdown fields need options")
        if self.kind == "checkbox":
            self.value = bool(self.value)
        elif self.kind == "dropdown":
            self._choice = (
                list(self.options).index(str(self.value)) if self.value in self.options else 0
            )
            self.value = self.options[self._choice]
        else:
            self.text = "" if self.value is None else str(self.value)
        self.label = self.label or self.name

    def current(self) -> object:
        if self.kind in ("checkbox", "dropdown"):
            return self.value
        if self.kind in ("text", "textarea"):
            return self.text
        if self.text.strip() == "":
            return None
        if self.kind == "date":
            return date.fromisoformat(self.text.strip())
        return int(self.text) if self.kind == "int" else float(self.text)

    def validate(self) -> str | None:
        v: object
        try:
            v = self.current()
        except ValueError:
            what = {"int": "a whole number", "date": "a date (YYYY-MM-DD)"}.get(
                self.kind, "a number"
            )
            self.error = f"must be {what}"
            return self.error
        self.error = None
        if self.required and (v is None or v == "" or (v is False and self.kind == "checkbox")):
            self.error = "required"
        elif isinstance(v, date):
            if self.minimum is not None and v < date.fromordinal(int(self.minimum)):
                self.error = f"must be on or after {date.fromordinal(int(self.minimum))}"
            elif self.maximum is not None and v > date.fromordinal(int(self.maximum)):
                self.error = f"must be on or before {date.fromordinal(int(self.maximum))}"
        elif isinstance(v, int | float) and not isinstance(v, bool):
            if self.minimum is not None and v < self.minimum:
                self.error = f"must be >= {self.minimum:g}"
            elif self.maximum is not None and v > self.maximum:
                self.error = f"must be <= {self.maximum:g}"
        if self.error is None:
            for check in self.validators:
                msg = check(v)
                if msg:
                    self.error = msg
                    break
        return self.error


class Form(InteractiveWidget):
    """Form of text, choice and toggle fields with validation."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 50,
        *,
        fields: Sequence[Field] = (),
        on_submit: Callable[[dict[str, object]], object] | None = None,
        on_cancel: Callable[[], object] | None = None,
        on_change: Callable[[str, object], object] | None = None,
        name: WidgetId | None = None,
    ) -> None:
        super().__init__(x, y, width, max(1, len(fields)), name=name)
        names = [f.name for f in fields]
        if len(set(names)) != len(names):
            raise ValueError("field names must be unique")
        self.fields = list(fields)
        self.on_submit, self.on_cancel, self.on_change = on_submit, on_cancel, on_change
        self.index = 0
        self.submitted = False

    def get(self, name: str) -> object:
        for f in self.fields:
            if f.name == name:
                try:
                    return f.current()
                except ValueError:
                    return None
        raise KeyError(name)

    def values(self) -> dict[str, object]:
        out: dict[str, object] = {}
        for f in self.fields:
            try:
                out[f.name] = f.current()
            except ValueError:
                out[f.name] = None
        return out

    def validate(self) -> bool:
        results = [f.validate() for f in self.fields]
        return all(r is None for r in results)

    def submit(self) -> bool:
        """Validate every field; on success call ``on_submit(values)``. Errors block submit."""
        ok = self.validate()
        if ok:
            self.submitted = True
            self.invoke_callback(self.on_submit, self.values())
        return ok

    def _changed(self, f: Field) -> None:
        self.invoke_callback(self.on_change, f.name, self.values()[f.name])

    def handle_key(self, event: KeyEvent) -> bool:
        if not self.effective_enabled or not self.fields:
            return False
        f = self.fields[self.index]
        key = event.key
        if f.kind == "dropdown" and f.open:
            if key in ("up", "down"):
                f._choice = (f._choice + (1 if key == "down" else -1)) % len(f.options)
            elif key in ("enter", "escape"):
                f.open = False
                if key == "enter":
                    f.value = f.options[f._choice]
                    self._changed(f)
            else:
                return False
            return True
        if key in ("tab", "down"):
            self.index = (
                min(len(self.fields) - 1, self.index + 1)
                if key == "down"
                else (self.index + 1) % len(self.fields)
            )
        elif key in ("backtab", "up") or (key == "tab" and event.shift):
            self.index = (
                max(0, self.index - 1) if key == "up" else (self.index - 1) % len(self.fields)
            )
        elif key == "escape":
            self.invoke_callback(self.on_cancel)
        elif key == "enter" and f.kind == "textarea":
            if f.max_length is None or len(f.text) < f.max_length:
                f.text += "\n"
            f.error = None
            self._changed(f)
        elif key == "enter" or (key == "s" and event.ctrl):
            if f.kind == "dropdown" and key == "enter":
                f.open = True
            else:
                self.submit()
        elif f.kind == "checkbox" and key == "space":
            f.value = not f.value
            self._changed(f)
        elif f.kind in ("text", "int", "float", "date", "textarea"):
            if key == "backspace":
                f.text = f.text[:-1]
            elif event.char and event.char.isprintable() and not event.ctrl and not event.alt:
                if f.kind == "date" and not (event.char.isdigit() or event.char == "-"):
                    return True
                if f.max_length is None or len(f.text) < f.max_length:
                    f.text += event.char
                else:
                    return True
            else:
                return False
            f.error = None
            self._changed(f)
        else:
            return False
        return True

    def render(self, canvas: Canvas) -> None:
        label_w = max((len(f.label) for f in self.fields), default=0) + 2
        for r, f in enumerate(self.fields):
            focus = r == self.index and self.focused
            canvas.write_text(
                r, 0, f.label.ljust(label_w) + ("*" if f.required else " "), Style(bold=focus)
            )
            col = label_w + 2
            if f.kind == "checkbox":
                shown = "[x]" if f.value else "[ ]"
            elif f.kind == "dropdown":
                shown = (
                    f"{f.options[f._choice if f.open else f.options.index(f.value)]} ▾"
                    if f.open
                    else f"{f.value} ▾"
                )
            else:
                shown = f.text.replace("\n", "⏎") + ("_" if focus else "")
            canvas.write_text(r, col, shown[: max(0, canvas.width - col)], Style(reverse=focus))
            if f.error:
                err = f"  ! {f.error}"
                canvas.write_text(
                    r,
                    min(canvas.width - 1, col + len(shown)),
                    err[: canvas.width],
                    Style(fg=RGB(230, 70, 70)),
                )
        _ = DEFAULT_STYLE

    def describe(self) -> str:
        return f"Form({', '.join(f'{k}={v!r}' for k, v in self.values().items())})"
