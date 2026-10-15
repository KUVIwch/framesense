"""FrameSense · Color Lab 桌面程序入口。"""

from __future__ import annotations

import sys


def main() -> int:
    from pathlib import Path
    from PySide6.QtWidgets import QApplication
    from framesense.ui.theme import apply_theme
    from framesense.ui.resources import app_icon

    app = QApplication(sys.argv)
    app.setApplicationName("FrameSense Color Lab")
    app.setApplicationVersion("0.3.0-preview")
    apply_theme(app)
    app.setWindowIcon(app_icon())
    from framesense.ui.main_window import MainWindow

    verification = None
    if "--verify-package" in sys.argv:
        verification = Path(sys.argv[sys.argv.index("--verify-package") + 1]).resolve()
        verification.parent.mkdir(parents=True, exist_ok=True)
    window = (
        MainWindow(
            db_path=verification.parent / "verification.db",
            draft_path=verification.parent / "draft.json",
        )
        if verification
        else MainWindow()
    )
    window.show()
    if verification:
        from framesense.diagnostics import verify_package

        verify_package(app, window, verification)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
