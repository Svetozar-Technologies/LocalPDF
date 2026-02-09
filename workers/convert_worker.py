"""QThread worker for PPT to PDF conversion."""

import os
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal
from core.converter import PPTConverter, ConversionResult
from core.branded_pdf import BrandedPDFGenerator, BrandingConfig, BrandedResult


class ConvertWorker(QThread):
    """Worker thread for PPT->PDF conversion, optionally followed by branding."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        branded: bool = False,
        branding_config: BrandingConfig = None,
        parent=None,
    ):
        super().__init__(parent)
        self._input_path = input_path
        self._output_path = output_path
        self._branded = branded
        self._branding_config = branding_config
        self._cancelled = False

    def run(self):
        try:
            converter = PPTConverter()

            # Step 1: Convert PPT to plain PDF
            if self._branded:
                # Use temp file for intermediate PDF
                tmp_fd, tmp_pdf = tempfile.mkstemp(suffix=".pdf", prefix="localpdf_")
                os.close(tmp_fd)
                convert_output = tmp_pdf
            else:
                convert_output = self._output_path

            self.progress.emit(5, 100, "Converting PPT to PDF...")

            result = converter.convert(
                self._input_path,
                convert_output,
                on_progress=self._on_convert_progress,
                is_cancelled=self._is_cancelled,
            )

            if self._cancelled:
                self._cleanup(tmp_pdf if self._branded else None)
                return

            if not result.success:
                self.finished.emit(result)
                return

            # Step 2: If branded, generate branded PDF
            if self._branded and self._branding_config:
                self.progress.emit(50, 100, "Generating branded PDF...")

                self._branding_config.input_pdf_path = convert_output
                self._branding_config.output_path = self._output_path

                generator = BrandedPDFGenerator()
                branded_result = generator.generate(
                    self._branding_config,
                    on_progress=self._on_brand_progress,
                    is_cancelled=self._is_cancelled,
                )

                # Clean up temp PDF
                self._cleanup(tmp_pdf)

                if not self._cancelled:
                    self.finished.emit(branded_result)
            else:
                if not self._cancelled:
                    self.finished.emit(result)

        except Exception as e:
            if not self._cancelled:
                self.error.emit(f"Unexpected error: {str(e)}")

    def cancel(self):
        self._cancelled = True

    def _is_cancelled(self) -> bool:
        return self._cancelled

    def _on_convert_progress(self, step: int, total: int, msg: str):
        # Map to first 50% of overall progress
        mapped = int(step / total * 50) if total > 0 else 0
        if not self._cancelled:
            self.progress.emit(mapped, 100, msg)

    def _on_brand_progress(self, step: int, total: int, msg: str):
        # Map to last 50% of overall progress
        mapped = 50 + int(step / total * 50) if total > 0 else 50
        if not self._cancelled:
            self.progress.emit(mapped, 100, msg)

    @staticmethod
    def _cleanup(path):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
