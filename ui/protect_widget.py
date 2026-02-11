"""PDF Protect / Unlock tab widget."""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QScrollArea, QGroupBox, QRadioButton, QButtonGroup, QLineEdit, QCheckBox,
)
from PyQt6.QtCore import Qt

from ui.components.drop_zone import DropZone
from ui.components.progress_widget import ProgressWidget
from ui.components.result_card import ResultCard
from workers.protect_worker import ProtectWorker
from core.protector import ProtectConfig, UnlockConfig
from core.utils import validate_pdf, get_output_path, format_file_size


class ProtectWidget(QWidget):
    """PDF Protect/Unlock tab: add or remove passwords from PDFs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = ""
        self._worker: ProtectWorker = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Protect / Unlock PDF")
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("Add password protection or remove passwords from PDFs. 100% local — your passwords never leave this computer.")
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Drop zone (accepts any PDF, including encrypted for unlock mode)
        self._drop_zone = DropZone(
            accepted_extensions=[".pdf"],
            placeholder_text="Drop PDF here or click to browse",
        )
        layout.addWidget(self._drop_zone)

        # Mode selection
        mode_group = QGroupBox("Mode")
        mode_layout = QVBoxLayout(mode_group)

        self._mode_group = QButtonGroup(self)
        self._protect_radio = QRadioButton("Protect — Add password to PDF")
        self._unlock_radio = QRadioButton("Unlock — Remove password from PDF")
        self._protect_radio.setChecked(True)
        self._mode_group.addButton(self._protect_radio, 0)
        self._mode_group.addButton(self._unlock_radio, 1)
        mode_layout.addWidget(self._protect_radio)
        mode_layout.addWidget(self._unlock_radio)

        layout.addWidget(mode_group)

        # Protect options
        self._protect_options = QGroupBox("Protection Settings")
        protect_layout = QVBoxLayout(self._protect_options)

        # User password
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Open Password:"))
        self._user_pw_input = QLineEdit()
        self._user_pw_input.setPlaceholderText("Password required to open the PDF")
        self._user_pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        row1.addWidget(self._user_pw_input)
        protect_layout.addLayout(row1)

        # Owner password
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Owner Password:"))
        self._owner_pw_input = QLineEdit()
        self._owner_pw_input.setPlaceholderText("(Optional) Password for editing permissions")
        self._owner_pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        row2.addWidget(self._owner_pw_input)
        protect_layout.addLayout(row2)

        # Permissions
        perm_label = QLabel("Permissions (when owner password is set):")
        perm_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        protect_layout.addWidget(perm_label)

        self._allow_print = QCheckBox("Allow printing")
        self._allow_print.setChecked(True)
        protect_layout.addWidget(self._allow_print)

        self._allow_copy = QCheckBox("Allow copying text")
        protect_layout.addWidget(self._allow_copy)

        self._allow_modify = QCheckBox("Allow modifying")
        protect_layout.addWidget(self._allow_modify)

        self._allow_annotate = QCheckBox("Allow annotating")
        self._allow_annotate.setChecked(True)
        protect_layout.addWidget(self._allow_annotate)

        layout.addWidget(self._protect_options)

        # Unlock options
        self._unlock_options = QGroupBox("Unlock Settings")
        unlock_layout = QVBoxLayout(self._unlock_options)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Password:"))
        self._unlock_pw_input = QLineEdit()
        self._unlock_pw_input.setPlaceholderText("Enter the PDF password")
        self._unlock_pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        row3.addWidget(self._unlock_pw_input)
        unlock_layout.addLayout(row3)

        self._unlock_options.hide()
        layout.addWidget(self._unlock_options)

        # Action button
        self._action_btn = QPushButton("Protect PDF")
        self._action_btn.setObjectName("primaryButton")
        self._action_btn.setEnabled(False)
        layout.addWidget(self._action_btn)

        # Progress
        self._progress = ProgressWidget()
        layout.addWidget(self._progress)

        # Result
        self._result_card = ResultCard()
        layout.addWidget(self._result_card)

        layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _connect_signals(self):
        self._drop_zone.file_selected.connect(self._on_file_selected)
        self._drop_zone.file_removed.connect(self._on_file_removed)
        self._mode_group.buttonClicked.connect(self._on_mode_changed)
        self._action_btn.clicked.connect(self._on_action_clicked)
        self._progress.cancel_clicked.connect(self._on_cancel_clicked)
        self._result_card.compress_another.connect(self._on_another)

    def _on_mode_changed(self):
        if self._protect_radio.isChecked():
            self._protect_options.show()
            self._unlock_options.hide()
            self._action_btn.setText("Protect PDF")
        else:
            self._protect_options.hide()
            self._unlock_options.show()
            self._action_btn.setText("Unlock PDF")

    def _on_file_selected(self, file_path: str):
        # For unlock mode, we accept encrypted PDFs too — skip validate_pdf
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Invalid File", "File not found.")
            self._drop_zone.reset()
            return

        ext = os.path.splitext(file_path)[1].lower()
        if ext != ".pdf":
            QMessageBox.warning(self, "Invalid File", "Please select a PDF file.")
            self._drop_zone.reset()
            return

        self._current_file = file_path
        self._action_btn.setEnabled(True)
        self._result_card.reset()
        self._progress.reset()

    def _on_file_removed(self):
        self._current_file = ""
        self._action_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.reset()

    def _on_action_clicked(self):
        if not self._current_file:
            return

        if self._protect_radio.isChecked():
            self._do_protect()
        else:
            self._do_unlock()

    def _do_protect(self):
        user_pw = self._user_pw_input.text()
        owner_pw = self._owner_pw_input.text()

        if not user_pw and not owner_pw:
            QMessageBox.warning(
                self, "No Password",
                "Please enter at least one password (open or owner).",
            )
            return

        output_path = get_output_path(self._current_file, suffix="_protected")

        config = ProtectConfig(
            input_path=self._current_file,
            output_path=output_path,
            user_password=user_pw,
            owner_password=owner_pw,
            allow_print=self._allow_print.isChecked(),
            allow_copy=self._allow_copy.isChecked(),
            allow_modify=self._allow_modify.isChecked(),
            allow_annotate=self._allow_annotate.isChecked(),
        )

        self._start_worker("protect", protect_config=config)

    def _do_unlock(self):
        password = self._unlock_pw_input.text()
        if not password:
            QMessageBox.warning(self, "No Password", "Please enter the PDF password.")
            return

        output_path = get_output_path(self._current_file, suffix="_unlocked")

        config = UnlockConfig(
            input_path=self._current_file,
            output_path=output_path,
            password=password,
        )

        self._start_worker("unlock", unlock_config=config)

    def _start_worker(self, mode, protect_config=None, unlock_config=None):
        self._action_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.start()

        self._worker = ProtectWorker(
            mode=mode,
            protect_config=protect_config,
            unlock_config=unlock_config,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, step: int, total: int, message: str):
        self._progress.update_progress(step, total, message)

    def _on_finished(self, result):
        self._progress.finish()
        self._action_btn.setEnabled(True)
        self._worker = None

        if result.success:
            mode = "Protected" if self._protect_radio.isChecked() else "Unlocked"
            self._result_card.show_simple_result(
                result.output_path,
                title=f"{mode}! {result.page_count} pages",
            )
        else:
            QMessageBox.critical(self, "Error", result.error_message or "Operation failed.")
            self._progress.reset()

    def _on_error(self, error_msg: str):
        self._progress.reset()
        self._action_btn.setEnabled(True)
        self._worker = None
        QMessageBox.critical(self, "Error", error_msg)

    def _on_cancel_clicked(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(5000)
            self._worker = None
        self._progress.reset()
        self._action_btn.setEnabled(bool(self._current_file))

    def _on_another(self):
        self._drop_zone.reset()
        self._result_card.reset()
        self._progress.reset()
        self._user_pw_input.clear()
        self._owner_pw_input.clear()
        self._unlock_pw_input.clear()
        self._current_file = ""
        self._action_btn.setEnabled(False)

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(5000)
