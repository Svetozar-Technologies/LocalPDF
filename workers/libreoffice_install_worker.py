"""Background worker for LibreOffice download and installation."""

from PyQt6.QtCore import QThread, pyqtSignal

from core.libreoffice_installer import LibreOfficeInstaller, InstallResult, DownloadProgress
from core.utils import format_file_size


class LibreOfficeInstallWorker(QThread):
    """Downloads and installs LibreOffice in a background thread."""

    progress = pyqtSignal(int, int, str)  # (current, total, message)
    finished = pyqtSignal(object)  # InstallResult
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False
        self._installer = LibreOfficeInstaller()

    def run(self):
        try:
            result = self._installer.download_and_install(
                on_progress=self._on_progress,
                is_cancelled=self._is_cancelled,
            )
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(f"Unexpected error: {str(e)}")

    def cancel(self):
        self._cancelled = True

    def _is_cancelled(self) -> bool:
        return self._cancelled

    def _on_progress(self, prog: DownloadProgress):
        if self._cancelled:
            return

        if prog.phase == "downloading":
            if prog.bytes_total > 0:
                pct = int(prog.bytes_downloaded / prog.bytes_total * 80)
                downloaded = format_file_size(prog.bytes_downloaded)
                total = format_file_size(prog.bytes_total)
            else:
                pct = 0
                downloaded = format_file_size(prog.bytes_downloaded)
                total = "?"

            speed = format_file_size(int(prog.speed_bps)) + "/s" if prog.speed_bps > 0 else ""
            msg = f"Downloading LibreOffice... {downloaded} / {total}"
            if speed:
                msg += f"  ({speed})"

        elif prog.phase == "installing":
            pct = 85
            msg = "Installing LibreOffice..."

        elif prog.phase == "verifying":
            pct = 95
            msg = "Verifying installation..."

        else:
            pct = 0
            msg = prog.phase

        self.progress.emit(pct, 100, msg)
