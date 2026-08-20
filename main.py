"""Arknights Angelina-pet-YuYuan - Desktop Pet Entry Point."""
import sys
import traceback
import time

from PySide6.QtWidgets import QApplication

from core import (
    load_settings, save_settings, ensure_single_instance,
    ERROR_LOG,
)
from pet_window import PetWindow


def main():
    if not ensure_single_instance():
        return 1

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    # Minimal QSS for checkbox checkmark visibility
    app.setStyleSheet(
        "QCheckBox::indicator:checked{background:#e8913a;border:2px solid #e8913a;border-radius:3px;}"
        "QCheckBox::indicator{width:16px;height:16px;border:2px solid #999;border-radius:3px;background:#fff;}"
    )

    settings = load_settings()
    save_settings(settings)

    PetWindow()
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        try:
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"{time.ctime()}\n")
                traceback.print_exc(file=f)
        except OSError:
            pass
        raise
