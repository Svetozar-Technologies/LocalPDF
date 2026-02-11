"""Background worker for PDF Protect/Unlock operations."""

from PyQt6.QtCore import QThread, pyqtSignal

from core.protector import PDFProtector, ProtectConfig, UnlockConfig, ProtectResult


class ProtectWorker(QThread):
    """Runs PDF protect/unlock in a background thread."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        mode: str,  # "protect" or "unlock"
        protect_config: ProtectConfig = None,
        unlock_config: UnlockConfig = None,
        parent=None,
    ):
        super().__init__(parent)
        self._mode = mode
        self._protect_config = protect_config
        self._unlock_config = unlock_config
        self._cancelled = False
        self._protector = PDFProtector()

    def run(self):
        try:
            if self._mode == "protect" and self._protect_config:
                result = self._protector.protect(
                    self._protect_config,
                    on_progress=self._on_progress,
                    is_cancelled=self._is_cancelled,
                )
            elif self._mode == "unlock" and self._unlock_config:
                result = self._protector.unlock(
                    self._unlock_config,
                    on_progress=self._on_progress,
                    is_cancelled=self._is_cancelled,
                )
            else:
                result = ProtectResult(success=False, error_message="Invalid configuration.")

            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(f"Unexpected error: {str(e)}")

    def cancel(self):
        self._cancelled = True

    def _on_progress(self, step: int, total: int, message: str):
        if not self._cancelled:
            self.progress.emit(step, total, message)

    def _is_cancelled(self) -> bool:
        return self._cancelled
