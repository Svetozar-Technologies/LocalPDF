"""Modal dialog for downloading and installing LibreOffice."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from workers.libreoffice_install_worker import LibreOfficeInstallWorker
from core.utils import get_libreoffice_install_instructions
from i18n import t


class LibreOfficeInstallDialog(QDialog):
    """Dialog that downloads and installs LibreOffice automatically."""

    install_completed = pyqtSignal(str)  # soffice path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(t("lo_install.title"))
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title = QLabel(t("lo_install.required"))
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        # Info
        info = QLabel(t("lo_install.info"))
        info.setWordWrap(True)
        info.setProperty("class", "textSecondary")
        layout.addWidget(info)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setMinimumHeight(24)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setProperty("class", "textCaption")
        self._status_label.hide()
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()

        self._manual_btn = QPushButton(t("lo_install.manual"))
        self._manual_btn.setProperty("class", "secondaryButton")
        self._manual_btn.clicked.connect(self._show_manual_instructions)
        btn_row.addWidget(self._manual_btn)

        btn_row.addStretch()

        self._cancel_btn = QPushButton(t("lo_install.not_now"))
        self._cancel_btn.setProperty("class", "secondaryButton")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        self._install_btn = QPushButton(t("lo_install.download"))
        self._install_btn.setObjectName("primaryButton")
        self._install_btn.clicked.connect(self._start_install)
        btn_row.addWidget(self._install_btn)

        layout.addLayout(btn_row)

    def _start_install(self):
        self._install_btn.setEnabled(False)
        self._cancel_btn.setText(t("common.cancel"))
        self._manual_btn.hide()
        self._progress_bar.show()
        self._progress_bar.setValue(0)
        self._status_label.show()
        self._status_label.setText(t("lo_install.starting"))

        self._worker = LibreOfficeInstallWorker()
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int, message: str):
        if total > 0:
            self._progress_bar.setValue(current)
        self._status_label.setText(message)

    def _on_finished(self, result):
        self._worker = None

        if result.success:
            self._progress_bar.setValue(100)
            self._status_label.setText(t("lo_install.success_msg"))
            self.install_completed.emit(result.soffice_path)
            QMessageBox.information(
                self, t("lo_install.success_title"),
                t("lo_install.success_detail"),
            )
            self.accept()
        else:
            self._progress_bar.setValue(0)
            self._progress_bar.hide()
            self._status_label.setText(result.error_message)
            self._install_btn.setEnabled(True)
            self._install_btn.setText(t("lo_install.retry"))
            self._cancel_btn.setText(t("common.close"))
            self._manual_btn.show()
            QMessageBox.warning(
                self, t("lo_install.failed_title"),
                t("lo_install.failed_msg", error=result.error_message),
            )

    def _on_error(self, error_msg: str):
        self._worker = None
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        self._status_label.setText(error_msg)
        self._install_btn.setEnabled(True)
        self._install_btn.setText(t("lo_install.retry"))
        self._cancel_btn.setText(t("common.close"))
        self._manual_btn.show()
        QMessageBox.warning(self, t("lo_install.failed_title"), error_msg)

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(5000)
            self._worker = None
        self.reject()

    def _show_manual_instructions(self):
        instructions = get_libreoffice_install_instructions()
        QMessageBox.information(self, t("lo_install.manual_title"), instructions)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(5000)
        event.accept()
