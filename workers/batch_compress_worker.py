"""Background worker for batch PDF compression."""

import os
from dataclasses import dataclass, field
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal

from core.compressor import PDFCompressor, CompressionConfig
from core.utils import get_output_path, format_file_size


@dataclass
class BatchFileResult:
    path: str
    success: bool
    original_size: int = 0
    compressed_size: int = 0
    output_path: str = ""
    error_message: str = ""


@dataclass
class BatchCompressResult:
    total_files: int = 0
    succeeded: int = 0
    failed: int = 0
    total_original_size: int = 0
    total_compressed_size: int = 0
    output_folder: str = ""
    file_results: List[BatchFileResult] = field(default_factory=list)


class BatchCompressWorker(QThread):
    """Compresses multiple PDFs in sequence."""

    progress = pyqtSignal(int, int, str)
    file_started = pyqtSignal(int, str)
    file_finished = pyqtSignal(int, object)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        file_paths: List[str],
        target_size_bytes: int,
        parent=None,
    ):
        super().__init__(parent)
        self._file_paths = file_paths
        self._target_size_bytes = target_size_bytes
        self._cancelled = False
        self._compressor = PDFCompressor()

    def run(self):
        total = len(self._file_paths)
        batch_result = BatchCompressResult(total_files=total)

        # Create a shared output subfolder next to the first input file
        first_dir = os.path.dirname(self._file_paths[0])
        output_dir = os.path.join(first_dir, "compressed")
        os.makedirs(output_dir, exist_ok=True)
        batch_result.output_folder = output_dir

        try:
            for i, path in enumerate(self._file_paths):
                if self._cancelled:
                    break

                name = os.path.basename(path)
                self.file_started.emit(i, name)

                # Save to compressed/ subfolder with original filename
                output_path = os.path.join(output_dir, name)
                # Avoid overwriting if same name exists
                if os.path.exists(output_path):
                    stem, ext = os.path.splitext(name)
                    counter = 1
                    while os.path.exists(output_path):
                        output_path = os.path.join(output_dir, f"{stem}({counter}){ext}")
                        counter += 1

                config = CompressionConfig(
                    input_path=path,
                    output_path=output_path,
                    target_size_bytes=self._target_size_bytes,
                )

                try:
                    result = self._compressor.compress(
                        config,
                        on_progress=lambda s, t, m, idx=i: self._on_file_progress(idx, s, t, m),
                        is_cancelled=self._is_cancelled,
                    )
                    if self._cancelled:
                        break

                    file_result = BatchFileResult(
                        path=path,
                        success=result.success,
                        original_size=result.original_size,
                        compressed_size=result.compressed_size,
                        output_path=result.output_path if result.success else "",
                        error_message=result.error_message,
                    )
                except Exception as e:
                    file_result = BatchFileResult(
                        path=path, success=False, error_message=str(e),
                    )

                if not self._cancelled:
                    self.file_finished.emit(i, file_result)
                    batch_result.file_results.append(file_result)
                    if file_result.success:
                        batch_result.succeeded += 1
                        batch_result.total_original_size += file_result.original_size
                        batch_result.total_compressed_size += file_result.compressed_size
                    else:
                        batch_result.failed += 1

                    overall_pct = int((i + 1) / total * 100)
                    self.progress.emit(
                        overall_pct, 100,
                        f"Completed {i + 1}/{total} files",
                    )

            if not self._cancelled:
                self.finished.emit(batch_result)

        except Exception as e:
            if not self._cancelled:
                self.error.emit(f"Batch compression error: {str(e)}")

    def cancel(self):
        self._cancelled = True

    def _on_file_progress(self, file_index: int, step: int, total: int, message: str):
        pass  # Per-file progress is not surfaced to overall progress bar

    def _is_cancelled(self) -> bool:
        return self._cancelled
