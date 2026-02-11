"""PDF Protect / Unlock Engine."""

import os
import fitz
from dataclasses import dataclass
from typing import Callable, Optional


# PyMuPDF permission flags
PERM_PRINT = fitz.PDF_PERM_PRINT
PERM_COPY = fitz.PDF_PERM_COPY
PERM_MODIFY = fitz.PDF_PERM_MODIFY
PERM_ANNOTATE = fitz.PDF_PERM_ANNOTATE


@dataclass
class ProtectResult:
    success: bool
    output_path: str = ""
    error_message: str = ""
    page_count: int = 0


@dataclass
class ProtectConfig:
    input_path: str
    output_path: str
    user_password: str = ""
    owner_password: str = ""
    allow_print: bool = True
    allow_copy: bool = False
    allow_modify: bool = False
    allow_annotate: bool = True


@dataclass
class UnlockConfig:
    input_path: str
    output_path: str
    password: str = ""


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class PDFProtector:
    """Adds or removes password protection on PDFs."""

    def protect(
        self,
        config: ProtectConfig,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> ProtectResult:
        """Add password protection to a PDF."""
        if not config.user_password and not config.owner_password:
            return ProtectResult(
                success=False,
                error_message="At least one password (user or owner) is required.",
            )

        self._report(on_progress, 10, 100, "Opening PDF...")

        try:
            doc = fitz.open(config.input_path)
        except Exception as e:
            return ProtectResult(success=False, error_message=f"Cannot open PDF: {e}")

        if is_cancelled and is_cancelled():
            doc.close()
            return ProtectResult(success=False, error_message="Cancelled.")

        page_count = len(doc)

        self._report(on_progress, 30, 100, "Applying encryption...")

        # Build permission flags
        permissions = 0
        if config.allow_print:
            permissions |= PERM_PRINT
        if config.allow_copy:
            permissions |= PERM_COPY
        if config.allow_modify:
            permissions |= PERM_MODIFY
        if config.allow_annotate:
            permissions |= PERM_ANNOTATE

        try:
            self._report(on_progress, 60, 100, "Saving protected PDF...")

            doc.save(
                config.output_path,
                encryption=fitz.PDF_ENCRYPT_AES_256,
                user_pw=config.user_password or None,
                owner_pw=config.owner_password or config.user_password,
                permissions=permissions,
            )
            doc.close()

            self._report(on_progress, 100, 100, "Done!")

            return ProtectResult(
                success=True,
                output_path=config.output_path,
                page_count=page_count,
            )

        except Exception as e:
            doc.close()
            return ProtectResult(success=False, error_message=f"Protection failed: {e}")

    def unlock(
        self,
        config: UnlockConfig,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> ProtectResult:
        """Remove password protection from a PDF."""
        self._report(on_progress, 10, 100, "Opening encrypted PDF...")

        try:
            doc = fitz.open(config.input_path)
        except Exception as e:
            return ProtectResult(success=False, error_message=f"Cannot open PDF: {e}")

        if not doc.is_encrypted:
            page_count = len(doc)
            doc.close()
            return ProtectResult(
                success=False,
                error_message="This PDF is not encrypted. No password to remove.",
            )

        # Try to authenticate with the provided password
        if not doc.authenticate(config.password):
            doc.close()
            return ProtectResult(
                success=False,
                error_message="Incorrect password. Cannot unlock this PDF.",
            )

        if is_cancelled and is_cancelled():
            doc.close()
            return ProtectResult(success=False, error_message="Cancelled.")

        page_count = len(doc)

        self._report(on_progress, 50, 100, "Removing encryption...")

        try:
            self._report(on_progress, 70, 100, "Saving unlocked PDF...")

            # Save without encryption
            doc.save(config.output_path, encryption=fitz.PDF_ENCRYPT_NONE)
            doc.close()

            self._report(on_progress, 100, 100, "Done!")

            return ProtectResult(
                success=True,
                output_path=config.output_path,
                page_count=page_count,
            )

        except Exception as e:
            doc.close()
            return ProtectResult(success=False, error_message=f"Unlock failed: {e}")

    @staticmethod
    def _report(cb: Optional[ProgressCallback], step: int, total: int, msg: str):
        if cb:
            cb(step, total, msg)
