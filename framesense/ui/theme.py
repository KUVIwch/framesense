"""FrameSense's quiet darkroom/editorial visual system.

One token table per theme feeds native Qt palettes and the shared stylesheet.
No photo processing depends on the interface palette.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

DARK = {
    "background": "#151b1b",
    "surface": "#1c2423",
    "raised": "#252e2b",
    "well": "#101514",
    "text": "#e6e0d5",
    "muted": "#adb6ad",
    "border": "#3c4943",
    "accent": "#c78961",
    "accent_hover": "#dc9e76",
    "accent_text": "#151b1b",
    "teal": "#6f9990",
    "selection": "#3c6158",
    "disabled": "#7f8a82",
    "error": "#e59c89",
}
LIGHT = {
    "background": "#eeebe4",
    "surface": "#f7f4ed",
    "raised": "#e2ded4",
    "well": "#dedbd2",
    "text": "#26342f",
    "muted": "#59665e",
    "border": "#a8b0a5",
    "accent": "#8b4c2e",
    "accent_hover": "#713d25",
    "accent_text": "#fffaf0",
    "teal": "#3c7065",
    "selection": "#c0d7ca",
    "disabled": "#727c72",
    "error": "#9b3d30",
}


def _tokens(name: str) -> dict[str, str]:
    if name not in ("dark", "light"):
        raise ValueError("Theme must be 'dark' or 'light'")
    return LIGHT if name == "light" else DARK


def stylesheet(name: str = "dark") -> str:
    c = _tokens(name)
    return f"""
    QWidget {{ background: {c['background']}; color: {c['text']};
        selection-background-color: {c['selection']}; selection-color: {c['text']}; }}
    QMainWindow, QDialog {{ background: {c['background']}; }}
    QWidget:disabled {{ color: {c['disabled']}; }}
    QLabel {{ background: transparent; }}
    QLabel#brand {{ font-size: 21px; font-weight: 600; letter-spacing: -.4px; }}
    QLabel#eyebrow {{ color: {c['teal']}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
    QLabel#sectionTitle {{ font-size: 14px; font-weight: 600; padding: 2px 0px; }}
    QLabel#muted, QLabel[role="subtle"] {{ color: {c['muted']}; }}
    QFrame#toolbar {{ background: {c['surface']}; border: 0;
        border-bottom: 1px solid {c['border']}; }}
    QFrame#sidebar {{ background: {c['surface']}; border: 0;
        border-left: 1px solid {c['border']}; }}
    QFrame#imageWell {{ background: {c['well']}; border: 0; }}
    QGroupBox {{ border: 0; border-top: 1px solid {c['border']};
        margin-top: 18px; padding-top: 16px; font-weight: 600; }}
    QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left;
        padding: 0px 6px 0px 0px; color: {c['muted']}; }}
    QPushButton, QToolButton {{ background: {c['surface']}; color: {c['text']};
        border: 1px solid {c['border']}; border-radius: 4px;
        padding: 7px 12px; min-height: 20px; }}
    QPushButton:hover, QToolButton:hover {{ background: {c['raised']}; border-color: {c['muted']}; }}
    QPushButton:pressed, QToolButton:pressed {{ background: {c['selection']}; }}
    QPushButton:checked, QToolButton:checked {{ border-color: {c['teal']}; background: {c['selection']}; }}
    QPushButton:focus, QToolButton:focus {{ border: 1px solid {c['accent']}; }}
    QPushButton:disabled, QToolButton:disabled {{ color: {c['disabled']}; background: {c['surface']};
        border-color: {c['border']}; }}
    QPushButton#primary {{ background: {c['accent']}; color: {c['accent_text']};
        border-color: {c['accent']}; font-weight: 600; }}
    QPushButton#primary:hover {{ background: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
    QPushButton#primary:disabled {{ background: {c['raised']}; color: {c['disabled']};
        border-color: {c['border']}; }}
    QPushButton#quiet, QToolButton#quiet {{ background: transparent; border-color: transparent; }}
    QPushButton#quiet:hover, QToolButton#quiet:hover {{ background: {c['raised']}; border-color: {c['border']}; }}
    QToolButton {{ padding: 5px 8px; }}
    QToolButton::menu-indicator {{ subcontrol-position: bottom right; }}
    QTabWidget::pane {{ border: 0; border-top: 1px solid {c['border']}; }}
    QTabBar::tab {{ background: transparent; color: {c['muted']}; border: 0;
        border-bottom: 2px solid transparent; padding: 9px 10px; margin-right: 3px; }}
    QTabBar::tab:selected {{ color: {c['text']}; border-bottom-color: {c['accent']}; }}
    QTabBar::tab:hover {{ background: {c['raised']}; color: {c['text']}; }}
    QTextBrowser, QTextEdit, QPlainTextEdit {{ background: {c['surface']};
        color: {c['text']}; border: 1px solid {c['border']}; border-radius: 3px;
        padding: 9px; selection-background-color: {c['selection']}; }}
    QTextBrowser:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {c['teal']}; }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {c['well']}; color: {c['text']};
        border: 1px solid {c['border']}; border-radius: 3px; padding: 6px 8px; min-height: 20px; }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {c['accent']}; }}
    QComboBox {{ padding-right: 24px; }}
    QComboBox::drop-down {{ width: 22px; border: 0; }}
    QComboBox::down-arrow {{ image: url(__FRAMESENSE_CHEVRON__); width: 10px; height: 10px; }}
    QComboBox QAbstractItemView {{ background: {c['surface']}; border: 1px solid {c['border']};
        selection-background-color: {c['selection']}; selection-color: {c['text']}; padding: 4px; }}
    QAbstractItemView {{ background: {c['surface']}; alternate-background-color: {c['raised']};
        color: {c['text']}; border: 1px solid {c['border']}; }}
    QAbstractItemView::item {{ padding: 6px; }}
    QAbstractItemView::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
    QHeaderView::section {{ background: {c['raised']}; color: {c['muted']};
        padding: 6px; border: 0; border-bottom: 1px solid {c['border']}; }}
    QCheckBox, QRadioButton {{ background: transparent; spacing: 7px; padding: 3px 0px; }}
    QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {c['muted']};
        border-radius: 2px; background: {c['well']}; }}
    QCheckBox::indicator:checked {{ background: {c['teal']}; border-color: {c['teal']};
        image: url(__FRAMESENSE_CHECK__); }}
    QCheckBox::indicator:disabled {{ border-color: {c['border']}; background: {c['raised']}; }}
    QSplitter::handle {{ background: {c['background']}; width: 7px; height: 7px; }}
    QSplitter::handle:hover {{ background: {c['border']}; }}
    QScrollArea {{ background: transparent; border: 0; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; min-height: 30px; border-radius: 4px; margin: 2px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: {c['border']}; min-width: 30px; border-radius: 4px; margin: 2px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QSlider::groove:horizontal {{ background: {c['border']}; height: 3px; }}
    QSlider::handle:horizontal {{ background: {c['teal']}; border: 1px solid {c['teal']};
        width: 12px; height: 12px; margin: -5px 0px; border-radius: 6px; }}
    QProgressBar {{ background: {c['well']}; border: 1px solid {c['border']};
        border-radius: 2px; text-align: center; min-height: 12px; }}
    QProgressBar::chunk {{ background: {c['teal']}; }}
    QStatusBar {{ background: {c['surface']}; color: {c['muted']};
        border-top: 1px solid {c['border']}; font-size: 11px; }}
    QStatusBar::item {{ border: 0; }}
    QMenuBar {{ background: {c['surface']}; color: {c['text']}; }}
    QMenuBar::item {{ padding: 6px 10px; background: transparent; }}
    QMenuBar::item:selected {{ background: {c['raised']}; }}
    QMenu {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 5px; }}
    QMenu::item {{ padding: 6px 24px 6px 12px; }}
    QMenu::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
    QMenu::item:disabled {{ color: {c['disabled']}; }}
    QMenu::separator {{ height: 1px; background: {c['border']}; margin: 5px 4px; }}
    QToolTip {{ background: {c['raised']}; color: {c['text']};
        border: 1px solid {c['border']}; padding: 6px; }}
    """.replace("__FRAMESENSE_CHECK__", _asset_url("check", name)).replace(
        "__FRAMESENSE_CHEVRON__", _asset_url("chevron", name)
    )


def _asset_url(stem: str, name: str) -> str:
    from framesense.ui.resources import asset_path

    return asset_path(
        f"{stem}-light.svg" if name == "light" else f"{stem}.svg"
    ).as_posix()


def apply_theme(app: QApplication, name: str = "dark") -> None:
    """Apply an explicit theme and readable system font without restart."""
    c = _tokens(name)
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: "background",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "well",
        QPalette.ColorRole.AlternateBase: "surface",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "surface",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.ToolTipBase: "raised",
        QPalette.ColorRole.ToolTipText: "text",
        QPalette.ColorRole.Highlight: "selection",
        QPalette.ColorRole.HighlightedText: "text",
        QPalette.ColorRole.PlaceholderText: "muted",
        QPalette.ColorRole.Link: "accent",
        QPalette.ColorRole.LinkVisited: "teal",
        QPalette.ColorRole.Light: "border",
        QPalette.ColorRole.Mid: "border",
        QPalette.ColorRole.Dark: "well",
        QPalette.ColorRole.Shadow: "well",
    }
    for role, key in roles.items():
        palette.setColor(role, QColor(c[key]))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["disabled"]))
    app.setPalette(palette)
    families = QFontDatabase.families()
    family = next(
        (
            f
            for f in ("Microsoft YaHei UI", "Segoe UI", "Noto Sans CJK SC")
            if f in families
        ),
        "sans-serif",
    )
    font = QFont(family, 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    app.setProperty("frameSenseTheme", name)
    app.setStyleSheet(stylesheet(name))
