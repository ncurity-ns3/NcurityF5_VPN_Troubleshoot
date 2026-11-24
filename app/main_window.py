"""Main window — sidebar + stacked pages (original UI + symptom diagnosis)."""

from __future__ import annotations

from functools import partial

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, __version__
from app.admin_checks import AdminItem
from app.paths import resource_path
from app.pages import (
    AdminDiagnosePage,
    GuidePage,
    HomePage,
    IssueDetailPage,
    IssueHubPage,
    ToolsPage,
    UserInfoPage,
    UserProgressPage,
    UserResultPage,
)
from app.user_info import get_user_info
from app.user_symptoms import get_symptom
from app.worker import ActionWorker
from app.workflows import Step


NAV_ITEMS = [
    ("홈", "home"),
    ("사용자 정보", "user_info"),
    ("이슈별 조치", "issues"),
    ("개별 도구", "tools"),
    ("관리자 진단", "admin_diag"),
    ("가이드", "guide"),
]


class _HealthProbe(QObject):
    finished = pyqtSignal(bool, str, list)

    def run(self) -> None:
        from app.health import check_edge_client_health

        result = check_edge_client_health()
        self.finished.emit(result.healthy, result.summary, list(result.reasons))


class _DiagnoseWorker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self, symptom_id: str) -> None:
        from app.diagnose import run_diagnosis

        sym = get_symptom(symptom_id)
        if not sym:
            self.finished.emit(None)
            return
        self.log.emit(f"{sym.title} 점검을 시작합니다…")

        def _log(msg: str) -> None:
            if not self._cancel:
                self.log.emit(msg)

        report = run_diagnosis(sym.id, sym.title, sym.check_ids, _log)
        if self._cancel:
            self.log.emit("중지되었습니다.")
        self.finished.emit(report)


class _SupportPackWorker(QObject):
    """Save diagnosis text + collect engineer materials, then open folder."""

    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self) -> None:
        super().__init__()
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self, report: object) -> None:
        from app.actions import collect_support_pack
        from app.diagnose import save_diagnosis_report
        from app.paths import troubleshoot_dir

        def _log(msg: str) -> None:
            if not self._cancel:
                self.log.emit(msg)

        try:
            if report is not None:
                path = save_diagnosis_report(report, _log)  # type: ignore[arg-type]
                _log(f"점검 요약 저장: {path.name}")
            if self._cancel:
                self.finished.emit(False, "")
                return
            result = collect_support_pack(_log, include_f5_report=True)
            self.finished.emit(result.ok, str(troubleshoot_dir()))
        except Exception as exc:  # noqa: BLE001
            _log(f"오류: {exc}")
            self.finished.emit(False, "")


