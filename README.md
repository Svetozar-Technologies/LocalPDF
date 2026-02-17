# LocalPDF

**Private PDF Tools - 100% Offline**

Your documents deserve privacy. LocalPDF compresses, merges, splits, protects, watermarks, converts, and edits PDFs entirely on your device. No cloud. No uploads. No compromise.

## Download

| Platform | Download |
|---|---|
| macOS | [LocalPDF-1.2.0-macOS.dmg](https://github.com/Svetozar-Technologies/LocalPDF/releases/latest/download/LocalPDF-1.2.0-macOS.dmg) |
| Windows | [LocalPDF-Windows.zip](https://github.com/Svetozar-Technologies/LocalPDF/releases/latest/download/LocalPDF-Windows.zip) |
| Linux | [LocalPDF-Linux.tar.gz](https://github.com/Svetozar-Technologies/LocalPDF/releases/latest/download/LocalPDF-Linux.tar.gz) |

## Why LocalPDF?

- **100% Offline** - Your files never leave your device
- **No Accounts** - No sign-up, no API keys, no tracking
- **Free Forever** - MIT licensed, open source
- **Fast & Efficient** - Native performance with PyMuPDF
- **Multi-Language** - Available in 8 languages including RTL support

## Features

### PDF Tools
- **Compress PDF** - Reduce file size while maintaining quality
- **Batch Compress** - Process multiple PDFs at once
- **Merge PDFs** - Combine multiple files into one
- **Split PDF** - Extract pages or split into separate files
- **Protect / Unlock** - Add or remove password protection (AES-256 encryption)
- **Watermark** - Add text or image watermarks to any PDF

### Page Editor
- **Page Manager** - Reorder, rotate, delete, and insert pages
- **Annotations** - Add text, images, and signatures to PDF pages
- **Eraser Tool** - Remove content from PDF pages
- **Edit & Preview** - Full page editing with zoom and navigation

### Convert
- **Image to PDF** - Convert images (JPG, PNG, etc.) to PDF
- **PDF to Image** - Export PDF pages as PNG or JPEG (72-600 DPI)
- **Convert PPT** - Convert PowerPoint presentations to PDF (via LibreOffice)

### Multi-Language Support
LocalPDF is available in 8 languages:

| Language | Native Name |
|---|---|
| English | English |
| Hindi | हिन्दी |
| Russian | Русский |
| Chinese (Simplified) | 中文 |
| Japanese | 日本語 |
| Spanish | Español |
| French | Français |
| Arabic (RTL) | العربية |

Change the language from **Settings** within the app.

## Quick Start

### From Release (Recommended)
Download the latest release for your platform from the [Releases](https://github.com/Svetozar-Technologies/LocalPDF/releases/latest) page.

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/Svetozar-Technologies/LocalPDF.git
   cd LocalPDF
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run LocalPDF:
   ```bash
   python main.py
   ```

## Requirements

- **macOS** 11.0+, **Windows** 10+, or **Linux** (Ubuntu 22.04+)
- Python 3.9+ (when running from source)
- LibreOffice (optional, for PPT conversion)

## Technology

LocalPDF is built with:

- **PyQt6** - Cross-platform native UI
- **PyMuPDF** - Fast PDF manipulation
- **Pillow** - Image processing
- **ReportLab** - PDF generation

## Privacy Promise

LocalPDF is designed with privacy as the foundation:

- **All processing happens on your device** - No data is ever sent to the cloud
- **No internet required** - Works completely offline
- **No telemetry or analytics** - We don't track anything you do
- **No accounts or registration** - Just download and use
- **Open source** - Full transparency, audit the code yourself

## Contributing

We welcome contributions! Please feel free to submit issues and pull requests.

## License

MIT License - Free to use, modify, and distribute.

---

**Built with privacy in mind.**

A [Svetozar Technologies](https://github.com/Svetozar-Technologies) project.
