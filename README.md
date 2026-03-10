# Dawnbreak Encryption Tool

A cross-platform desktop app for encrypting and decrypting files and folders with AES-256, built with Python and Tkinter.

![Python](https://img.shields.io/badge/Python-3.x-blue)
![License](https://img.shields.io/badge/License-Unlicense-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

## Features

- **AES-256 encryption** via Fernet (AES-CBC + HMAC) with PBKDF2-HMAC-SHA256 key derivation (100k iterations)
- **File and folder encryption** — folders are compressed to ZIP before encrypting
- **Secure deletion** — multi-pass overwrite of original files after encryption
- **Drag-and-drop** support (optional, via `tkinterdnd2`)
- **Dark and light themes**
- **Password strength meter** with real-time feedback
- **Verify** encrypted files without decrypting to disk
- **Batch operations** — encrypt or decrypt multiple items at once
- **Standalone executables** — build with PyInstaller for any platform

## Getting Started

### Prerequisites

- Python 3.x
- pip

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
# Windows
python main.py

# macOS / Linux
python3 main.py
```

### Build Standalone Executable

```bash
# Windows
pyinstaller --onefile --noconsole --add-data "fonts;fonts" main.py

# macOS / Linux
pyinstaller --onefile --noconsole --add-data "fonts:fonts" main.py
```

If you're on Windows with WSL installed, run `build.bat` to compile for both Windows and Linux in one step.

## How It Works

The tool has a two-file core:

| File | Role |
|------|------|
| `encrypter.py` | Pure encryption logic — no GUI dependencies, can be used standalone or from CLI |
| `main.py` | Tkinter GUI with theming, threading, and drag-and-drop |

### Encryption Pipeline

```
Password → PBKDF2-HMAC-SHA256 (100k iterations + random salt) → Fernet key → AES-CBC + HMAC
```

Encrypted file format: `salt (16 bytes) + Fernet token`

Folders are zipped into a single archive before encryption. Encrypted files use the `.locked` extension.

### Runtime Files

The app generates these files during use (not tracked in git):

- `config.json` — remembers the last browsed directory
- `dawnbreak.log` — operation log with timestamps

## Testing

There are no automated tests. Use the `test_folder/` directory for manual encrypt/decrypt verification — it contains sample files and folders with identical text content you can modify.

## Project Structure

```
encryption_tool/
├── main.py              # GUI application
├── encrypter.py         # Encryption core (GUI-agnostic)
├── requirements.txt     # Python dependencies
├── build.bat            # Cross-compile script (Windows + WSL)
├── main.spec            # PyInstaller config
├── LICENSE              # Unlicense (public domain)
├── fonts/               # Cinzel font family
│   ├── Cinzel-Bold.ttf
│   ├── Cinzel-Medium.ttf
│   ├── Cinzel-Regular.ttf
│   ├── Cinzel-SemiBold.ttf
│   └── OFL.txt          # SIL Open Font License
└── test_folder/         # Manual test files
```

## License

This project is released into the public domain under the [Unlicense](LICENSE).

### Font License

This project includes the [Cinzel](https://github.com/NDISCOVER/Cinzel) font family, Copyright 2020 The Cinzel Project Authors. Cinzel is licensed under the [SIL Open Font License, Version 1.1](fonts/OFL.txt). The full license text is distributed with this project at `fonts/OFL.txt` as required by the OFL.
