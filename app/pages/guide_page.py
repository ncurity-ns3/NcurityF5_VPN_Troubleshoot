"""Guide page."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app import actions
from app.widgets import info_row, make_card, page_header, primary_button, secondary_button


class GuidePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        root.addWidget(
            page_header(
                "이용 가이드",
                "증상별 대응 요약과 상세 가이드 문서입니다.",
            )
        )

        card = make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(8)
        t = QLabel("주요 이슈")
        t.setObjectName("cardTitle")
        cl.addWidget(t)
        for line in [
            "초기화 중 — Miniport·서비스 점검 후 Edge Client 재설치",
            "설치 실패 — 인증서 확인 후 삭제·재부팅·재설치",
            "해지 서버 오류 — 인증서 해지 확인 해제",
            "연결 장치 없음 — 구성 요소 제거 및 서비스 확인",
            "VPN 후 인터넷 불가 — 환경 정보·F5 로그 수집 후 전달",
            "터널 미생성 — 시스템·네트워크 검사 후 재부팅",
            "서버 연결 실패 — TLS 1.2 사용 확인",
        ]:
            cl.addWidget(info_row(f"• {line}"))
        root.addWidget(card)

        b1 = primary_button("가이드 문서 열기")
        b1.clicked.connect(lambda: actions.open_guide_pdf(lambda _m: None))
        b2 = secondary_button("작업 폴더 열기")
        b2.clicked.connect(lambda: actions.open_workdir(lambda _m: None))
        root.addWidget(b1)
        root.addWidget(b2)
        root.addStretch(1)
