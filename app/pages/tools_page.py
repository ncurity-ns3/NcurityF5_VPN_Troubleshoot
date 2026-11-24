"""Individual tools page — sectioned (환경 분석 / 임시 조치 / 삭제·재설치)."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.widgets import (
    danger_button,
    info_row,
    make_card,
    page_header,
    primary_button,
)
from app.workflows import TOOL_SECTIONS, Step


class ToolsPage(QWidget):
    run_steps = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._busy = False
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(
            page_header(
                "개별 도구",
                "환경 분석 · 임시 조치 · 삭제/재설치를 섹션별로 실행할 수 있습니다.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 0, 8, 0)

        for section in TOOL_SECTIONS:
            layout.addWidget(self._make_section(section.title, section.summary, section.steps))
        layout.addStretch(1)
        scroll.setWidget(host)
        root.addWidget(scroll, stretch=2)

        self.log = QPlainTextEdit()
        self.log.setObjectName("logView")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)
        root.addWidget(self.log, stretch=1)

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        from PyQt6.QtWidgets import QPushButton

        for btn in self.findChildren(QPushButton):
            if btn.text() == "실행":
                btn.setEnabled(not busy)

    def _make_section(self, title: str, summary: str, steps: list[Step]) -> QWidget:
        wrap = QWidget()
        vl = QVBoxLayout(wrap)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(6)

        head = QLabel(title)
        head.setObjectName("cardTitle")
        vl.addWidget(head)
        if summary:
            vl.addWidget(info_row(summary))

        for step in steps:
            vl.addWidget(self._make_row(step))
        return wrap

    def _make_row(self, step: Step) -> QWidget:
        card = make_card()
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 10, 14, 10)
        left = QVBoxLayout()
        title = QLabel(step.title)
        title.setObjectName("cardTitle")
        left.addWidget(title)
        if step.description:
            left.addWidget(info_row(step.description))
        row.addLayout(left, stretch=1)
        btn = danger_button("실행") if step.destructive else primary_button("실행")
        btn.clicked.connect(lambda _=False, s=step: self._run(s))
        row.addWidget(btn)
        return card

    def _run(self, step: Step) -> None:
        if self._busy:
            return
        if step.requires_confirm:
            reply = QMessageBox.warning(
                self,
                "확인",
                f"실행할까요?\n\n{step.title}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.run_steps.emit([step])
