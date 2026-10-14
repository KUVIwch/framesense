"""FrameSense · Color Lab 桌面程序入口。"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from framesense.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FrameSense Color Lab")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
