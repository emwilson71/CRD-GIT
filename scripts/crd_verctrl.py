# ---------------------------------------------------------------------------
"""
crd_verctrl.py
PyQt6
Version 1.00 Updated 07/21/26
"""
# ---------------------------------------------------------------------------
import sys
import os
import re
import ast
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QFileDialog, QMessageBox, QHeaderView, QAbstractItemView,
    QDialog, QTextEdit, QDialogButtonBox, QStatusBar, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPalette, QBrush

try:
    from crd_embedded import Styles
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from crd_embedded import Styles
# ---------------------------------------------------------------------------
HEADER_RE = re.compile(
    r'Version\s+(\d+\.\d+)\s*-?\s*Updated\s+(\d{2}/\d{2}/\d{2})',
    re.IGNORECASE
)
# ---------------------------------------------------------------------------
def parse_version_info(filepath: str) -> tuple:
    version = "—"
    updated = "—"
    snippet = ""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= 40:
                    break
                lines.append(line)
            content = "".join(lines)
            snippet = content[:500]
        try:
            tree = ast.parse(content)
            doc = ast.get_docstring(tree)
            if doc:
                m = HEADER_RE.search(doc)
                if m:
                    return m.group(1), m.group(2), doc[:300]
        except Exception:
            pass
        m = HEADER_RE.search(content)
        if m:
            version = m.group(1)
            updated = m.group(2)
    except Exception as e:
        snippet = f"<Error Reading File {e}>"
    return version, updated, snippet
# ---------------------------------------------------------------------------
def bump_version(ver_str: str) -> str:
    try:
        major, minor = ver_str.split(".")
        major = int(major)
        minor = int(minor)
        minor += 1
        if minor >= 100:
            major += 1
            minor = 0
        return f"{major}.{minor:02d}"
    except Exception:
        return "1.00"
# ---------------------------------------------------------------------------
def today_str() -> str:
    return datetime.now().strftime("%m/%d/%y")
# ---------------------------------------------------------------------------
def update_file_header(filepath: str, new_version: str, new_date: str) -> bool:
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        patterns = [
            (re.compile(
                r'(Version\s+)\d+\.\d+(\s*-?\s*Updated\s+)\d{2}/\d{2}/\d{2}',
                re.IGNORECASE
            ), rf'\g<1>{new_version}\g<2>{new_date}'),
            (re.compile(
                r'(Version\s*:\s*)\d+\.\d+(\s+Updated\s*:\s*)\d{2}/\d{2}/\d{2}',
                re.IGNORECASE
            ), rf'\g<1>{new_version}\g<2>{new_date}'),
        ]
        new_content = content
        replaced = False
        for pat, repl in patterns:
            if pat.search(new_content):
                new_content = pat.sub(repl, new_content, count=1)
                replaced = True
                break
        if not replaced:
            m = re.search(
                r'^((?:#!.*\n)?(?:#.*coding[:=].*\n)?)(\s*)("""|\'\'\')',
                new_content,
                re.MULTILINE,
            )
            if m:
                insert_pos = m.end()
                header_line = f"\nVersion {new_version} Updated {new_date}\n"
                new_content = new_content[:insert_pos] + header_line + new_content[insert_pos:]
                replaced = True
            else:
                m2 = re.match(
                    r'^((?:#!.*\n)?(?:#.*coding[:=].*\n)?)',
                    new_content,
                )
                prefix = m2.group(1) if m2 else ""
                rest = new_content[len(prefix):]
                basename = os.path.basename(filepath)
                new_doc = (
                    f'{prefix}"""\n'
                    f'{basename}\n'
                    f'Version {new_version} Updated {new_date}\n'
                    f'"""\n\n'
                )
                new_content = new_doc + rest.lstrip("\n")
                replaced = True
        if not replaced:
            return False
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
        return True
    except Exception:
        return False
# ---------------------------------------------------------------------------
def collect_scripts(root: str, recursive: bool = True) -> list:
    root_path = Path(root).resolve()
    results = []
    skip_dirs = {
        "__pycache__", ".git", ".svn", ".hg", ".bzr",
        "venv", ".venv", "env", ".env",
        "node_modules", "site-packages", "dist", "build",
        ".idea", ".vscode", "__pypackages__"
    }
# ---------------------------------------------------------------------------
    def should_skip(p: Path) -> bool:
        return any(part in skip_dirs for part in p.parts)

    if recursive:
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for name in filenames:
                if name.lower().endswith((".py", ".pyw")):
                    full = Path(dirpath) / name
                    if should_skip(full):
                        continue
                    rel = full.relative_to(root_path)
                    ver, upd, snip = parse_version_info(str(full))
                    results.append({
                        "path": str(full),
                        "rel": str(rel).replace("\\", "/"),
                        "name": name,
                        "version": ver,
                        "updated": upd,
                        "snippet": snip,
                    })
    else:
        for name in os.listdir(root_path):
            full = root_path / name
            if full.is_file() and name.lower().endswith((".py", ".pyw")):
                ver, upd, snip = parse_version_info(str(full))
                results.append({
                    "path": str(full),
                    "rel": name,
                    "name": name,
                    "version": ver,
                    "updated": upd,
                    "snippet": snip,
                })
    results.sort(key=lambda x: x["rel"].lower())
    return results
