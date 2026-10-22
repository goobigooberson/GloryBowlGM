# setup_check.py
# Step 1 test: confirms Python and NiceGUI are installed correctly.
# Run it from the VS Code terminal with:   python setup_check.py

import sys

print("=" * 50)
print("  Glory Bowl GM - Setup Check")
print("=" * 50)

# 1. Python version
major, minor = sys.version_info.major, sys.version_info.minor
print(f"Python version: {major}.{minor}.{sys.version_info.micro}")

if (major, minor) < (3, 10):
    print("PROBLEM: Python is too old. Install Python 3.13 from python.org.")
else:
    print("OK: Python version is good.")

# 2. NiceGUI (the screens toolkit)
try:
    import nicegui
    print(f"OK: NiceGUI is installed (version {nicegui.__version__}).")
except ImportError:
    print("PROBLEM: NiceGUI is not installed.")
    print("Fix: type this in the terminal and press Enter:")
    print("     python -m pip install -r requirements.txt")

# 3. SQLite (the database, built into Python)
try:
    import sqlite3
    print(f"OK: SQLite database is available (version {sqlite3.sqlite_version}).")
except ImportError:
    print("PROBLEM: SQLite is missing. Reinstall Python from python.org.")

print("=" * 50)
print("If every line above says OK, you're ready for Step 2.")
