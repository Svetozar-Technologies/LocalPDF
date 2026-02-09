"""PDF Merge Engine."""

import os
import fitz
from dataclasses import dataclass
from typing import Callable, Optional, List


@dataclass
class MergeResult:
    success: bool
    output_path: str = ""
    total_pages: int = 0
    file_count: int = 0
    output_size: int = 0
    error_message: str = ""


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class PDFMerger:
    """Merges multiple PDF files into one."""

    def merge(
        self,
        input_paths: List[str],
        output_path: str,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> MergeResult:
        if len(input_paths) < 2:
            return MergeResult(
                success=False,
                error_message="At least 2 PDF files are required to merge.",
            )

        # Validate all inputs first
        for path in input_paths:
            if not os.path.exists(path):
                return MergeResult(
                    success=False,
                    error_message=f"File not found: {os.path.basename(path)}",
                )

        total = len(input_paths)
        self._report(on_progress, 0, total, "Starting merge...")

        output_doc = fitz.open()
        total_pages = 0

        try:
            for i, path in enumerate(input_paths):
                if is_cancelled and is_cancelled():
                    output_doc.close()
                    return MergeResult(success=False, error_message="Cancelled.")

                name = os.path.basename(path)
                self._report(on_progress, i, total, f"Merging {name} ({i + 1}/{total})...")

                try:
                    src_doc = fitz.open(path)
                    if src_doc.is_encrypted:
                        src_doc.close()
                        output_doc.close()
                        return MergeResult(
                            success=False,
                            error_message=f"'{name}' is password-protected.",
                        )
                    output_doc.insert_pdf(src_doc)
                    total_pages += len(src_doc)
                    src_doc.close()
                except Exception as e:
                    output_doc.close()
                    return MergeResult(
                        success=False,
                        error_message=f"Error reading '{name}': {e}",
                    )

            self._report(on_progress, total, total, "Saving merged PDF...")
            output_doc.save(output_path, garbage=4)
            output_doc.close()

            output_size = os.path.getsize(output_path)
            return MergeResult(
                success=True,
                output_path=output_path,
                total_pages=total_pages,
                file_count=total,
                output_size=output_size,
            )

        except Exception as e:
            try:
                output_doc.close()
            except Exception:
                pass
            return MergeResult(success=False, error_message=f"Merge failed: {e}")

    @staticmethod
    def _report(cb: Optional[ProgressCallback], step: int, total: int, msg: str):
        if cb:
            cb(step, total, msg)
