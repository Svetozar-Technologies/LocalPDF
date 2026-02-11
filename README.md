# LocalPDF

**Private PDF Tools - 100% Offline**

Your documents deserve privacy. LocalPDF compresses, merges, splits, protects, watermarks, converts, and OCRs PDFs entirely on your Mac. No cloud. No uploads. No compromise.

## Why LocalPDF?

- **100% Offline** - Your files never leave your device
- **No Accounts** - No sign-up, no API keys, no tracking
- **Free Forever** - MIT licensed, open source
- **Fast & Efficient** - Native performance with PyMuPDF

## Features

### PDF Tools
- **Compress PDF** - Reduce file size while maintaining quality
- **Batch Compress** - Process multiple PDFs at once
- **Merge PDFs** - Combine multiple files into one
- **Split PDF** - Extract pages or split into separate files
- **Protect / Unlock** - Add or remove password protection (AES-256 encryption)
- **Watermark** - Add text or image watermarks to any PDF

### Convert
- **Image to PDF** - Convert images (JPG, PNG, etc.) to PDF
- **PDF to Image** - Export PDF pages as PNG or JPEG (72-600 DPI)
- **Convert PPT** - Convert PowerPoint presentations to PDF

### AI Tools
- **OCR (Scan to Text)** - Extract text from scanned PDFs and images using Tesseract OCR
  - Extract text for copy/paste
  - Create searchable PDFs with invisible text layer
  - Multi-language support
- **Dark Mode** - Comfortable use day and night

## Quick Start

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

4. Install Tesseract OCR (for text recognition):
   ```bash
   # macOS
   brew install tesseract

   # Ubuntu/Debian
   sudo apt install tesseract-ocr

   # Windows - download from:
   # https://github.com/UB-Mannheim/tesseract/wiki
   ```

5. Run LocalPDF:
   ```bash
   python main.py
   ```

## Requirements

- macOS 11.0 or later (Windows/Linux coming soon)
- Python 3.9+
- 4GB RAM minimum
- Tesseract OCR (for OCR features)
- LibreOffice (for PPT conversion)

## Project Structure

```
LocalPDF/
├── main.py                 # Application entry point
├── ui/                     # User interface components
│   ├── main_window.py      # Main application window
│   ├── compress_widget.py  # Single file compression
│   ├── batch_compress_widget.py  # Batch compression
│   ├── merge_widget.py     # PDF merging
│   ├── split_widget.py     # PDF splitting
│   ├── protect_widget.py   # Password protect/unlock
│   ├── watermark_widget.py # Watermark addition
│   ├── image_to_pdf_widget.py  # Image conversion
│   ├── pdf_to_image_widget.py  # PDF export to images
│   ├── convert_widget.py   # PPT conversion
│   ├── ocr_widget.py       # OCR text recognition
│   ├── settings_widget.py  # App settings
│   └── theme.py            # Theme management
├── core/                   # Core functionality
│   ├── compressor.py       # PDF compression engine
│   ├── merger.py           # PDF merging logic
│   ├── splitter.py         # PDF splitting logic
│   ├── protector.py        # PDF encryption/decryption
│   ├── watermark.py        # Watermark engine
│   ├── converter.py        # Format conversion
│   ├── image_to_pdf.py     # Image to PDF conversion
│   ├── pdf_to_image.py     # PDF to Image conversion
│   ├── ocr.py              # OCR engine (Tesseract)
│   └── utils.py            # Shared utilities
└── workers/                # Background processing
```

## Technology

LocalPDF is built with:

- **PyQt6** - Cross-platform native UI
- **PyMuPDF** - Fast PDF manipulation
- **Pillow** - Image processing
- **ReportLab** - PDF generation
- **Tesseract OCR** - Offline text recognition

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
