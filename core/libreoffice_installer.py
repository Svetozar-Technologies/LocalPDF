"""LibreOffice auto-downloader and installer."""

import os
import sys
import time
import shutil
import platform
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from core.utils import get_platform, detect_libreoffice, format_file_size


# Pinned stable version — update with each LocalPDF release
LO_VERSION = "26.2.0"

# Official mirror base
LO_BASE_URL = "https://download.documentfoundation.org/libreoffice/stable"


@dataclass
class DownloadProgress:
    bytes_downloaded: int
    bytes_total: int  # -1 if unknown
    speed_bps: float
    phase: str  # "downloading", "installing", "verifying"


@dataclass
class InstallResult:
    success: bool
    error_message: str = ""
    soffice_path: str = ""


ProgressCallback = Callable[[DownloadProgress], None]
CancelCheck = Callable[[], bool]


class LibreOfficeInstaller:
    """Downloads and installs LibreOffice silently."""

    def __init__(self):
        self._download_dir = Path(tempfile.gettempdir()) / "localpdf_lo_install"

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def get_download_url(self) -> str:
        """Build the platform-specific download URL."""
        plat = get_platform()
        if plat == "macos":
            arch = platform.machine()  # "arm64" or "x86_64"
            if arch == "arm64":
                fname = f"LibreOffice_{LO_VERSION}_MacOS_aarch64.dmg"
                return f"{LO_BASE_URL}/{LO_VERSION}/mac/aarch64/{fname}"
            else:
                fname = f"LibreOffice_{LO_VERSION}_MacOS_x86-64.dmg"
                return f"{LO_BASE_URL}/{LO_VERSION}/mac/x86_64/{fname}"
        elif plat == "windows":
            fname = f"LibreOffice_{LO_VERSION}_Win_x86-64.msi"
            return f"{LO_BASE_URL}/{LO_VERSION}/win/x86_64/{fname}"
        else:
            fname = f"LibreOffice_{LO_VERSION}_Linux_x86-64.deb.tar.gz"
            return f"{LO_BASE_URL}/{LO_VERSION}/deb/x86_64/{fname}"

    def get_expected_filename(self) -> str:
        """Return the expected local filename."""
        url = self.get_download_url()
        return url.rsplit("/", 1)[-1]

    # ------------------------------------------------------------------
    # Pre-flight checks
    # ------------------------------------------------------------------

    def check_already_installed(self) -> Optional[str]:
        """Return soffice path if LibreOffice is already installed, else None."""
        info = detect_libreoffice()
        if info.found:
            return info.path
        return None

    def check_disk_space(self) -> Tuple[bool, str]:
        """Ensure at least 600 MB free in the temp dir and install dir."""
        required = 600 * 1024 * 1024  # 600 MB
        try:
            self._download_dir.mkdir(parents=True, exist_ok=True)
            stat = shutil.disk_usage(str(self._download_dir))
            if stat.free < required:
                return False, (
                    f"Not enough disk space. Need at least 600 MB, "
                    f"only {format_file_size(stat.free)} available."
                )
        except Exception as e:
            return False, f"Cannot check disk space: {e}"
        return True, ""

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(
        self,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> Tuple[bool, str, str]:
        """Download LibreOffice installer.

        Returns (success, file_path, error_message).
        """
        url = self.get_download_url()
        self._download_dir.mkdir(parents=True, exist_ok=True)
        dest = self._download_dir / self.get_expected_filename()

        max_retries = 3
        backoff = [1, 4, 16]

        for attempt in range(max_retries):
            if is_cancelled and is_cancelled():
                return False, "", "Cancelled."

            try:
                req = urllib.request.Request(url)
                req.add_header("User-Agent", "LocalPDF/1.0")

                # Resume support
                downloaded = 0
                if dest.exists():
                    downloaded = dest.stat().st_size
                    req.add_header("Range", f"bytes={downloaded}-")

                response = urllib.request.urlopen(req, timeout=30)

                # Handle content length
                content_length = response.headers.get("Content-Length")
                if content_length:
                    total = int(content_length) + downloaded
                else:
                    total = -1

                # Check if server supports range (206) or sent full file (200)
                if response.status == 200:
                    # Server sent full file, start from scratch
                    downloaded = 0
                    mode = "wb"
                else:
                    mode = "ab"

                chunk_size = 65536  # 64 KB
                start_time = time.time()
                bytes_since_last = 0
                last_progress_time = start_time

                with open(dest, mode) as f:
                    while True:
                        if is_cancelled and is_cancelled():
                            return False, "", "Cancelled."

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)
                        bytes_since_last += len(chunk)

                        now = time.time()
                        elapsed = now - last_progress_time
                        if elapsed >= 0.3 and on_progress:
                            speed = bytes_since_last / elapsed if elapsed > 0 else 0
                            on_progress(DownloadProgress(
                                bytes_downloaded=downloaded,
                                bytes_total=total,
                                speed_bps=speed,
                                phase="downloading",
                            ))
                            bytes_since_last = 0
                            last_progress_time = now

                response.close()

                # Verify download
                if total > 0 and dest.stat().st_size < total * 0.95:
                    raise Exception("Download incomplete.")

                return True, str(dest), ""

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(backoff[attempt])
                    continue
                return False, "", f"Download failed after {max_retries} attempts: {e}"

        return False, "", "Download failed."

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    def install(
        self,
        installer_path: str,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> InstallResult:
        """Install LibreOffice from a downloaded file."""
        plat = get_platform()

        if on_progress:
            on_progress(DownloadProgress(0, 0, 0, "installing"))

        if plat == "macos":
            return self._install_macos(installer_path, on_progress, is_cancelled)
        elif plat == "windows":
            return self._install_windows(installer_path, on_progress, is_cancelled)
        else:
            return InstallResult(
                success=False,
                error_message="Auto-install is not supported on Linux. "
                              "Please install LibreOffice via your package manager:\n"
                              "sudo apt install libreoffice",
            )

    def _install_macos(
        self,
        dmg_path: str,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> InstallResult:
        """Mount DMG, copy .app to /Applications, unmount."""
        mount_point = str(self._download_dir / "lo_mount")

        try:
            # Mount DMG
            if on_progress:
                on_progress(DownloadProgress(0, 0, 0, "installing"))

            result = subprocess.run(
                ["hdiutil", "attach", dmg_path, "-nobrowse", "-quiet",
                 "-mountpoint", mount_point],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return InstallResult(
                    success=False,
                    error_message=f"Failed to mount installer: {result.stderr.strip()}",
                )

            if is_cancelled and is_cancelled():
                self._unmount(mount_point)
                return InstallResult(success=False, error_message="Cancelled.")

            # Find LibreOffice.app inside the mount
            app_src = os.path.join(mount_point, "LibreOffice.app")
            if not os.path.isdir(app_src):
                # Search for it
                for item in os.listdir(mount_point):
                    if item.endswith(".app") and "LibreOffice" in item:
                        app_src = os.path.join(mount_point, item)
                        break

            if not os.path.isdir(app_src):
                self._unmount(mount_point)
                return InstallResult(
                    success=False,
                    error_message="Could not find LibreOffice.app in the installer.",
                )

            # Copy to /Applications (try system-level first, then user)
            dest = "/Applications/LibreOffice.app"
            try:
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                subprocess.run(
                    ["cp", "-R", app_src, dest],
                    capture_output=True, text=True, timeout=300,
                    check=True,
                )
            except (PermissionError, subprocess.CalledProcessError):
                # Fallback to ~/Applications
                user_apps = os.path.expanduser("~/Applications")
                os.makedirs(user_apps, exist_ok=True)
                dest = os.path.join(user_apps, "LibreOffice.app")
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                subprocess.run(
                    ["cp", "-R", app_src, dest],
                    capture_output=True, text=True, timeout=300,
                    check=True,
                )

            # Clear quarantine attribute
            subprocess.run(
                ["xattr", "-rd", "com.apple.quarantine", dest],
                capture_output=True, timeout=30,
            )

            # Unmount
            self._unmount(mount_point)

            if on_progress:
                on_progress(DownloadProgress(0, 0, 0, "verifying"))

            # Verify
            soffice = os.path.join(dest, "Contents", "MacOS", "soffice")
            if os.path.isfile(soffice):
                return InstallResult(success=True, soffice_path=soffice)

            return InstallResult(
                success=False,
                error_message="Installation completed but soffice binary not found.",
            )

        except Exception as e:
            self._unmount(mount_point)
            return InstallResult(success=False, error_message=f"Installation failed: {e}")

    def _install_windows(
        self,
        msi_path: str,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> InstallResult:
        """Run MSI installer silently."""
        try:
            if on_progress:
                on_progress(DownloadProgress(0, 0, 0, "installing"))

            cmd = ["msiexec", "/i", msi_path, "/qn", "/norestart"]

            # Try with elevation on Windows
            if sys.platform == "win32":
                import ctypes
                if not ctypes.windll.shell32.IsUserAnAdmin():
                    # Request elevation
                    params = f'/i "{msi_path}" /qn /norestart'
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", "msiexec", params, None, 1
                    )
                    if ret <= 32:
                        return InstallResult(
                            success=False,
                            error_message="Administrator access is required to install LibreOffice.\n"
                                          "Please run LocalPDF as administrator or install LibreOffice manually.",
                        )
                    # Wait for installation to complete
                    time.sleep(30)
                else:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=600,
                    )
                    if result.returncode != 0:
                        return InstallResult(
                            success=False,
                            error_message=f"Installation failed (exit code {result.returncode}).",
                        )

            if on_progress:
                on_progress(DownloadProgress(0, 0, 0, "verifying"))

            # Verify
            expected_paths = [
                r"C:\Program Files\LibreOffice\program\soffice.exe",
                r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            ]
            for path in expected_paths:
                if os.path.isfile(path):
                    return InstallResult(success=True, soffice_path=path)

            # Give it a moment and retry
            time.sleep(5)
            for path in expected_paths:
                if os.path.isfile(path):
                    return InstallResult(success=True, soffice_path=path)

            return InstallResult(
                success=False,
                error_message="Installation completed but soffice.exe was not found.",
            )

        except Exception as e:
            return InstallResult(success=False, error_message=f"Installation failed: {e}")

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def download_and_install(
        self,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> InstallResult:
        """Full pipeline: check → download → install → verify."""
        # Already installed?
        existing = self.check_already_installed()
        if existing:
            return InstallResult(success=True, soffice_path=existing)

        # Disk space check
        ok, err = self.check_disk_space()
        if not ok:
            return InstallResult(success=False, error_message=err)

        # Download
        success, file_path, error = self.download(on_progress, is_cancelled)
        if not success:
            return InstallResult(success=False, error_message=error or "Download failed.")

        if is_cancelled and is_cancelled():
            return InstallResult(success=False, error_message="Cancelled.")

        # Install
        result = self.install(file_path, on_progress, is_cancelled)

        # Cleanup downloaded file on success
        if result.success:
            self.cleanup()

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unmount(mount_point: str):
        """Safely unmount a DMG."""
        try:
            subprocess.run(
                ["hdiutil", "detach", mount_point, "-quiet", "-force"],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass

    def cleanup(self):
        """Remove downloaded installer files."""
        try:
            if self._download_dir.exists():
                shutil.rmtree(str(self._download_dir))
        except Exception:
            pass
