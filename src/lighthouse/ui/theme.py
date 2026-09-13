"""Shared color/font constants and the application-wide stylesheet.

Same dark palette/approach as Semaphore, so Lighthouse reads as part of the
same family of apps rather than a one-off.
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QPolygon

from lighthouse.core._storage import APP_SUPPORT_DIR

_ICON_DIR = APP_SUPPORT_DIR / "icons"

BACKGROUND = "#202024"
PANEL_BACKGROUND = "#28282d"
BORDER = "#3a3a40"
TEXT = "#c9c9ce"
TEXT_DIM = "#6a6a70"
HOVER_BACKGROUND = "#34343a"

STATUS_OK = "#4caf50"
STATUS_STALE = "#e05a4e"

FONT_FAMILIES = ["Arial", "Helvetica"]
_FONT_FAMILY_CSS = ", ".join(f'"{family}"' if " " in family else family for family in FONT_FAMILIES)


def build_font() -> QFont:
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPointSize(11)
    return font


def _triangle_icon_path(name: str, direction: str, color: str, width: int, height: int) -> str:
    """Renders a small solid-fill triangle to a real PNG file under
    APP_SUPPORT_DIR/icons for use as a QSS combo/spinbox arrow — QSS url()
    does not reliably load data: URIs (see Semaphore/ui/theme.py for the
    two approaches that were tried and rejected there first)."""
    path = _ICON_DIR / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)

    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    if direction == "down":
        points = [QPoint(0, 0), QPoint(width, 0), QPoint(width // 2, height)]
    else:
        points = [QPoint(0, height), QPoint(width, height), QPoint(width // 2, 0)]
    painter.drawPolygon(QPolygon(points))
    painter.end()
    pixmap.save(str(path), "PNG")
    return path.as_posix()


def build_stylesheet() -> str:
    combo_down_arrow = _triangle_icon_path("combo_down_arrow", "down", TEXT, 8, 5)
    spin_up_arrow = _triangle_icon_path("spin_up_arrow", "up", TEXT, 9, 6)
    spin_down_arrow = _triangle_icon_path("spin_down_arrow", "down", TEXT, 9, 6)
    return f"""
    QWidget {{
        background-color: {BACKGROUND};
        color: {TEXT};
        font-family: {_FONT_FAMILY_CSS};
    }}
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: 6px;
        margin-top: 9px;
        padding: 6px;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    QListWidget, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {PANEL_BACKGROUND};
        border: 1px solid {BORDER};
        border-radius: 3px;
        padding: 4px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {PANEL_BACKGROUND};
        color: {TEXT};
        font-family: {_FONT_FAMILY_CSS};
        selection-background-color: {HOVER_BACKGROUND};
        outline: none;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox::down-arrow {{
        image: url({combo_down_arrow});
        width: 8px;
        height: 5px;
        margin-right: 6px;
    }}
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        background-color: transparent;
        border: none;
        width: 14px;
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        image: url({spin_up_arrow});
        width: 9px;
        height: 6px;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: url({spin_down_arrow});
        width: 9px;
        height: 6px;
    }}
    QStatusBar {{
        background-color: {BACKGROUND};
        color: {TEXT_DIM};
    }}
    """
