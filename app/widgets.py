"""Shared UI widgets."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


def make_card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setFrameShape(QFrame.Shape.NoFrame)
    return frame


def page_header(title: str, subtitle: str = "") -> QWidget:
    wrap = QWidget()
    layout = QVBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 8)
    layout.setSpacing(4)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    layout.addWidget(t)
    s = QLabel(subtitle or "")
    s.setObjectName("pageSubtitle")
    s.setWordWrap(True)
    s.setVisible(bool(subtitle))
    layout.addWidget(s)
    wrap.title_label = t  # type: ignore[attr-defined]
    wrap.subtitle_label = s  # type: ignore[attr-defined]
    return wrap


def primary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("role", "primary")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def danger_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("role", "danger")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def secondary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def info_row(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("muted")
    lbl.setWordWrap(True)
    return lbl


def badge(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("badge")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


def hbox(*widgets: QWidget, stretch_last: bool = False) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for i, w in enumerate(widgets):
        layout.addWidget(w)
        if stretch_last and i == len(widgets) - 1:
            layout.setStretch(i, 1)
    return layout
