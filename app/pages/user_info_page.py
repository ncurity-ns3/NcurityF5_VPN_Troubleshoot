"""User-reported case information form."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.user_info import UserCaseInfo, get_user_info, set_user_info
from app.widgets import info_row, make_card, page_header, primary_button, secondary_button


class UserInfoPage(QWidget):
    saved = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        root.addWidget(
            page_header(
                "사용자 정보",
                "문제 해결에 필요한 기본 정보입니다. 정확하게 입력해 주세요.",
            )
        )
        root.addWidget(
            info_row(
                "VPN 접속 도메인은 이슈별 조치의 서버 접근(DNS/HTTPS) 점검에 그대로 사용됩니다. "
                "오류 문구는 「연결 시 오류 메시지」 진단 분기에도 사용됩니다."
            )
        )

        card = make_card()
        form_wrap = QVBoxLayout(card)
        form_wrap.setContentsMargins(16, 16, 16, 16)
        form = QFormLayout()
        form.setSpacing(10)

        self.edit_id = QLineEdit()
        self.edit_id.setPlaceholderText("예: hong.gildong")
        form.addRow("사용자 계정 (ID) *", self.edit_id)

        self.edit_time = QLineEdit()
        self.edit_time.setPlaceholderText("예: 2026-07-31 14:30")
        form.addRow("이슈 발생 시간 *", self.edit_time)

        self.edit_domain = QLineEdit()
        self.edit_domain.setPlaceholderText("예: vpn.company.com")
        form.addRow("VPN 접속 도메인 *", self.edit_domain)

        self.edit_os = QLineEdit()
        self.edit_os.setPlaceholderText("예: Windows 11 24H2")
        form.addRow("OS 버전", self.edit_os)

        self.edit_symptom = QPlainTextEdit()
        self.edit_symptom.setPlaceholderText("화면에 표시된 오류 문구, 재현 방법 등")
        self.edit_symptom.setFixedHeight(80)
        form.addRow("증상 / 오류 메시지", self.edit_symptom)

        self.edit_note = QPlainTextEdit()
        self.edit_note.setPlaceholderText("연락처 또는 기타 메모")
        self.edit_note.setFixedHeight(60)
        form.addRow("비고", self.edit_note)

        form_wrap.addLayout(form)
        root.addWidget(card)

        self.status = QLabel("")
        self.status.setObjectName("muted")
        root.addWidget(self.status)

        btn_save = primary_button("저장")
        btn_save.clicked.connect(self._save)
        btn_open = secondary_button("작업 폴더 열기")
        from app import actions

        btn_open.clicked.connect(lambda: actions.open_workdir(lambda _m: None))
        root.addWidget(btn_save)
        root.addWidget(btn_open)
        root.addStretch(1)

        self._load_existing()

    def _load_existing(self) -> None:
        info = get_user_info()
        if not info.user_id and not info.issue_time:
            return
        self.edit_id.setText(info.user_id)
        self.edit_time.setText(info.issue_time)
        self.edit_domain.setText(info.vpn_domain)
        self.edit_os.setText(info.os_note)
        self.edit_symptom.setPlainText(info.symptom)
        self.edit_note.setPlainText(info.note)
        if info.saved_at:
            self.status.setText(f"마지막 저장: {info.saved_at}")

    def _save(self) -> None:
        info = UserCaseInfo(
            user_id=self.edit_id.text().strip(),
            issue_time=self.edit_time.text().strip(),
            vpn_domain=self.edit_domain.text().strip(),
            os_note=self.edit_os.text().strip(),
            symptom=self.edit_symptom.toPlainText().strip(),
            note=self.edit_note.toPlainText().strip(),
        )
        if not info.user_id:
            QMessageBox.warning(self, "입력 필요", "사용자 계정(ID)을 입력해 주세요.")
            self.edit_id.setFocus()
            return
        if not info.issue_time:
            QMessageBox.warning(
                self,
                "입력 필요",
                "이슈 발생 시간을 입력해 주세요.\n예: 2026-07-31 14:30",
            )
            self.edit_time.setFocus()
            return
        if not info.vpn_domain:
            QMessageBox.warning(self, "입력 필요", "VPN 접속 도메인을 입력해 주세요.")
            self.edit_domain.setFocus()
            return

        path = set_user_info(info)
        self.status.setText(f"저장 완료: {path}")
        QMessageBox.information(self, "저장 완료", "사용자 정보를 저장했습니다.")
        self.saved.emit()
