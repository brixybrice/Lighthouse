"""QApplication bootstrap."""

import sys

from PySide6.QtWidgets import QApplication

from lighthouse.core.logging_setup import configure_logging
from lighthouse.ui.main_window import MainWindow
from lighthouse.ui.theme import build_font, build_stylesheet


def main() -> int:
    configure_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("Lighthouse")
    app.setOrganizationName("brixybrice")
    app.setFont(build_font())
    app.setStyleSheet(build_stylesheet())
    # Closing the window only hides it (see MainWindow.closeEvent) — the
    # tray icon keeps the app alive, same as any macOS menu bar utility.
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    # No explicit resize: the window sizes itself to its fixed-size square
    # panels (see MainWindow._fit_to_content), not an arbitrary guess.
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
