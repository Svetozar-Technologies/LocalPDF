# LocalPDF

**Private PDF Tools - 100% Offline**

Your documents deserve privacy. LocalPDF compresses, merges, splits, and converts PDFs entirely on your Mac. No cloud. No uploads. No compromise.

## Why LocalPDF?

- **100% Offline** - Your files never leave your device
- **No Accounts** - No sign-up, no API keys, no tracking
- **Free Forever** - MIT licensed, open source
- **Fast & Efficient** - Native performance with PyMuPDF

## Features

- **Compress PDF** - Reduce file size while maintaining quality
- **Batch Compress** - Process multiple PDFs at once
- **Merge PDFs** - Combine multiple files into one
- **Split PDF** - Extract pages or split into separate files
- **Image to PDF** - Convert images (JPG, PNG, etc.) to PDF
- **Convert PPT** - Convert PowerPoint presentations to PDF
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

4. Run LocalPDF:
   ```bash
   python main.py
   ```

## Requirements

- macOS 11.0 or later (Windows/Linux coming soon)
- Python 3.9+
- 4GB RAM minimum

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
│   ├── image_to_pdf_widget.py  # Image conversion
│   ├── convert_widget.py   # PPT conversion
│   ├── settings_widget.py  # App settings
│   └── theme.py            # Theme management
├── core/                   # Core functionality
│   ├── compressor.py       # PDF compression engine
│   ├── merger.py           # PDF merging logic
│   ├── splitter.py         # PDF splitting logic
│   ├── converter.py        # Format conversion
│   ├── image_to_pdf.py     # Image to PDF conversion
│   └── utils.py            # Shared utilities
└── workers/                # Background processing
```

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
