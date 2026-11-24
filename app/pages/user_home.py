"""End-user home — symptom cards + full scan."""

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


class UserHomePage(QWidget):
    run_symptom = pyqtSignal(str)
    open_admin = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 16)
        root.setSpacing(16)

        root.addWidget(
            page_header(
                "VPN 문제 해결 도구",
                "VPN 사용 중 문제가 발생했다면 아래에서 선택해 주세요.",
            )
        )

        hero = make_card()
        hero.setObjectName("heroCard")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(20, 18, 20, 18)
        hl.setSpacing(8)
        full_btn = primary_button(FULL_SCAN.title)
        full_btn.setMinimumHeight(44)
        full_btn.clicked.connect(lambda: self.run_symptom.emit(FULL_SCAN.id))
        hl.addWidget(full_btn)
        hl.addWidget(info_row(FULL_SCAN.hint))
        root.addWidget(hero)

        q = QLabel("어떤 문제가 발생했나요?")
        q.setObjectName("cardTitle")
        root.addWidget(q)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        host = QWidget()
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 8, 0)
        grid.setSpacing(12)

        for i, sym in enumerate(SYMPTOMS):
            card = self._symptom_card(sym.id, sym.title, sym.hint)
            grid.addWidget(card, i // 2, i % 2)
        scroll.setWidget(host)
        root.addWidget(scroll, stretch=1)

        foot = QHBoxLayout()
        foot.addWidget(info_row("진단 결과와 문제 해결 방법을 안내합니다."))
        foot.addStretch(1)
        admin = secondary_button("관리자 모드")
        admin.setToolTip("엔지니어용 상세 진단·복구 메뉴")
        admin.clicked.connect(self.open_admin.emit)
        foot.addWidget(admin)
        root.addLayout(foot)

    def _symptom_card(self, sid: str, title: str, hint: str) -> QWidget:
        card = _ClickCard()
        vl = QVBoxLayout(card)
        vl.setContentsMargins(16, 16, 16, 16)
        vl.setSpacing(6)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        t.setWordWrap(True)
        vl.addWidget(t)
        if hint:
            vl.addWidget(info_row(hint))
        card.clicked.connect(lambda symptom_id=sid: self.run_symptom.emit(symptom_id))
        return card
