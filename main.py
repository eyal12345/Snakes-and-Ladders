"""Entry point: run `python main.py` to start Snakes and Ladders."""

import os
import sys
import tkinter as tk

from gui import SnakesAndLaddersApp

ICON_FILE = "snake.ico"


def resource_path(name):
    """Locate a bundled file both when running from source and from the PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def main():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f"Unable to open the game window: {error}", file=sys.stderr)
        return 1
    try:
        # default= also applies the icon to every dialog window (Settings, History Matches).
        root.iconbitmap(default=resource_path(ICON_FILE))
    except tk.TclError:
        pass  # icon is cosmetic; run without it if missing
    SnakesAndLaddersApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
