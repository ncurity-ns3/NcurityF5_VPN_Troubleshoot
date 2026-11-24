"""Issue hub — 8 user symptoms + full scan (no legacy step workflows)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.user_symptoms import FULL_SCAN, SYMPTOMS
from app.widgets import info_row, make_card, page_header, primary_button, secondary_button


class _ClickCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class IssueHubPage(QWidget):
    run_symptom = pyqtSignal(str)
    save_blank_hint = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)
        outer.addWidget(
            page_header(
                "이슈별 조치",
                "증상을 선택하면 PC에서 확인 가능한 항목을 자동 점검합니다. "
                "인증 실패·정책 거부는 관리자 확인으로 안내합니다.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 8, 0)

        full = make_card()
        full.setObjectName("heroCard")
        fl = QVBoxLayout(full)
        fl.setContentsMargins(16, 14, 16, 14)
        fl.setSpacing(8)
        full_btn = primary_button(FULL_SCAN.title)
        full_btn.setMinimumHeight(42)
        full_btn.clicked.connect(lambda: self.run_symptom.emit(FULL_SCAN.id))
        fl.addWidget(full_btn)
        fl.addWidget(info_row(FULL_SCAN.hint))
        layout.addWidget(full)

        q = QLabel("어떤 문제가 발생했나요?")
        q.setObjectName("cardTitle")
        layout.addWidget(q)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        for i, sym in enumerate(SYMPTOMS):
            card = _ClickCard()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(4)
            num = QLabel(f"{i + 1}")
            num.setObjectName("badge")
            title = QLabel(sym.title)
            title.setObjectName("cardTitle")
            title.setWordWrap(True)
            cl.addWidget(num, alignment=Qt.AlignmentFlag.AlignLeft)
            cl.addWidget(title)
            if sym.hint:
                cl.addWidget(info_row(sym.hint))
            card.clicked.connect(lambda sid=sym.id: self.run_symptom.emit(sid))
            grid.addWidget(card, i // 2, i % 2)
        layout.addWidget(grid_host)

        foot = make_card()
        foot_l = QHBoxLayout(foot)
        foot_l.setContentsMargins(14, 12, 14, 12)
        foot_l.addWidget(
            info_row("다른 문제이거나 해결되지 않으면 진단 결과를 저장해 관리자에게 전달하세요."),
            stretch=1,
        )
        save_btn = secondary_button("작업 폴더 열기")
        save_btn.clicked.connect(self.save_blank_hint.emit)
        foot_l.addWidget(save_btn)
        layout.addWidget(foot)

        layout.addStretch(1)
        scroll.setWidget(host)
        outer.addWidget(scroll)
