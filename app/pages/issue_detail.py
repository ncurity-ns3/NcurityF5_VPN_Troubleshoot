"""Issue detail — run steps one-by-one or as a sequence."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.widgets import (
    badge,
    danger_button,
    info_row,
    make_card,
    page_header,
    primary_button,
    secondary_button,
)
from app.workflows import IssueWorkflow, Step, get_issue


class IssueDetailPage(QWidget):
    run_steps = pyqtSignal(list)  # list[Step]
    back = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._issue: IssueWorkflow | None = None
        self._step_status: dict[int, QLabel] = {}
        self._busy = False

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 24, 24, 24)
        self.root.setSpacing(12)

        self.header_host = QVBoxLayout()
        self.root.addLayout(self.header_host)

        self.notes_card = make_card()
        self.notes_layout = QVBoxLayout(self.notes_card)
        self.notes_layout.setContentsMargins(14, 12, 14, 12)
        self.root.addWidget(self.notes_card)

        actions = QHBoxLayout()
        self.btn_back = secondary_button("← 이슈 목록")
        self.btn_back.clicked.connect(self.back.emit)
        self.btn_run_all = primary_button("순서대로 실행")
        self.btn_run_all.clicked.connect(self._on_run_all)
        self.btn_stop = danger_button("중지")
        self.btn_stop.setEnabled(False)
        actions.addWidget(self.btn_back)
        actions.addStretch(1)
        actions.addWidget(self.btn_stop)
        actions.addWidget(self.btn_run_all)
        self.root.addLayout(actions)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.steps_host = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_host)
        self.steps_layout.setSpacing(8)
        self.steps_layout.setContentsMargins(0, 0, 8, 0)
        scroll.setWidget(self.steps_host)
        self.root.addWidget(scroll, stretch=2)

        self.log = QPlainTextEdit()
        self.log.setObjectName("logView")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("실행 결과가 여기에 표시됩니다.")
        self.log.setMinimumHeight(160)
        self.root.addWidget(self.log, stretch=1)

    def set_issue(self, issue_id: str) -> None:
        issue = get_issue(issue_id)
        if not issue:
            return
        self._issue = issue
        self._rebuild()

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def clear_log(self) -> None:
        self.log.clear()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.btn_run_all.setEnabled(not busy)
        self.btn_stop.setEnabled(busy)
        for btn in self.findChildren(QPushButton):
            if btn in (self.btn_back, self.btn_stop):
                continue
            if btn is self.btn_run_all:
                continue
            # step "실행" buttons
            if btn.text() == "실행":
                btn.setEnabled(not busy)

    def mark_step(self, index: int, ok: bool | None) -> None:
        lbl = self._step_status.get(index)
        if not lbl:
            return
        if ok is None:
            lbl.setText("실행 중…")
            lbl.setStyleSheet("color: #0260EA; font-weight: 600;")
        elif ok:
            lbl.setText("완료")
            lbl.setStyleSheet("color: #1A7F37; font-weight: 600;")
        else:
            lbl.setText("확인 필요")
            lbl.setStyleSheet("color: #B42318; font-weight: 600;")

    def _rebuild(self) -> None:
        assert self._issue is not None
        issue = self._issue

        while self.header_host.count():
            item = self.header_host.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.header_host.addWidget(page_header(issue.title, issue.summary))
        self.header_host.addWidget(badge(issue.guide_ref), alignment=Qt.AlignmentFlag.AlignLeft)

        while self.notes_layout.count():
            item = self.notes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        title = QLabel("안내")
        title.setObjectName("cardTitle")
        self.notes_layout.addWidget(title)
        for note in issue.notes:
            self.notes_layout.addWidget(info_row(f"• {note}"))

        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._step_status.clear()

        for idx, step in enumerate(issue.steps):
            self.steps_layout.addWidget(self._make_step_card(idx, step))
        self.steps_layout.addStretch(1)
        self.clear_log()

    def _make_step_card(self, idx: int, step: Step) -> QWidget:
        card = make_card()
        card.setObjectName("stepCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)

        left = QVBoxLayout()
        title = QLabel(step.title)
        title.setObjectName("cardTitle")
        left.addWidget(title)
        if step.description:
            left.addWidget(info_row(step.description))
        status = QLabel("대기")
        status.setObjectName("muted")
        self._step_status[idx] = status
        left.addWidget(status)
        layout.addLayout(left, stretch=1)

        btn = danger_button("실행") if step.destructive else primary_button("실행")
        btn.clicked.connect(lambda _=False, i=idx: self._on_run_one(i))
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignTop)
        return card

    def _confirm(self, step: Step) -> bool:
        if not step.requires_confirm:
            return True
            reply = QMessageBox.warning(
                self,
                "확인",
                f"다음 작업을 실행할까요?\n\n{step.title}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
        return reply == QMessageBox.StandardButton.Yes

    def _on_run_one(self, idx: int) -> None:
        if not self._issue or self._busy:
            return
        step = self._issue.steps[idx]
        if not self._confirm(step):
            return
        self.run_steps.emit([(idx, step)])

    def _on_run_all(self) -> None:
        if not self._issue or self._busy:
            return
        # Confirm if any remaining destructive steps
        destructive = [s for s in self._issue.steps if s.requires_confirm]
        if destructive:
            reply = QMessageBox.warning(
                self,
                "확인",
                "일부 단계는 PC 설정이나 프로그램을 변경합니다.\n계속할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        jobs = [(i, s) for i, s in enumerate(self._issue.steps)]
        self.run_steps.emit(jobs)
