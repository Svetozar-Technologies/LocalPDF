# -*- mode: python ; coding: utf-8 -*-
"""
LocalPDF macOS/Windows Application Spec File

Build with: pyinstaller LocalPDF.spec --clean
"""

import sys
from pathlib import Path

block_cipher = None

# Get the current directory
ROOT = Path(SPECPATH)

# Find PyQt6 plugins
def find_pyqt6_plugins():
    """Find PyQt6 Qt plugins."""
    import PyQt6
    pyqt6_path = Path(PyQt6.__file__).parent
    plugins_path = pyqt6_path / 'Qt6' / 'plugins'
    datas = []
    if plugins_path.exists():
        platforms_path = plugins_path / 'platforms'
        if platforms_path.exists():
            datas.append((str(platforms_path), 'PyQt6/Qt6/plugins/platforms'))
        styles_path = plugins_path / 'styles'
        if styles_path.exists():
            datas.append((str(styles_path), 'PyQt6/Qt6/plugins/styles'))
        imageformats_path = plugins_path / 'imageformats'
        if imageformats_path.exists():
            datas.append((str(imageformats_path), 'PyQt6/Qt6/plugins/imageformats'))
    return datas

pyqt6_plugins = find_pyqt6_plugins()

# Collect data files
datas = [
    (str(ROOT / 'core'), 'core'),
    (str(ROOT / 'ui'), 'ui'),
    (str(ROOT / 'workers'), 'workers'),
    (str(ROOT / 'assets'), 'assets'),
] + pyqt6_plugins

# Hidden imports
hiddenimports = [
    # PyQt6/Qt essentials
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtSvg',

    # Core modules
    'core',
    'core.compressor',
    'core.merger',
    'core.splitter',
    'core.converter',
    'core.image_to_pdf',
    'core.branded_pdf',
    'core.utils',

    # UI modules
    'ui',
    'ui.main_window',
    'ui.compress_widget',
    'ui.batch_compress_widget',
    'ui.merge_widget',
    'ui.split_widget',
    'ui.image_to_pdf_widget',
    'ui.convert_widget',
    'ui.settings_widget',
    'ui.theme',

    # Workers
    'workers',

    # PDF libraries
    'fitz',  # PyMuPDF
    'PIL',
    'PIL.Image',
    'reportlab',
    'reportlab.lib',
    'reportlab.pdfgen',
]

# Exclude unnecessary modules
excludes = [
    'tkinter',
    'matplotlib',
    'IPython',
    'notebook',
    'pytest',
    'PyQt5',
    'PySide6',
    'PySide2',
    'torch',
    'tensorflow',
    'numpy.testing',
]

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LocalPDF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LocalPDF',
)

# macOS app bundle
app = BUNDLE(
    coll,
    name='LocalPDF.app',
    icon='assets/icon.icns',
    bundle_identifier='ai.localpdf.desktop',
    info_plist={
        'CFBundleName': 'LocalPDF',
        'CFBundleDisplayName': 'LocalPDF',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleExecutable': 'LocalPDF',
        'CFBundleIdentifier': 'ai.localpdf.desktop',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'LSMinimumSystemVersion': '11.0',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'PDF Document',
                'CFBundleTypeExtensions': ['pdf'],
                'CFBundleTypeRole': 'Editor',
                'LSHandlerRank': 'Alternate',
            },
        ],
        'NSDesktopFolderUsageDescription': 'LocalPDF needs access to save processed documents.',
        'NSDocumentsFolderUsageDescription': 'LocalPDF needs access to open and save documents.',
        'NSDownloadsFolderUsageDescription': 'LocalPDF needs access to save processed documents.',
        'LSApplicationCategoryType': 'public.app-category.productivity',
        'NSPrincipalClass': 'NSApplication',
        'NSHumanReadableCopyright': 'Copyright © 2025 Svetozar Technologies. MIT License.',
        'CFBundleGetInfoString': 'LocalPDF - Private PDF Tools. 100% Offline.',
    },
)
