"""Format-neutral workbook model shared by the ODS and XLSX readers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CellStyle:
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: Optional[str] = None
    fill: Optional[str] = None
    h_align: Optional[str] = None      # left|center|right|None(general)
    v_align: Optional[str] = None      # top|center|bottom|None
    wrap: bool = False
    shrink: bool = False
    border: str = ""                   # e.g. "thin" when all four sides, else per-side "L:thin,T:thin"
    number_format: Optional[str] = None

    def key(self) -> tuple:
        return tuple(self.__dict__.values())


@dataclass
class Cell:
    row: int                           # 1-based
    col: int                           # 1-based
    value: Any = None                  # str | int | float | datetime.date | None
    kind: str = "empty"                # empty|string|int|float|date|bool
    text: str = ""                     # display text as stored (line breaks = "\n")
    style: CellStyle = field(default_factory=CellStyle)
    comment: Optional[str] = None

    @property
    def ref(self) -> str:
        return f"{col_letter(self.col)}{self.row}"


@dataclass
class PrintSetup:
    orientation: Optional[str] = None
    paper_w_in: Optional[float] = None
    paper_h_in: Optional[float] = None
    margin_top: Optional[float] = None
    margin_bottom: Optional[float] = None
    margin_left: Optional[float] = None
    margin_right: Optional[float] = None
    fit_width: Optional[int] = None
    fit_height: Optional[int] = None
    scale_pct: Optional[int] = None
    title_rows: Optional[str] = None
    freeze: Optional[str] = None


@dataclass
class Sheet:
    name: str
    cells: dict[tuple[int, int], Cell] = field(default_factory=dict)
    col_widths_in: dict[int, float] = field(default_factory=dict)   # 1-based col -> inches
    row_heights_pt: dict[int, float] = field(default_factory=dict)
    merged: list[str] = field(default_factory=list)
    print: PrintSetup = field(default_factory=PrintSetup)
    max_row: int = 0
    max_col: int = 0

    def get(self, row: int, col: int) -> Cell:
        return self.cells.get((row, col)) or Cell(row, col)

    def row_values(self, row: int, ncols: Optional[int] = None) -> list[Any]:
        n = ncols or self.max_col
        return [self.get(row, c).value for c in range(1, n + 1)]


@dataclass
class Workbook:
    path: str
    fmt: str                           # ods|xlsx
    sheets: list[Sheet] = field(default_factory=list)
    default_font: Optional[tuple[str, float]] = None
    properties: dict[str, str] = field(default_factory=dict)


def col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def display_text(cell: "Cell") -> str:
    """Text as a spreadsheet would display it (dates as m/d/yyyy)."""
    import datetime as _dt
    if cell.kind == "date" and isinstance(cell.value, (_dt.date, _dt.datetime)):
        v = cell.value
        return f"{v.month}/{v.day}/{v.year}"
    return cell.text or ("" if cell.value is None else str(cell.value))
