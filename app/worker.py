"""Background worker for running actions without freezing the UI."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from app import actions
from app.workflows import Step


class ActionWorker(QObject):
    log = pyqtSignal(str)
    step_started = pyqtSignal(int, str)
    step_finished = pyqtSignal(int, bool, str)
    finished = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    @pyqtSlot(object)
    def run_steps(self, jobs: object) -> None:
        """jobs: list[Step] or list[tuple[int, Step]] (ui_index, step)."""
        overall = False
        try:
            self._cancel = False
            assert isinstance(jobs, list)
            overall = True
            for i, item in enumerate(jobs):
                if self._cancel:
                    self.log.emit("중지되었습니다.")
                    overall = False
                    break
                if isinstance(item, tuple):
                    ui_index, step = item
                else:
                    ui_index, step = i, item
                assert isinstance(step, Step)
                self.step_started.emit(ui_index, step.title)
                self.log.emit(f"—— {step.title} ——")
                fn = actions.ACTIONS.get(step.action_id)
                if not fn:
                    self.log.emit("실행할 수 없는 작업입니다.")
                    self.step_finished.emit(ui_index, False, "unknown action")
                    overall = False
                    continue
                try:
                    result = fn(self.log.emit)
                    self.step_finished.emit(ui_index, result.ok, result.message)
                    if not result.ok:
                        overall = False
                except Exception as exc:  # noqa: BLE001
                    self.log.emit(f"오류: {exc}")
                    self.step_finished.emit(ui_index, False, str(exc))
                    overall = False
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"오류: {exc}")
            overall = False
        finally:
            self.finished.emit(overall)
