"""File validation, platform detection, disk space, and formatting utilities."""

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class FileType(Enum):
    PDF = "pdf"
    PPT = "ppt"
    PPTX = "pptx"


@dataclass
class ValidationResult:
    valid: bool
    error_message: str = ""
    file_size_bytes: int = 0
    file_type: Optional[FileType] = None
    is_encrypted: bool = False
    page_count: int = 0


@dataclass
class LibreOfficeInfo:
    found: bool
    path: str = ""
    version: str = ""
    install_instructions: str = ""


def validate_pdf(file_path: str) -> ValidationResult:
    """Validate a PDF file for compression."""
    from i18n import t

    if not file_path:
        return ValidationResult(False, t("validate.no_file"))

    if not os.path.exists(file_path):
        return ValidationResult(False, t("validate.file_not_found", name=os.path.basename(file_path)))

    ext = Path(file_path).suffix.lower()
    if ext != ".pdf":
        return ValidationResult(False, t("validate.wrong_ext_pdf", ext=ext))

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return ValidationResult(False, t("validate.empty_file"))

    try:
        import fitz
        doc = fitz.open(file_path)
    except Exception as e:
        return ValidationResult(False, t("validate.cannot_open_pdf", error=str(e)))

    if doc.is_encrypted:
        doc.close()
        return ValidationResult(
            False,
            t("validate.encrypted"),
            file_size_bytes=file_size,
            file_type=FileType.PDF,
            is_encrypted=True,
        )

    page_count = len(doc)
    doc.close()

    if page_count == 0:
        return ValidationResult(False, t("validate.no_pages"), file_size_bytes=file_size, file_type=FileType.PDF)

    return ValidationResult(
        valid=True,
        file_size_bytes=file_size,
        file_type=FileType.PDF,
        page_count=page_count,
    )


