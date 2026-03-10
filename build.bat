pyinstaller --onefile --noconsole --add-data "fonts;fonts" main.py
wsl bash -c "cd $(wslpath '%cd%') && source .venv/bin/activate && pyinstaller --onefile --noconsole --add-data 'fonts:fonts' main.py"