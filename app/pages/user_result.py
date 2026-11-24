"""End-user diagnosis result — findings + actionable fixes."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.diagnose import DiagnosisReport
from app.widgets import (
    info_row,
    make_card,
    page_header,
    primary_button,
    secondary_button,
)

_STATUS_UI = {
    "ok": ("정상", "healthOk"),
    "pc_issue": ("PC 문제", "healthBad"),
    "suspect": ("주의", "healthPending"),
    "needs_admin": ("관리자", "healthPending"),
    "skip": ("보류", "healthPending"),
}

_FIX_LABELS = {
    "install_sectigo": "인증서 설치",
    "restart_client": "VPN 프로그램 다시 실행",
    "launch_installer": "설치 파일 실행",
}


class UserProgressPage(QWidget):
    cancel = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 40, 28, 28)
        root.setSpacing(16)
        root.addWidget(page_header("진행 중", "잠시만 기다려 주세요."))
        self.status = QLabel("준비하고 있습니다…")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        root.addWidget(self.bar)
        root.addStretch(1)
        stop = secondary_button("중지")
        stop.clicked.connect(self.cancel.emit)
        root.addWidget(stop)

    def set_status(self, text: str) -> None:
        self.status.setText(text)


class UserResultPage(QWidget):
    back_home = pyqtSignal()
    recheck = pyqtSignal()
    save_report = pyqtSignal()
    apply_fix = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._symptom_id = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 16)
        root.setSpacing(12)

        self.header = page_header("점검 결과", "")
        root.addWidget(self.header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        host = QWidget()
        self.body = QVBoxLayout(host)
        self.body.setSpacing(12)
        self.body.setContentsMargins(0, 0, 8, 0)
        scroll.setWidget(host)
        root.addWidget(scroll, stretch=1)

        self.fix_row = QHBoxLayout()
        root.addLayout(self.fix_row)

        actions = QHBoxLayout()
        self.btn_recheck = primary_button("다시 점검")
        self.btn_recheck.clicked.connect(self.recheck.emit)
        self.btn_save = secondary_button("결과 저장")
        self.btn_save.clicked.connect(self.save_report.emit)
        self.btn_home = secondary_button("이슈 목록으로")
        self.btn_home.clicked.connect(self.back_home.emit)
        actions.addWidget(self.btn_recheck)
        actions.addWidget(self.btn_save)
        actions.addWidget(self.btn_home)
        actions.addStretch(1)
        root.addLayout(actions)

    def show_report(self, report: DiagnosisReport) -> None:
        self._symptom_id = report.symptom_id
        while self.body.count():
            item = self.body.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        while self.fix_row.count():
            item = self.fix_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.header.title_label.setText(report.headline())  # type: ignore[attr-defined]
        self.header.subtitle_label.setText(f"{report.symptom_title} 점검 결과")  # type: ignore[attr-defined]
        self.header.subtitle_label.setVisible(True)  # type: ignore[attr-defined]

        summary = make_card()
        sl = QVBoxLayout(summary)
        sl.setContentsMargins(16, 16, 16, 16)
        sl.addWidget(info_row(report.summary()))
        self.body.addWidget(summary)

        for r in report.results:
            label, obj = _STATUS_UI.get(r.status, ("기타", "healthPending"))
            row = make_card()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 10, 14, 10)
            badge = QLabel(label)
            badge.setObjectName(obj)
            left = QVBoxLayout()
            t = QLabel(r.user_label)
            t.setObjectName("cardTitle")
            left.addWidget(t)
            left.addWidget(info_row(r.user_detail))
            if r.fix_hint and r.status != "ok":
                left.addWidget(info_row(f"→ {r.fix_hint}"))
            rl.addLayout(left, stretch=1)
            rl.addWidget(badge)
            self.body.addWidget(row)

        fix = make_card()
        fl = QVBoxLayout(fix)
        fl.setContentsMargins(16, 16, 16, 16)
        ft = QLabel("다음에 할 일")
        ft.setObjectName("cardTitle")
        fl.addWidget(ft)
        fl.addWidget(info_row(report.recommended_fix()))
        if report.has_needs_admin:
            fl.addWidget(
                info_row("담당자 확인이 필요하면 「결과 저장」으로 자료를 모아 전달해 주세요.")
            )
        self.body.addWidget(fix)
        self.body.addStretch(1)

        actions: list[str] = []
        for r in report.results:
            if r.fix_action and r.status in ("pc_issue", "suspect") and r.fix_action not in actions:
                actions.append(r.fix_action)
        for fa in actions:
            btn = primary_button(_FIX_LABELS.get(fa, fa))
            btn.clicked.connect(lambda _=False, a=fa: self.apply_fix.emit(a))
            self.fix_row.addWidget(btn)
        self.fix_row.addStretch(1)

    @property
    def symptom_id(self) -> str:
        return self._symptom_id