# ---------------------------------------------------------------------------
class FileEditorDialog(QDialog):
    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setWindowTitle(f"Edit — {os.path.basename(filepath)}")
        self.resize(900, 700)
        self.setStyleSheet(Styles.POPUP_DIALOG + Styles.TEXT_EDIT_STYLE)
        layout = QVBoxLayout(self)
        info = QLabel(filepath)
        info.setStyleSheet(Styles.STD_LABEL_STYLE)
        info.setWordWrap(True)
        layout.addWidget(info)
        self.editor = QTextEdit()
        self.editor.setStyleSheet(Styles.TEXT_EDIT_STYLE)
        self.editor.setFont(QFont("Consolas", 11))
        self.editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setStyleSheet(Styles.BUTTON_STYLE)
        buttons.accepted.connect(self.save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._load()
# ---------------------------------------------------------------------------
    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
                self.editor.setPlainText(f.read())
        except Exception as e:
            self.editor.setPlainText(f"# ERROR Loading File\n# {e}")
# ---------------------------------------------------------------------------
    def save_and_accept(self):
        try:
            with open(self.filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.editor.toPlainText())
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
# ---------------------------------------------------------------------------
class VersionControlWindow(QMainWindow):
    def __init__(self, initial_root: str = None):
        super().__init__()
        self.setWindowTitle("CRD Version Control")
        self.resize(700, 400)
        self.setMinimumSize(700, 600)
        self.root_dir = initial_root or os.getcwd()
        self.recursive = True
        self.scripts = []
        self._build_ui()
        self._apply_styles()
        self.refresh()
# ---------------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        path_row = QHBoxLayout()
        path_label = QLabel("Root:")
        path_label.setStyleSheet(Styles.STD_LABEL_STYLE)
        path_row.addWidget(path_label)
        self.path_edit = QLineEdit(self.root_dir)
        self.path_edit.setStyleSheet(Styles.LINE_EDIT_STYLE)
        self.path_edit.setReadOnly(True)
        path_row.addWidget(self.path_edit, 1)

        btn_browse = QPushButton("Browse…")
        btn_browse.setStyleSheet(Styles.BUTTON_STYLE)
        btn_browse.setFixedWidth(90)
        btn_browse.clicked.connect(self.browse_root)
        path_row.addWidget(btn_browse)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setStyleSheet(Styles.BUTTON_STYLE)
        btn_refresh.setFixedWidth(90)
        btn_refresh.clicked.connect(self.refresh)
        path_row.addWidget(btn_refresh)

        self.chk_recursive = QCheckBox("Recursive")
        self.chk_recursive.setChecked(True)
        self.chk_recursive.setStyleSheet("color: white; font-weight: bold;")
        self.chk_recursive.stateChanged.connect(self._on_recursive_changed)
        path_row.addWidget(self.chk_recursive)
        main_layout.addLayout(path_row)

        title = QLabel("Python Script Table")
        title.setStyleSheet(Styles.DYNAMIC_HEADER_STYLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["File", "Version", "Updated", ""])
        self.table.setStyleSheet(getattr(Styles, "TABLE_STYLE", ""))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 50)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        main_layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.lbl_count = QLabel("0 scripts")
        self.lbl_count.setStyleSheet(Styles.STD_LABEL_STYLE)
        bottom.addWidget(self.lbl_count)
        bottom.addStretch()

        btn_edit = QPushButton("Edit Selected")
        btn_edit.setStyleSheet(Styles.BUTTON_STYLE)
        btn_edit.clicked.connect(self.edit_selected)
        bottom.addWidget(btn_edit)
        main_layout.addLayout(bottom)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")
# ---------------------------------------------------------------------------
    def _apply_styles(self):
        base = getattr(Styles, "MAIN_WINDOW_STYLE", "") + getattr(Styles, "WIDGET_STYLE", "")
        self.setStyleSheet(base)
# ---------------------------------------------------------------------------
    def _on_recursive_changed(self, state):
        self.recursive = bool(state)
        self.refresh()
# ---------------------------------------------------------------------------
    def browse_root(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Root Directory of Scripts", self.root_dir
        )
        if d:
            self.root_dir = d
            self.path_edit.setText(d)
            self.refresh()
