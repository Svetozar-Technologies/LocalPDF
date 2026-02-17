"""PPT/PPTX to PDF converter using LibreOffice headless."""

import os
import sys
import subprocess
import tempfile
import shutil
import time
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path

from core.utils import detect_libreoffice, get_platform


@dataclass
class ConversionResult:
    success: bool
    output_path: str = ""
    error_message: str = ""
    libreoffice_missing: bool = False
    install_instructions: str = ""
    page_count: int = 0


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class PPTConverter:
    """Converts PPT/PPTX to PDF using LibreOffice in headless mode."""

    def __init__(self):
        self._lo_info = None

    def check_libreoffice(self):
        """Check and cache LibreOffice detection result."""
        if self._lo_info is None:
            self._lo_info = detect_libreoffice()
        return self._lo_info

    def convert(
        self,
        input_path: str,
        output_path: str,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> ConversionResult:
        """Convert PPT/PPTX to PDF."""
        # Step 1: Check LibreOffice
        lo = self.check_libreoffice()
        if not lo.found:
            return ConversionResult(
                success=False,
                libreoffice_missing=True,
                install_instructions=lo.install_instructions,
                error_message="LibreOffice is not installed.",
            )

        if on_progress:
            on_progress(10, 100, "Starting LibreOffice conversion...")

        # Step 2: Convert using a temp directory
        with tempfile.TemporaryDirectory(prefix="localpdf_convert_") as tmp_dir:
            cmd = [
                lo.path,
                "--headless",
                "--norestore",
                "--convert-to", "pdf",
                "--outdir", tmp_dir,
                input_path,
            ]

            if on_progress:
                on_progress(20, 100, "Converting slides to PDF...")

            try:
                popen_kwargs = {
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.PIPE,
                }
                # On Windows, hide the console window
                if get_platform() == "windows":
                    popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

                proc = subprocess.Popen(cmd, **popen_kwargs)
                start_time = time.time()
                timeout = 300

                # Poll with cancellation check
                while proc.poll() is None:
                    if is_cancelled and is_cancelled():
                        proc.kill()
                        proc.wait()
                        return ConversionResult(
                            success=False,
                            error_message="Cancelled.",
                        )
                    if time.time() - start_time > timeout:
                        proc.kill()
                        proc.wait()
                        return ConversionResult(
                            success=False,
                            error_message="Conversion timed out. The file may be too large.",
                        )
                    time.sleep(0.3)

                if proc.returncode != 0:
                    stderr = proc.stderr.read().decode(errors="replace").strip() if proc.stderr else ""
                    stdout = proc.stdout.read().decode(errors="replace").strip() if proc.stdout else ""
                    error_detail = stderr or stdout
                    return ConversionResult(
                        success=False,
                        error_message=f"LibreOffice conversion failed.\n{error_detail}",
                    )
            except Exception as e:
                return ConversionResult(
                    success=False,
                    error_message=f"Error running LibreOffice: {e}",
                )

            if on_progress:
                on_progress(80, 100, "Finalizing...")

            # Step 3: Find and move the output
            pptx_stem = Path(input_path).stem
            generated_pdf = os.path.join(tmp_dir, f"{pptx_stem}.pdf")

            if not os.path.exists(generated_pdf):
                # Try to find any PDF in tmp_dir
                import glob
                pdfs = glob.glob(os.path.join(tmp_dir, "*.pdf"))
                if pdfs:
                    generated_pdf = pdfs[0]
                else:
                    return ConversionResult(
                        success=False,
                        error_message="Conversion produced no output. The file format may not be supported.",
                    )

            # Get page count
            page_count = 0
            try:
                import fitz
                doc = fitz.open(generated_pdf)
                page_count = len(doc)
                doc.close()
            except Exception:
                pass

            # Move to final output
            shutil.move(generated_pdf, output_path)

            if on_progress:
                on_progress(100, 100, "Done!")

            return ConversionResult(
                success=True,
                output_path=output_path,
                page_count=page_count,
            )
