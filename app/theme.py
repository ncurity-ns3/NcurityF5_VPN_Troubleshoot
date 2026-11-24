"""Ncurity brand theme — white-first, blue accents (aligned with F5 Managing Tool)."""

from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication

# --- Brand tokens (26Y PPT palette) ---
BRAND_ACCENT_LIGHT = "#25B6FF"
BRAND_ACCENT = "#0093F2"
BRAND_PRIMARY = "#0260EA"
BRAND_NAVY = "#0032DF"

BG_APP = "#F7F9FC"
BG_SURFACE = "#FFFFFF"
BG_SIDEBAR = "#FFFFFF"

BORDER = "#E2E8F0"
BORDER_STRONG = "#94A3B8"
BORDER_FOCUS = "#B8D4F0"

TEXT = "#1A2332"
TEXT_MUTED = "#64748B"

NAV_SELECTED_BG = "#EDF5FF"
NAV_HOVER_BG = "#F4F8FC"
SOFT_FILL = "#F1F5F9"

OK = "#1A7F37"
WARN = "#B45309"
FAIL = "#B42318"

FONT_UI = '"Malgun Gothic", "Segoe UI", sans-serif'
FONT_MONO = '"Consolas", "Malgun Gothic", monospace'


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Malgun Gothic", 10))

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_APP))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SOFT_FILL))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(BRAND_PRIMARY))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)
    app.setStyleSheet(APP_STYLESHEET)


APP_STYLESHEET = f"""
QWidget {{
    font-family: {FONT_UI};
    color: {TEXT};
}}

QMainWindow, QDialog {{
    background: {BG_APP};
}}

#navFrame {{
    background: {BG_SIDEBAR};
    border-right: 1px solid {BORDER};
}}

#navHeader {{
    background: {BG_SIDEBAR};
    border-bottom: 1px solid {BORDER};
    padding: 14px 12px;
}}

#navList {{
    background: {BG_SIDEBAR};
    border: none;
    outline: none;
    padding: 8px;
}}

#navList::item {{
    padding: 10px 12px;
    margin: 2px 0;
    border-radius: 8px;
    border-left: 3px solid transparent;
    color: {TEXT};
}}

#navList::item:hover {{
    background: {NAV_HOVER_BG};
}}

#navList::item:selected {{
    background: {NAV_SELECTED_BG};
    border-left: 3px solid {BRAND_PRIMARY};
    color: {BRAND_PRIMARY};
    font-weight: 600;
}}

#contentHost {{
    background: {BG_APP};
}}

#pageTitle {{
    font-size: 20px;
    font-weight: 700;
    color: {TEXT};
}}

#pageSubtitle {{
    font-size: 12px;
    color: {TEXT_MUTED};
}}

QFrame#card, QFrame#stepCard, QFrame#infoCard, QFrame#heroCard {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QFrame#card:hover {{
    border-color: {BORDER_FOCUS};
    background: {NAV_HOVER_BG};
}}

QLabel#cardTitle {{
    font-size: 14px;
    font-weight: 700;
}}

QLabel#muted {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

QLabel#badge {{
    background: {NAV_SELECTED_BG};
    color: {BRAND_PRIMARY};
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#healthOk {{
    background: #ECFDF3;
    color: {OK};
    border: 1px solid #A7F3D0;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 700;
}}

QLabel#healthBad {{
    background: #FFF5F5;
    color: {FAIL};
    border: 1px solid #FECACA;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 700;
}}

QLabel#healthPending {{
    background: {SOFT_FILL};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    min-height: 18px;
}}

QPushButton:hover {{
    background: {NAV_HOVER_BG};
    border-color: {BORDER_FOCUS};
}}

QPushButton:pressed {{
    background: {SOFT_FILL};
}}

QPushButton:disabled {{
    color: {TEXT_MUTED};
    background: {SOFT_FILL};
}}

QPushButton[role="primary"] {{
    background: {BRAND_PRIMARY};
    color: #FFFFFF;
    border: 1px solid {BRAND_PRIMARY};
    font-weight: 600;
}}

QPushButton[role="primary"]:hover {{
    background: {BRAND_ACCENT};
    border-color: {BRAND_ACCENT};
}}

QPushButton[role="primary"]:pressed {{
    background: {BRAND_NAVY};
    border-color: {BRAND_NAVY};
}}

QPushButton[role="danger"] {{
    background: #FFF5F5;
    color: {FAIL};
    border: 1px solid #FECACA;
    font-weight: 600;
}}

QPushButton[role="danger"]:hover {{
    background: #FEE2E2;
}}

QPushButton[role="success"] {{
    background: #ECFDF3;
    color: {OK};
    border: 1px solid #A7F3D0;
    font-weight: 600;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: {BRAND_PRIMARY};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {BRAND_PRIMARY};
}}

QPlainTextEdit#logView {{
    font-family: {FONT_MONO};
    font-size: 12px;
    background: #0F172A;
    color: #E2E8F0;
    border-radius: 10px;
    border: 1px solid #1E293B;
    padding: 10px;
}}

QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background: {SOFT_FILL};
    text-align: center;
    height: 14px;
}}

QProgressBar::chunk {{
    background: {BRAND_PRIMARY};
    border-radius: 5px;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QStatusBar {{
    background: {BG_SURFACE};
    border-top: 1px solid {BORDER};
    color: {TEXT_MUTED};
}}

QGroupBox {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: {TEXT};
}}

QCheckBox {{
    spacing: 8px;
}}

QListWidget#stepList {{
    background: transparent;
    border: none;
}}

QListWidget#stepList::item {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px;
    margin: 4px 0;
}}
"""