class _AdminMixedWorker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self, items: list) -> None:
        from app import actions
        from app.diagnose import CHECKS

        overall = True
        for item in items:
            if self._cancel:
                self.log.emit("중지되었습니다.")
                overall = False
                break
            assert isinstance(item, AdminItem)
            self.log.emit(f"—— {item.title} ——")
            try:
                if item.kind == "diagnose":
                    fn = CHECKS.get(item.target)
                    if not fn:
                        self.log.emit("알 수 없는 점검입니다.")
                        overall = False
                        continue
                    result = fn(self.log.emit)
                    self.log.emit(f"[{result.status}] {result.user_label}: {result.user_detail}")
                    if result.tech_detail:
                        self.log.emit(f"  tech: {result.tech_detail}")
                    if result.status == "fail":
                        overall = False
                else:
                    fn = actions.ACTIONS.get(item.target)
                    if not fn:
                        self.log.emit("알 수 없는 작업입니다.")
                        overall = False
                        continue
                    r = fn(self.log.emit)
                    if not r.ok:
                        overall = False
            except Exception as exc:  # noqa: BLE001
                self.log.emit(f"오류: {exc}")
                overall = False
        self.finished.emit(overall)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(1100, 760)
        icon = resource_path("branding", "app_icon.ico")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))

        self._thread: QThread | None = None
        self._worker: ActionWorker | None = None
        self._diag_thread: QThread | None = None
        self._diag_worker: _DiagnoseWorker | None = None
        self._pack_thread: QThread | None = None
        self._pack_worker: _SupportPackWorker | None = None
        self._admin_thread: QThread | None = None
        self._admin_worker: _AdminMixedWorker | None = None
        self._health_thread: QThread | None = None
        self._health_probe: _HealthProbe | None = None
        self._active_log_target = "issue"
        self._busy_token = 0
        self._last_report = None
        self._last_symptom_id = ""

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_nav())
        self.stack = QStackedWidget()
        self.stack.setObjectName("contentHost")
        layout.addWidget(self.stack, stretch=1)

        self.home = HomePage()
        self.user_info = UserInfoPage()
        self.issues = IssueHubPage()
        self.issue_detail = IssueDetailPage()
        self.tools = ToolsPage()
        self.admin_diag = AdminDiagnosePage()
        self.guide = GuidePage()
        self.user_progress = UserProgressPage()
        self.user_result = UserResultPage()

        # 0 home, 1 user_info, 2 issues, 3 issue_detail, 4 tools, 5 admin_diag, 6 guide,
        # 7 symptom progress, 8 symptom result
        for w in (
            self.home,
            self.user_info,
            self.issues,
            self.issue_detail,
            self.tools,
            self.admin_diag,
            self.guide,
            self.user_progress,
            self.user_result,
        ):
            self.stack.addWidget(w)

        self.home.open_user_info.connect(lambda: self._goto("user_info"))
        self.home.open_issues.connect(self._goto_issues_gated)
        self.home.open_tools.connect(self._goto_tools_gated)
        self.home.open_temp_actions.connect(self._goto_tools_gated)
        self.home.open_reinstall.connect(self._goto_tools_gated)
        self.home.open_guide.connect(lambda: self._goto("guide"))
        self.home.refresh_health.connect(self._start_health_check)
        self.home.run_analyze.connect(self._run_analyze_from_home)
        self.issues.run_symptom.connect(self._start_user_diagnosis)
        self.issues.save_blank_hint.connect(self._open_workdir_from_issues)
        self.issue_detail.back.connect(self._back_to_issue_hub)
        self.issue_detail.run_steps.connect(self._run_from_issue)
        self.issue_detail.btn_stop.clicked.connect(self._cancel)
        self.tools.run_steps.connect(self._run_from_tools)
        self.admin_diag.run_selected.connect(self._run_admin_selected)
        self.user_info.saved.connect(self._on_user_info_saved)
        self.user_progress.cancel.connect(self._cancel_user_progress)
        self.user_result.back_home.connect(self._back_to_issue_hub)
        self.user_result.recheck.connect(self._recheck_last)
        self.user_result.save_report.connect(self._save_last_report)
        self.user_result.apply_fix.connect(self._apply_user_fix)

        status = QStatusBar()
        status.showMessage("관리자 권한으로 실행 중")
        self.setStatusBar(status)

        self.nav_list.setCurrentRow(0)
        self._refresh_user_info_status()
        self.home.set_health_pending()
        QTimer.singleShot(200, self._start_health_check)

    def _build_nav(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("navFrame")
        frame.setFixedWidth(220)
        v = QVBoxLayout(frame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QFrame()
        header.setObjectName("navHeader")
        hl = QVBoxLayout(header)
        title = QLabel("F5 SSL VPN")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0260EA;")
        hl.addWidget(title)
        sub = QLabel("Troubleshoot Tool")
        sub.setObjectName("muted")
        hl.addWidget(sub)
        v.addWidget(header)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        for label, _key in NAV_ITEMS:
            QListWidgetItem(label, self.nav_list)
        self.nav_list.currentRowChanged.connect(self._on_nav)
        v.addWidget(self.nav_list, stretch=1)
        return frame

    def _stack_index(self, key: str) -> int:
        return {
            "home": 0,
            "user_info": 1,
            "issues": 2,
            "issue_detail": 3,
            "tools": 4,
            "admin_diag": 5,
            "guide": 6,
            "symptom_progress": 7,
            "symptom_result": 8,
        }[key]

    def _on_nav(self, row: int) -> None:
        if row < 0 or row >= len(NAV_ITEMS):
            return
        key = NAV_ITEMS[row][1]
        if key in ("issues", "tools") and not self._ensure_user_info():
            self.nav_list.blockSignals(True)
            self.nav_list.setCurrentRow(next(i for i, (_, k) in enumerate(NAV_ITEMS) if k == "user_info"))
            self.nav_list.blockSignals(False)
            self.stack.setCurrentIndex(self._stack_index("user_info"))
            return
        self.stack.setCurrentIndex(self._stack_index(key))

    def _goto(self, key: str) -> None:
        nav_idx = next(i for i, (_label, k) in enumerate(NAV_ITEMS) if k == key)
        if self.nav_list.currentRow() == nav_idx:
            self._on_nav(nav_idx)
        else:
            self.nav_list.setCurrentRow(nav_idx)

    def _ensure_user_info(self) -> bool:
        if get_user_info().is_complete():
            return True
        QMessageBox.information(
            self,
            "사용자 정보 필요",
            "조치를 진행하려면 먼저 [사용자 정보]에서\n"
            "계정·이슈 발생 시간·VPN 접속 도메인을 입력해 주세요.",
        )
        self._goto("user_info")
        return False

    def _goto_issues_gated(self) -> None:
        if self._ensure_user_info():
            self._goto("issues")

    def _goto_tools_gated(self) -> None:
        if self._ensure_user_info():
            self._goto("tools")

    def _back_to_issue_hub(self) -> None:
        if not self._ensure_user_info():
            return
        self.stack.setCurrentIndex(self._stack_index("issues"))
        self.nav_list.blockSignals(True)
        self.nav_list.setCurrentRow(next(i for i, (_, k) in enumerate(NAV_ITEMS) if k == "issues"))
        self.nav_list.blockSignals(False)

    def _open_workdir_from_issues(self) -> None:
        from app import actions

        actions.open_workdir(lambda m: self.statusBar().showMessage(m[:120]))

    def _on_user_info_saved(self) -> None:
        self._refresh_user_info_status()

    def _refresh_user_info_status(self) -> None:
        info = get_user_info()
        if info.is_complete():
            self.statusBar().showMessage(
                f"{info.user_id} · {info.issue_time} · {info.vpn_domain}"
            )
        else:
            self.statusBar().showMessage("사용자 정보를 입력해 주세요")

    # ----- symptom diagnosis (이슈별 조치) -----
    def _start_user_diagnosis(self, symptom_id: str) -> None:
        if not self._ensure_user_info():
            return
        if self._diag_thread and self._diag_thread.isRunning():
            return
        self._last_symptom_id = symptom_id
        self.stack.setCurrentIndex(self._stack_index("symptom_progress"))
        self.nav_list.blockSignals(True)
        self.nav_list.setCurrentRow(next(i for i, (_, k) in enumerate(NAV_ITEMS) if k == "issues"))
        self.nav_list.blockSignals(False)
        self.user_progress.set_status("점검을 준비하고 있습니다…")

        self._diag_thread = QThread(self)
        self._diag_worker = _DiagnoseWorker()
        self._diag_worker.moveToThread(self._diag_thread)
        self._diag_thread.started.connect(partial(self._diag_worker.run, symptom_id))
        self._diag_worker.log.connect(self.user_progress.set_status)
        self._diag_worker.finished.connect(self._on_user_diagnosis_done)
        self._diag_worker.finished.connect(self._diag_thread.quit)
        self._diag_thread.finished.connect(self._cleanup_diag_thread)
        self._diag_thread.start()

    def _cancel_diagnosis(self) -> None:
        if self._diag_worker:
            self._diag_worker.request_cancel()

    def _on_user_diagnosis_done(self, report: object) -> None:
        if report is None:
            self._back_to_issue_hub()
            return
        self._last_report = report
        self.user_result.show_report(report)  # type: ignore[arg-type]
        self.stack.setCurrentIndex(self._stack_index("symptom_result"))
        self.statusBar().showMessage(report.headline())  # type: ignore[union-attr]

    def _cleanup_diag_thread(self) -> None:
        if self._diag_worker:
            self._diag_worker.deleteLater()
            self._diag_worker = None
        if self._diag_thread:
            self._diag_thread.deleteLater()
            self._diag_thread = None

    def _recheck_last(self) -> None:
        if self._last_symptom_id:
            self._start_user_diagnosis(self._last_symptom_id)

    def _save_last_report(self) -> None:
        if not self._last_report:
            return
        if self._pack_thread and self._pack_thread.isRunning():
            return
        reply = QMessageBox.question(
            self,
            "결과 저장",
            "점검 요약과 함께 환경 정보·이벤트 로그·F5 진단 리포트를 수집합니다.\n"
            "F5 리포트는 몇 분 걸릴 수 있습니다. 계속할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.stack.setCurrentIndex(self._stack_index("symptom_progress"))
        self.user_progress.set_status("지원 자료를 수집하고 있습니다…")
        self._pack_thread = QThread(self)
        self._pack_worker = _SupportPackWorker()
        self._pack_worker.moveToThread(self._pack_thread)
        self._pack_thread.started.connect(partial(self._pack_worker.run, self._last_report))
        self._pack_worker.log.connect(self.user_progress.set_status)
        self._pack_worker.finished.connect(self._on_support_pack_done)
        self._pack_worker.finished.connect(self._pack_thread.quit)
        self._pack_thread.finished.connect(self._cleanup_pack_thread)
        self._pack_thread.start()

    def _cancel_user_progress(self) -> None:
        if self._pack_worker:
            self._pack_worker.request_cancel()
        if self._diag_worker:
            self._diag_worker.request_cancel()

    def _on_support_pack_done(self, ok: bool, folder: str) -> None:
        self.stack.setCurrentIndex(self._stack_index("symptom_result"))
        if folder:
            QMessageBox.information(
                self,
                "저장 완료",
                "자료를 저장했습니다. 작업 폴더를 열었습니다.\n\n"
                f"{folder}\n\n"
                "이 폴더를 담당자에게 전달해 주세요."
                + ("" if ok else "\n\n일부 항목 수집에 실패했을 수 있습니다."),
            )
            self.statusBar().showMessage(f"저장 폴더: {folder}")
        else:
            QMessageBox.warning(self, "저장", "자료 수집이 완료되지 않았습니다.")

    def _cleanup_pack_thread(self) -> None:
        if self._pack_worker:
            self._pack_worker.deleteLater()
            self._pack_worker = None
        if self._pack_thread:
            self._pack_thread.deleteLater()
            self._pack_thread = None

    def _apply_user_fix(self, action_id: str) -> None:
        if not self._ensure_user_info():
            return
        from app import actions
        from app.diagnose import safe_restart_edge_client

        logs: list[str] = []

        def _log(m: str) -> None:
            logs.append(m)
            self.statusBar().showMessage(m[:120])

        if action_id == "install_sectigo":
            reply = QMessageBox.question(
                self,
                "인증서 설치",
                "Sectigo 코드 서명 인증서(루트/중간)를 설치할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            result = actions.install_root_certs(_log)
            QMessageBox.information(
                self,
                "인증서 설치",
                "\n".join(logs[-12:]) or ("완료" if result.ok else "실패"),
            )
        elif action_id == "restart_client":
            ok = safe_restart_edge_client(_log)
            QMessageBox.information(
                self,
                "VPN 다시 실행",
                "\n".join(logs) if logs else ("완료" if ok else "실패"),
            )
        elif action_id == "launch_installer":
            reply = QMessageBox.question(
                self,
                "설치 파일 실행",
                "승인된 Edge Client 설치 파일을 실행할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            installer = actions.find_edge_installer()
            if installer is None:
                QMessageBox.warning(
                    self,
                    "설치 파일 없음",
                    "resources/installers 폴더에 설치 파일이 없습니다.\n관리자에게 문의해 주세요.",
                )
                return
            result = actions.ACTIONS["open_workdir"](_log)  # ensure folder
            from app.winproc import popen_silent

            try:
                popen_silent([str(installer)], cwd=str(installer.parent))
                _log(f"설치 실행: {installer.name}")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "실행 실패", str(exc))
                return
            QMessageBox.information(self, "설치", "\n".join(logs[-8:]))
        else:
            QMessageBox.information(self, "안내", "이 항목은 관리자 확인이 필요합니다. 결과를 저장해 주세요.")
            return

        if self._last_symptom_id:
            reply = QMessageBox.question(
                self,
                "다시 점검",
                "조치 후 같은 항목을 다시 점검할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._recheck_last()

    # ----- health -----
    def _start_health_check(self) -> None:
        if self._health_thread and self._health_thread.isRunning():
            return
        self.home.set_health_pending()
        self._health_thread = QThread(self)
        self._health_probe = _HealthProbe()
        self._health_probe.moveToThread(self._health_thread)
        self._health_thread.started.connect(self._health_probe.run)
        self._health_probe.finished.connect(self._on_health_done)
        self._health_probe.finished.connect(self._health_thread.quit)
        self._health_thread.finished.connect(self._cleanup_health_thread)
        self._health_thread.start()

    def _on_health_done(self, healthy: bool, summary: str, reasons: list) -> None:
        self.home.set_health(healthy, summary, reasons)
        self.statusBar().showMessage(f"설치 상태: {summary}")

    def _cleanup_health_thread(self) -> None:
        if self._health_probe:
            self._health_probe.deleteLater()
            self._health_probe = None
        if self._health_thread:
            self._health_thread.deleteLater()
            self._health_thread = None

    # ----- workers -----
    def _run_analyze_from_home(self) -> None:
        if not self._ensure_user_info():
            return
        self._goto("tools")
        self._active_log_target = "tools"
        self._start_worker(
            [Step("analyze_environment", "단말기 환경 분석", "환경 정보를 수집합니다")]
        )

    def _run_admin_selected(self, items: list) -> None:
        if self._admin_thread and self._admin_thread.isRunning():
            return
        self.admin_diag.set_busy(True)
        self.admin_diag.append_log("선택 항목 점검을 시작합니다.")
        self._admin_thread = QThread(self)
        self._admin_worker = _AdminMixedWorker()
        self._admin_worker.moveToThread(self._admin_thread)
        self._admin_thread.started.connect(partial(self._admin_worker.run, items))
        self._admin_worker.log.connect(self.admin_diag.append_log)
        self._admin_worker.finished.connect(self._on_admin_mixed_done)
        self._admin_worker.finished.connect(self._admin_thread.quit)
        self._admin_thread.finished.connect(self._cleanup_admin_thread)
        self._admin_thread.start()

    def _on_admin_mixed_done(self, overall: bool) -> None:
        self.admin_diag.set_busy(False)
        self.admin_diag.append_log(
            "완료되었습니다." if overall else "완료되었습니다. 일부 항목을 확인해 주세요."
        )
        self._start_health_check()

    def _cleanup_admin_thread(self) -> None:
        if self._admin_worker:
            self._admin_worker.deleteLater()
            self._admin_worker = None
        if self._admin_thread:
            self._admin_thread.deleteLater()
            self._admin_thread = None

    def _run_from_issue(self, steps: list) -> None:
        if not self._ensure_user_info():
            return
        self._active_log_target = "issue"
        self._start_worker(steps)

    def _run_from_tools(self, steps: list) -> None:
        if not self._ensure_user_info():
            return
        self._active_log_target = "tools"
        self._start_worker(steps)

    def _start_worker(self, steps: list[Step]) -> None:
        if self._thread and self._thread.isRunning():
            return
        self._set_busy(True)
        self._append_log("작업을 시작합니다.")
        self._busy_token += 1
        token = self._busy_token
        QTimer.singleShot(900_000, lambda t=token: self._clear_busy_if(t))

        self._thread = QThread(self)
        self._worker = ActionWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(partial(self._worker.run_steps, steps))
        self._worker.log.connect(self._append_log)
        self._worker.step_started.connect(self._on_step_started)
        self._worker.step_finished.connect(self._on_step_finished)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _cancel(self) -> None:
        if self._worker:
            self._worker.request_cancel()
            self._append_log("중지를 요청했습니다.")

    def _append_log(self, text: str) -> None:
        if self._active_log_target == "tools":
            self.tools.append_log(text)
        else:
            self.issue_detail.append_log(text)
        self.statusBar().showMessage(text[:120])

    def _on_step_started(self, index: int, title: str) -> None:
        if self._active_log_target == "issue":
            self.issue_detail.mark_step(index, None)

    def _on_step_finished(self, index: int, ok: bool, _msg: str) -> None:
        if self._active_log_target == "issue":
            self.issue_detail.mark_step(index, ok)

    def _on_finished(self, overall: bool) -> None:
        self._set_busy(False)
        self._append_log(
            "작업이 완료되었습니다." if overall else "작업이 끝났습니다. 일부 항목을 확인해 주세요."
        )
        self._start_health_check()

    def _clear_busy_if(self, token: int) -> None:
        if token == self._busy_token:
            self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.issue_detail.set_busy(busy)
        self.tools.set_busy(busy)
        self.admin_diag.set_busy(busy)

    def _cleanup_thread(self) -> None:
        self._set_busy(False)
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None