# ---------------------------------------------------------------------------
    def refresh(self):
        self.status.showMessage("Scanning…")
        QApplication.processEvents()
        self.scripts = collect_scripts(self.root_dir, recursive=self.recursive)
        self._populate_table()
        self.lbl_count.setText(f"{len(self.scripts)} script{'s' if len(self.scripts) != 1 else ''}")
        self.status.showMessage(f"Loaded {len(self.scripts)} Scripts From {self.root_dir}")
# ---------------------------------------------------------------------------
    def _populate_table(self):
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.scripts))
        plus_style = getattr(Styles, "PLUS_BUTTON_STYLE", Styles.BUTTON_STYLE)
        for row, info in enumerate(self.scripts):
            item_file = QTableWidgetItem(info["rel"])
            item_file.setData(Qt.ItemDataRole.UserRole, info["path"])
            tip = info["path"]
            if info["snippet"]:
                tip += "\n\n" + info["snippet"][:200]
            item_file.setToolTip(tip)
            self.table.setItem(row, 0, item_file)

            item_ver = QTableWidgetItem(info["version"])
            item_ver.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if info["version"] == "—":
                item_ver.setForeground(QBrush(QColor("#888888")))
            self.table.setItem(row, 1, item_ver)

            item_upd = QTableWidgetItem(info["updated"])
            item_upd.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if info["updated"] == "—":
                item_upd.setForeground(QBrush(QColor("#888888")))
            self.table.setItem(row, 2, item_upd)

            btn = QPushButton("+")
            btn.setStyleSheet(plus_style)
            btn.setToolTip("Bump Version, Update Date, Then Open Editor")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, r=row: self._on_plus_clicked(r))
            self.table.setCellWidget(row, 3, btn)
            self.table.setRowHeight(row, 34)
# ---------------------------------------------------------------------------
    def _get_selected_row(self) -> int:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            r = self.table.currentRow()
            return r if r >= 0 else -1
        return rows[0].row()
# ---------------------------------------------------------------------------
    def _on_plus_clicked(self, row: int):
        if 0 <= row < len(self.scripts):
            self._bump_and_edit(self.scripts[row]["path"], row)
# ---------------------------------------------------------------------------
    def _on_double_click(self, row: int, col: int):
        if col != 3 and 0 <= row < len(self.scripts):
            self._open_editor(self.scripts[row]["path"])
# ---------------------------------------------------------------------------
    def bump_selected(self):
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.information(self, "No Selection", "Select a Row")
            return
        self._bump_only(self.scripts[row]["path"], row)
# ---------------------------------------------------------------------------
    def edit_selected(self):
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.information(self, "No Selection", "Select a Row")
            return
        self._open_editor(self.scripts[row]["path"])
# ---------------------------------------------------------------------------
    def _bump_only(self, filepath: str, row: int):
        ver, _, _ = parse_version_info(filepath)
        new_ver = "1.00" if ver == "—" else bump_version(ver)
        new_date = today_str()
        if not update_file_header(filepath, new_ver, new_date):
            QMessageBox.warning(
                self, "Update Failed",
                f"Could Not Update Header in:\n{filepath}\n\n"
                "Expected a Line \nVersion 1.00 Updated 07/17/26"
            )
            return
        new_ver2, new_upd2, snip = parse_version_info(filepath)
        self.scripts[row]["version"] = new_ver2
        self.scripts[row]["updated"] = new_upd2
        self.scripts[row]["snippet"] = snip
        self.table.item(row, 1).setText(new_ver2)
        self.table.item(row, 1).setForeground(QBrush(QColor("white")))
        self.table.item(row, 2).setText(new_upd2)
        self.table.item(row, 2).setForeground(QBrush(QColor("white")))
        self.status.showMessage(f"Bumped {os.path.basename(filepath)} → {new_ver2} ({new_upd2})")
# ---------------------------------------------------------------------------
    def _bump_and_edit(self, filepath: str, row: int):
        self._bump_only(filepath, row)
        self._open_editor(filepath)
        if 0 <= row < len(self.scripts):
            ver, upd, snip = parse_version_info(filepath)
            self.scripts[row]["version"] = ver
            self.scripts[row]["updated"] = upd
            self.scripts[row]["snippet"] = snip
            self.table.item(row, 1).setText(ver)
            self.table.item(row, 2).setText(upd)
# ---------------------------------------------------------------------------
    def _open_editor(self, filepath: str):
        dlg = FileEditorDialog(filepath, self)
        dlg.exec()
# ---------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(32, 32, 32))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(32, 32, 32))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(48, 48, 48))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(32, 32, 32))
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(96, 96, 96))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Highlight, QColor(64, 64, 64))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    app.setPalette(palette)

    root = None
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        root = sys.argv[1]
    win = VersionControlWindow(initial_root=root)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
# ---------------------------------------------------------------------------