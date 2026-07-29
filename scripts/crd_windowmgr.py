# ------------------------------------------------------------------------
"""
crd_windowmgr Holds last know position of the window
Version 2.00 Updated 07/28/26
"""
# ------------------------------------------------------------------------
import json
import os
from pathlib import Path
# ------------------------------------------------------------------------
class WindowPosition:
    def __init__(self, config_path: str = "../config/settings.html"):
        self.config_path = Path(config_path)
        self.default_x = 10
        self.default_y = 10
# ------------------------------------------------------------------------
    def load(self) -> tuple[int, int]:
        try:
            if not self.config_path.exists():
                return self.default_x, self.default_y

            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            win = data.get("window", {})
            x = int(win.get("windowx", self.default_x))
            y = int(win.get("windowy", self.default_y))
            return x, y
        except Exception:
            return self.default_x, self.default_y
# ------------------------------------------------------------------------
    def save(self, x: int, y: int) -> None:
        try:
            data = {}
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            data.setdefault("window", {})
            data["window"]["windowx"] = str(x)
            data["window"]["windowy"] = str(y)
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            return
