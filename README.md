# Dawnbreak Encryption Tool

A cross-platform desktop GUI app (tkinter) for AES file/folder encryption using Python's `cryptography` library (Fernet/PBKDF2).

## Commands

```bash
# Run the app
.venv/Scripts/python main.py        # Windows
.venv/bin/python main.py             # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Build standalone executable (Windows)
pyinstaller --onefile --noconsole --add-data "fonts;fonts" main.py

# Build standalone executable (Linux/macOS — note colon separator)
pyinstaller --onefile --noconsole --add-data "fonts:fonts" main.py
```

There are no automated tests. Use `test_folder/` for manual encrypt/decrypt testing.

## Architecture

**Two-file core:**
- `encrypter.py` — Pure encryption logic, no GUI. All functions accept optional `progress_callback` and `do_secure_delete` params. Encryption pipeline: password → PBKDF2-HMAC-SHA256 (100k iterations) + random salt → Fernet key → AES-CBC + HMAC. Folders are zipped before encryption. File format: `salt (16 bytes) + fernet token`.
- `main.py` — Tkinter GUI app. All encryption runs in background threads via `threading.Thread` with `self.after()` for thread-safe UI updates. Themes (DARK/LIGHT dicts) are applied recursively to all child widgets.

**Key design patterns:**
- `encrypter.py` is GUI-agnostic — it can be used standalone or from CLI
- Progress callbacks use `(percent: int, message: str)` signature
- Cross-platform font loading in `_load_fonts()` uses platform-specific APIs (Windows `AddFontResourceExW`, macOS `~/Library/Fonts`, Linux `~/.local/share/fonts`)
- `tkinterdnd2` for drag-and-drop is optional — app degrades gracefully if not installed

**Persistent files (generated at runtime):**
- `config.json` — last browsed directory
- `dawnbreak.log` — operation log (timestamp, operation, file, status)

## Conventions

- App title is "Dawnbreak Encryption Tool"
- Fonts: Cinzel family from `fonts/` directory (Bold, SemiBold, Medium, Regular are used; Black and ExtraBold are unused)
- Encrypted files use `.locked` extension
- The `verify_file()` function checks integrity without writing output — it decrypts in memory and discards the result