def validate_ppt(file_path: str) -> ValidationResult:
    """Validate a PPT/PPTX file for conversion."""
    from i18n import t

    if not file_path:
        return ValidationResult(False, t("validate.no_file"))

    if not os.path.exists(file_path):
        return ValidationResult(False, t("validate.file_not_found", name=os.path.basename(file_path)))

    ext = Path(file_path).suffix.lower()
    if ext not in (".ppt", ".pptx"):
        return ValidationResult(False, t("validate.wrong_ext_ppt", ext=ext))

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return ValidationResult(False, t("validate.empty_file"))

    file_type = FileType.PPTX if ext == ".pptx" else FileType.PPT

    # Basic magic byte check for PPTX (ZIP) or PPT (OLE)
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
        if ext == ".pptx" and header[:4] != b"PK\x03\x04":
            return ValidationResult(False, t("validate.corrupted_pptx"))
        if ext == ".ppt" and header[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            return ValidationResult(False, t("validate.corrupted_ppt"))
    except Exception as e:
        return ValidationResult(False, t("validate.cannot_read", error=str(e)))

    return ValidationResult(
        valid=True,
        file_size_bytes=file_size,
        file_type=file_type,
    )


def format_file_size(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    if size_bytes < 0:
        return "0 B"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def parse_target_size_mb(value: float) -> int:
    """Convert MB to bytes. Raises ValueError if invalid."""
    if value <= 0:
        raise ValueError("Target size must be greater than 0.")
    return int(value * 1024 * 1024)


def get_output_path(input_path: str, suffix: str = "_compressed") -> str:
    """Generate an output path that doesn't overwrite the input file."""
    p = Path(input_path)
    base = p.stem + suffix
    ext = p.suffix
    output = p.parent / (base + ext)

    counter = 1
    while output.exists():
        output = p.parent / (f"{base}({counter}){ext}")
        counter += 1

    return str(output)


def check_disk_space(output_dir: str, required_bytes: int) -> Tuple[bool, str]:
    """Check if output directory has enough free disk space."""
    try:
        stat = shutil.disk_usage(output_dir)
        # Require 2x safety margin
        needed = required_bytes * 2
        if stat.free < needed:
            from i18n import t
            return (
                False,
                t("validate.disk_space",
                  needed=format_file_size(needed),
                  available=format_file_size(stat.free)),
            )
        return (True, "")
    except Exception as e:
        return (True, "")  # If we can't check, proceed anyway


def get_platform() -> str:
    """Return 'macos', 'windows', or 'linux'."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return "linux"


def detect_libreoffice() -> LibreOfficeInfo:
    """Detect LibreOffice installation on the system."""
    plat = get_platform()

    search_paths = []
    if plat == "macos":
        search_paths = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS/soffice"),
            "/opt/homebrew/bin/soffice",
            "soffice",
        ]
    elif plat == "windows":
        search_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            "soffice",
        ]
    else:
        search_paths = [
            "/usr/bin/soffice",
            "/usr/bin/libreoffice",
            "soffice",
            "libreoffice",
        ]

    for path in search_paths:
        resolved = shutil.which(path) if not os.path.isabs(path) else path
        if resolved and os.path.isfile(resolved):
            # Try to get version
            version = ""
            try:
                result = subprocess.run(
                    [resolved, "--version"],
                    capture_output=True, text=True, timeout=10,
                )
                version = result.stdout.strip()
            except Exception:
                pass
            return LibreOfficeInfo(found=True, path=resolved, version=version)

    return LibreOfficeInfo(
        found=False,
        install_instructions=get_libreoffice_install_instructions(),
    )


def get_libreoffice_install_instructions() -> str:
    """Return platform-specific LibreOffice install instructions."""
    from i18n import t
    plat = get_platform()
    if plat == "macos":
        return t("lo_instructions.macos")
    if plat == "windows":
        return t("lo_instructions.windows")
    return t("lo_instructions.linux")


def validate_image(file_path: str) -> ValidationResult:
    """Validate an image file for Image-to-PDF conversion."""
    from i18n import t

    if not file_path:
        return ValidationResult(False, t("validate.no_file"))

    if not os.path.exists(file_path):
        return ValidationResult(False, t("validate.file_not_found", name=os.path.basename(file_path)))

    ext = Path(file_path).suffix.lower()
    valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
    if ext not in valid_exts:
        return ValidationResult(False, t("validate.unsupported_image", ext=ext))

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return ValidationResult(False, t("validate.empty_file"))

    try:
        from PIL import Image
        img = Image.open(file_path)
        img.verify()
    except Exception as e:
        return ValidationResult(False, t("validate.cannot_open_image", error=str(e)))

    return ValidationResult(valid=True, file_size_bytes=file_size)


@dataclass
class TesseractInfo:
    found: bool
    path: str = ""
    version: str = ""
    languages: list = None
    install_instructions: str = ""

    def __post_init__(self):
        if self.languages is None:
            self.languages = []


def detect_tesseract() -> TesseractInfo:
    """Detect Tesseract OCR installation on the system."""
    plat = get_platform()

    search_paths = []
    if plat == "macos":
        search_paths = [
            "/opt/homebrew/bin/tesseract",
            "/usr/local/bin/tesseract",
            "tesseract",
        ]
    elif plat == "windows":
        search_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            "tesseract",
        ]
    else:
        search_paths = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            "tesseract",
        ]

    for path in search_paths:
        resolved = shutil.which(path) if not os.path.isabs(path) else path
        if resolved and os.path.isfile(resolved):
            version = ""
            languages = []
            try:
                result = subprocess.run(
                    [resolved, "--version"],
                    capture_output=True, text=True, timeout=10,
                )
                version = result.stdout.strip().split("\n")[0]
            except Exception:
                pass
            try:
                result = subprocess.run(
                    [resolved, "--list-langs"],
                    capture_output=True, text=True, timeout=10,
                )
                lines = result.stdout.strip().split("\n")
                # First line is header, rest are languages
                languages = [l.strip() for l in lines[1:] if l.strip() and l.strip() != "osd"]
            except Exception:
                languages = ["eng"]
            return TesseractInfo(
                found=True, path=resolved, version=version, languages=languages,
            )

    return TesseractInfo(
        found=False,
        install_instructions=get_tesseract_install_instructions(),
    )


def get_tesseract_install_instructions() -> str:
    """Return platform-specific Tesseract install instructions."""
    plat = get_platform()
    if plat == "macos":
        return (
            "Tesseract OCR is needed for text recognition.\n\n"
            "Install with Homebrew:\nbrew install tesseract\n\n"
            "For additional languages:\nbrew install tesseract-lang"
        )
    if plat == "windows":
        return (
            "Tesseract OCR is needed for text recognition.\n\n"
            "Download the installer from:\n"
            "https://github.com/UB-Mannheim/tesseract/wiki\n\n"
            "Run the installer and restart LocalPDF."
        )
    return (
        "Tesseract OCR is needed for text recognition.\n\n"
        "Install via your package manager:\nsudo apt install tesseract-ocr\n\n"
        "For additional languages:\nsudo apt install tesseract-ocr-all"
    )


def validate_image_or_pdf(file_path: str) -> ValidationResult:
    """Validate a file as either a PDF or an image (for OCR input)."""
    if not file_path:
        return ValidationResult(False, "No file selected.")

    if not os.path.exists(file_path):
        return ValidationResult(False, f"File not found: {os.path.basename(file_path)}")

    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        return validate_pdf(file_path)

    valid_image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
    if ext in valid_image_exts:
        return validate_image(file_path)

    return ValidationResult(
        False,
        f"Unsupported file format: '{ext}'. Expected PDF or image (JPG, PNG, BMP, TIFF, WebP).",
    )


def get_asset_path(relative_path: str) -> str:
    """Get absolute path to an asset, works for dev and PyInstaller."""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)
