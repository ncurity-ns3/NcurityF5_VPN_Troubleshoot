"""Admin selectable diagnostics checklist."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.admin_checks import ADMIN_GROUPS, ADMIN_ITEMS, AdminItem
from app.widgets import info_row, page_header, primary_button, secondary_button


class AdminDiagnosePage(QWidget):
    run_selected = pyqtSignal(list)  # list[AdminItem]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._boxes: dict[str, QCheckBox] = {}
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(10)
        root.addWidget(
            page_header(
                "관리자 진단",
                "필요한 진단만 선택하거나 전체 항목을 점검할 수 있습니다.",
            )
        )

        top = QHBoxLayout()
        all_btn = secondary_button("전체 선택")
        all_btn.clicked.connect(self._select_all)
        none_btn = secondary_button("선택 해제")
        none_btn.clicked.connect(self._clear_all)
        run_btn = primary_button("선택 항목 실행")
        run_btn.clicked.connect(self._run)
        top.addWidget(all_btn)
        top.addWidget(none_btn)
        top.addStretch(1)
        top.addWidget(run_btn)
        root.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        host = QWidget()
        vl = QVBoxLayout(host)
        vl.setSpacing(10)
        for group in ADMIN_GROUPS:
            gtitle = QLabel(group)
            gtitle.setObjectName("cardTitle")
            vl.addWidget(gtitle)
            for item in ADMIN_ITEMS:
                if item.group != group:
                    continue
                cb = QCheckBox(item.title)
                cb.setChecked(True)
                if item.destructive:
                    cb.setText(f"{item.title}  (주의)")
                self._boxes[item.id] = cb
                vl.addWidget(cb)
            vl.addSpacing(6)
        vl.addStretch(1)
        scroll.setWidget(host)
        root.addWidget(scroll, stretch=2)

        root.addWidget(info_row("관리자 권한이 필요한 복구는 「개별 도구」·「이슈별 조치」에서도 실행할 수 있습니다."))

        self.log = QPlainTextEdit()
        self.log.setObjectName("logView")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(140)
        root.addWidget(self.log, stretch=1)

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy

    def _select_all(self) -> None:
        for cb in self._boxes.values():
            cb.setChecked(True)

    def _clear_all(self) -> None:
        for cb in self._boxes.values():
            cb.setChecked(False)

    def _run(self) -> None:
        if self._busy:
            return
        selected: list[AdminItem] = []
        for item in ADMIN_ITEMS:
            cb = self._boxes.get(item.id)
            if cb and cb.isChecked():
                selected.append(item)
        if not selected:
            self.append_log("선택된 항목이 없습니다.")
            return
        self.run_selected.emit(selected)
