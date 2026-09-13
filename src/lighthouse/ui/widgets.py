"""Small reusable widgets shared across the UI."""

from PySide6.QtWidgets import QComboBox


class WideComboBox(QComboBox):
    """A QComboBox whose popup always fits its longest item.

    Qt caps the popup's width to the box's own (often layout-squeezed)
    width by default, which is exactly why option text was getting cut off
    — this widens the popup view on open regardless of how narrow the
    closed box itself is drawn.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

    def showPopup(self) -> None:
        self.view().setMinimumWidth(self.view().sizeHintForColumn(0) + 24)
        super().showPopup()
