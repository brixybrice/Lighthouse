"""macOS menu bar (top tray) items showing the live f-stop values.

Native NSStatusItem text (PyObjC), not a QSystemTrayIcon pixmap. Repeated,
directly-measured testing (see CLAUDE.md) showed QSystemTrayIcon scales
any icon image down to fit a fixed, undocumented status-item slot — text
drawn that way hits a hard, unpredictable size ceiling no amount of font-
size or padding tuning gets past. NSStatusItem.button.title is real menu
bar text drawn by AppKit's own font renderer instead: the point size we
ask for is the point size that renders, and it adapts to the light/dark
menu bar automatically, the same way any other menu item's text does.

Public interface (connect_show_window/connect_quit/set_toggle_text/
hide_all) is unchanged from the previous QSystemTrayIcon version;
update_display() now takes a (fstop, is_stale) pair per label so a
disconnected sensor's title can grey out instead of vanishing.
"""

import objc
from AppKit import (
    NSColor,
    NSFont,
    NSForegroundColorAttributeName,
    NSMenu,
    NSMenuItem,
    NSStatusBar,
    NSVariableStatusItemLength,
)
from Foundation import NSAttributedString, NSObject

from lighthouse.core.exposure import format_fstop, snap_to_standard_fstop

FONT_SIZE = 18


class _MenuTarget(NSObject):
    """Bridges NSMenuItem's Objective-C target-action to plain Python
    callables — NSMenuItem.setTarget_ doesn't retain the target, so the
    owning SensorTrayIcons keeps this alive for the app's lifetime."""

    def initWithCallbacks_(self, callbacks):
        self = objc.super(_MenuTarget, self).init()
        if self is None:
            return None
        self._callbacks = callbacks
        return self

    def showWindow_(self, _sender):
        self._callbacks["show"]()

    def quitApp_(self, _sender):
        self._callbacks["quit"]()


def _display_text(fstop: float | None) -> str:
    if fstop is None:
        return "—"
    return format_fstop(snap_to_standard_fstop(fstop))


def _apply_title(item, text: str, stale: bool) -> None:
    """Plain title when live; greyed attributed title when the sensor's
    connection is stale — same text, just visually muted."""
    if not stale:
        item.button().setTitle_(text)
        return
    attributed = NSAttributedString.alloc().initWithString_attributes_(
        text, {NSForegroundColorAttributeName: NSColor.tertiaryLabelColor()}
    )
    item.button().setAttributedTitle_(attributed)


class SensorTrayIcons:
    """Owns one native NSStatusItem per sensor, all sharing one menu."""

    def __init__(self):
        self._target = None
        self._menu = None
        self._toggle_item = None
        self._items: dict[str, object] = {}  # label -> NSStatusItem
        self._show_slot = None
        self._quit_slot = None

    def connect_show_window(self, slot) -> None:
        self._show_slot = slot
        self._build_menu_once_ready()

    def connect_quit(self, slot) -> None:
        self._quit_slot = slot
        self._build_menu_once_ready()

    def _build_menu_once_ready(self) -> None:
        if self._menu is not None or self._show_slot is None or self._quit_slot is None:
            return

        self._target = _MenuTarget.alloc().initWithCallbacks_(
            {"show": self._show_slot, "quit": self._quit_slot}
        )

        menu = NSMenu.alloc().init()
        self._toggle_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Show Lighthouse", "showWindow:", ""
        )
        self._toggle_item.setTarget_(self._target)
        menu.addItem_(self._toggle_item)
        menu.addItem_(NSMenuItem.separatorItem())
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit Lighthouse", "quitApp:", ""
        )
        quit_item.setTarget_(self._target)
        menu.addItem_(quit_item)
        self._menu = menu

        for item in self._items.values():
            item.setMenu_(self._menu)

    def set_toggle_text(self, showing: bool) -> None:
        if self._toggle_item is not None:
            self._toggle_item.setTitle_("Hide Lighthouse" if showing else "Show Lighthouse")

    def update_display(self, entries: dict[str, tuple[float | None, bool]]) -> None:
        """entries: label -> (fstop, is_stale). A stale entry's title is
        shown greyed out rather than removed, so a sensor that drops out
        stays visible (last known reading, muted) instead of disappearing."""
        status_bar = NSStatusBar.systemStatusBar()
        for label in list(self._items):
            if label not in entries:
                status_bar.removeStatusItem_(self._items.pop(label))

        for label, (fstop, is_stale) in entries.items():
            item = self._items.get(label)
            if item is None:
                item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
                item.button().setFont_(NSFont.boldSystemFontOfSize_(FONT_SIZE))
                if self._menu is not None:
                    item.setMenu_(self._menu)
                self._items[label] = item
            text = _display_text(fstop)
            _apply_title(item, text, is_stale)
            item.button().setToolTip_(f"{label}: {text}" + (" (offline)" if is_stale else ""))

    def hide_all(self) -> None:
        status_bar = NSStatusBar.systemStatusBar()
        for item in self._items.values():
            status_bar.removeStatusItem_(item)
        self._items.clear()
