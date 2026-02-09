"""PDF Split / Extract Pages Engine."""

import os
import fitz
from dataclasses import dataclass, field
from typing import Callable, Optional, List
from pathlib import Path


@dataclass
class SplitResult:
    success: bool
    output_paths: List[str] = field(default_factory=list)
    total_pages_extracted: int = 0
    total_output_size: int = 0
    error_message: str = ""


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class PageRangeParser:
    """Parses page range strings like '1-5', '3,7,10-15', '1,3-5,8'."""

    @staticmethod
    def parse(range_str: str, max_page: int) -> List[int]:
        """
        Parse a page range string and return sorted, deduplicated, 0-indexed page numbers.
        Input is 1-indexed (user-facing). Output is 0-indexed (for fitz).
        Raises ValueError on invalid input.
        """
        if not range_str or not range_str.strip():
            raise ValueError("Page range cannot be empty.")

        pages = set()
        parts = range_str.split(",")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if "-" in part:
                bounds = part.split("-", 1)
                if len(bounds) != 2:
                    raise ValueError(f"Invalid range: '{part}'")
                try:
                    start = int(bounds[0].strip())
                    end = int(bounds[1].strip())
                except ValueError:
                    raise ValueError(f"Non-numeric value in range: '{part}'")

                if start > end:
                    raise ValueError(f"Invalid range '{part}': start ({start}) > end ({end}).")
                if start < 1:
                    raise ValueError(f"Page number must be at least 1, got {start}.")
                if end > max_page:
                    raise ValueError(f"Page {end} exceeds document length ({max_page} pages).")

                for p in range(start, end + 1):
                    pages.add(p - 1)  # Convert to 0-indexed
            else:
                try:
                    p = int(part)
                except ValueError:
                    raise ValueError(f"Non-numeric page number: '{part}'")
                if p < 1:
                    raise ValueError(f"Page number must be at least 1, got {p}.")
                if p > max_page:
                    raise ValueError(f"Page {p} exceeds document length ({max_page} pages).")
                pages.add(p - 1)  # Convert to 0-indexed

        if not pages:
            raise ValueError("No valid pages specified.")

        return sorted(pages)


class PDFSplitter:
    """Extracts pages from a PDF or splits into individual pages."""

    def extract_pages(
        self,
        input_path: str,
        output_path: str,
        page_numbers: List[int],
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> SplitResult:
        """Extract specified pages into a single output PDF."""
        if not page_numbers:
            return SplitResult(success=False, error_message="No pages selected.")

        self._report(on_progress, 0, 100, "Opening PDF...")

        try:
            doc = fitz.open(input_path)
        except Exception as e:
            return SplitResult(success=False, error_message=f"Cannot open PDF: {e}")

        if is_cancelled and is_cancelled():
            doc.close()
            return SplitResult(success=False, error_message="Cancelled.")

        try:
            self._report(on_progress, 30, 100, f"Extracting {len(page_numbers)} pages...")
            doc.select(page_numbers)
            self._report(on_progress, 70, 100, "Saving...")
            doc.save(output_path, garbage=4)
            doc.close()

            output_size = os.path.getsize(output_path)
            return SplitResult(
                success=True,
                output_paths=[output_path],
                total_pages_extracted=len(page_numbers),
                total_output_size=output_size,
            )
        except Exception as e:
            doc.close()
            return SplitResult(success=False, error_message=f"Extraction failed: {e}")

    def split_individual(
        self,
        input_path: str,
        output_dir: str,
        page_numbers: List[int],
        base_name: str = "",
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> SplitResult:
        """Split into individual PDFs, one per page."""
        if not page_numbers:
            return SplitResult(success=False, error_message="No pages selected.")

        if not base_name:
            base_name = Path(input_path).stem

        total = len(page_numbers)
        # Zero-pad width based on total pages
        pad_width = len(str(max(page_numbers) + 1))  # +1 for 1-indexed display

        self._report(on_progress, 0, total, "Opening PDF...")

        try:
            src_doc = fitz.open(input_path)
        except Exception as e:
            return SplitResult(success=False, error_message=f"Cannot open PDF: {e}")

        output_paths = []
        total_size = 0

        try:
            for i, page_num in enumerate(page_numbers):
                if is_cancelled and is_cancelled():
                    src_doc.close()
                    return SplitResult(success=False, error_message="Cancelled.")

                page_label = str(page_num + 1).zfill(pad_width)
                out_name = f"{base_name}_page_{page_label}.pdf"
                out_path = os.path.join(output_dir, out_name)

                self._report(on_progress, i, total,
                             f"Saving page {page_num + 1} ({i + 1}/{total})...")

                single_doc = fitz.open()
                single_doc.insert_pdf(src_doc, from_page=page_num, to_page=page_num)
                single_doc.save(out_path, garbage=4)
                single_doc.close()

                output_paths.append(out_path)
                total_size += os.path.getsize(out_path)

            src_doc.close()

            return SplitResult(
                success=True,
                output_paths=output_paths,
                total_pages_extracted=total,
                total_output_size=total_size,
            )
        except Exception as e:
            src_doc.close()
            return SplitResult(success=False, error_message=f"Split failed: {e}")

    @staticmethod
    def _report(cb: Optional[ProgressCallback], step: int, total: int, msg: str):
        if cb:
            cb(step, total, msg)
