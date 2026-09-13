"""Central logging setup.

A rotating file under Application Support so background-thread failures
(the UDP listener worker) leave a trace even in the packaged .app, which
has no attached console.
"""

import logging
from logging.handlers import RotatingFileHandler

from lighthouse.core._storage import APP_SUPPORT_DIR

LOG_FILE = APP_SUPPORT_DIR / "lighthouse.log"

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    _configured = True
