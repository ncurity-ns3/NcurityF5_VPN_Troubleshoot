"""Home page — health + shortcuts (original sidebar UI)."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.widgets import (
    info_row,
    make_card,
    page_header,
    primary_button,
    secondary_button,
)


class HomePage(QWidget):
    open_user_info = pyqtSignal()
    open_issues = pyqtSignal()
    open_tools = pyqtSignal()
    open_guide = pyqtSignal()
    run_analyze = pyqtSignal()
    refresh_health = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(
            page_header(
                "F5 SSL VPN 트러블슈팅",
                "증상별 조치 또는 개별 도구를 실행할 수 있습니다. 관리자 권한으로 실행해 주세요.",
            )
        )

        health = make_card()
        hl = QVBoxLayout(health)
        hl.setContentsMargins(16, 16, 16, 16)
        hl.setSpacing(8)

        top = QHBoxLayout()
        ht = QLabel("VPN Client 설치 상태")
        ht.setObjectName("cardTitle")
        top.addWidget(ht)
        top.addStretch(1)
        self.health_badge = QLabel("미실행")
        self.health_badge.setObjectName("healthPending")
        top.addWidget(self.health_badge)
        hl.addLayout(top)

        self.health_summary = QLabel(
            "시작할 때 자동으로 검사하지 않습니다. 필요할 때 「설치 상태 확인」을 눌러 주세요."
        )
        self.health_summary.setObjectName("muted")
        self.health_summary.setWordWrap(True)
        hl.addWidget(self.health_summary)

        self.health_reasons = QLabel("")
        self.health_reasons.setObjectName("muted")
        self.health_reasons.setWordWrap(True)
        hl.addWidget(self.health_reasons)

        row = QHBoxLayout()
        refresh = primary_button("설치 상태 확인")
        refresh.clicked.connect(self.refresh_health.emit)
        analyze = secondary_button("단말기 환경 분석")
        analyze.clicked.connect(self.run_analyze.emit)
        row.addWidget(refresh)
        row.addWidget(analyze)
        row.addStretch(1)
        hl.addLayout(row)
        root.addWidget(health)

        hero = make_card()
        hero.setObjectName("heroCard")
        hero_l = QVBoxLayout(hero)
        hero_l.setContentsMargins(20, 20, 20, 20)
        hero_l.setSpacing(12)

        hero_l.addWidget(QLabel("VPN 접속 문제를 이슈별로 확인하고, 필요한 단계만 실행하세요."))
        hero_l.addWidget(
            info_row("먼저 사용자 정보를 입력한 뒤 조치를 진행해 주세요.")
        )

        b0 = primary_button("1. 사용자 정보 입력")
        b0.clicked.connect(self.open_user_info.emit)
        b1 = secondary_button("2. 이슈별 조치")
        b1.clicked.connect(self.open_issues.emit)
        b2 = secondary_button("개별 도구")
        b2.clicked.connect(self.open_tools.emit)
        b3 = secondary_button("이용 가이드")
        b3.clicked.connect(self.open_guide.emit)
        hero_l.addWidget(b0)
        hero_l.addWidget(b1)
        hero_l.addWidget(b2)
        hero_l.addWidget(b3)
        root.addWidget(hero)

        tip = make_card()
        tip_l = QVBoxLayout(tip)
        tip_l.setContentsMargins(16, 16, 16, 16)
        title = QLabel("시작 전 확인")
        title.setObjectName("cardTitle")
        tip_l.addWidget(title)
        tip_l.addWidget(info_row("• 관리자 권한으로 실행"))
        tip_l.addWidget(info_row("• 브라우저 모두 종료"))
        tip_l.addWidget(info_row("• 사용자 정보 입력"))
        tip_l.addWidget(info_row("• 결과는 바탕화면 F5_VPN_Troubleshoot 폴더에 저장"))
        root.addWidget(tip)
        root.addStretch(1)

    def set_health_idle(self) -> None:
        self.health_badge.setText("미실행")
        self.health_badge.setObjectName("healthPending")
        self.health_badge.style().unpolish(self.health_badge)
        self.health_badge.style().polish(self.health_badge)
        self.health_summary.setText(
            "시작할 때 자동으로 검사하지 않습니다. 필요할 때 「설치 상태 확인」을 눌러 주세요."
        )
        self.health_reasons.setText("")

    def set_health_pending(self) -> None:
        self.health_badge.setText("확인 중…")
        self.health_badge.setObjectName("healthPending")
        self.health_badge.style().unpolish(self.health_badge)
        self.health_badge.style().polish(self.health_badge)
        self.health_summary.setText("설치 상태를 확인하고 있습니다…")
        self.health_reasons.setText("")

    def set_health(self, healthy: bool, summary: str, reasons: list[str]) -> None:
        if healthy:
            self.health_badge.setText("Healthy")
            self.health_badge.setObjectName("healthOk")
            self.health_summary.setText("Edge Client 설치 및 관련 구성이 정상으로 보입니다.")
        else:
            self.health_badge.setText("Unhealthy")
            self.health_badge.setObjectName("healthBad")
            self.health_summary.setText("설치 상태에 문제가 있습니다. 아래를 확인하세요.")
        self.health_badge.style().unpolish(self.health_badge)
        self.health_badge.style().polish(self.health_badge)
        if reasons:
            self.health_reasons.setText("\n".join(f"· {r}" for r in reasons[:6]))
        else:
            self.health_reasons.setText("")
