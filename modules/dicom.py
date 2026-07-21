# -------------------------------------------------------------
# DICOM Header Viewer (ew)
# -------------------------------------------------------------
import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QSplitter, QTreeView, QFileSystemModel, QMenu, QFrame
)
from PyQt5.QtCore import Qt, QDir, QModelIndex
from PyQt5.QtGui import QPalette, QColor, QPixmap
import stylesheets
# -------------------------------------------------------------
class DICOMHeaderViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DHV")
        self.setGeometry(100, 100, 1400, 920)
        self.current_folder = None
        self.dicom_files = []
        self.init_ui()

        stylesheets.apply_dark_theme(self)
        app = QApplication.instance()
        if app:
            stylesheets.apply_dark_theme(app)
# -------------------------------------------------------------
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 4)

        btn_browse = QPushButton("Browse Folder")
        btn_browse.clicked.connect(self.browse_folder)
        btn_browse.setMinimumWidth(120)

        self.folder_label = QLabel("No Folder Selected")
        self.folder_label.setMinimumWidth(500)

        self.btn_copy_csv = QPushButton("Copy as CSV")
        self.btn_copy_csv.clicked.connect(self.copy_header_as_csv)
        self.btn_copy_csv.setEnabled(False)
        self.btn_copy_csv.setMinimumWidth(110)

        self.btn_copy_header = QPushButton("Copy as TXT")
        self.btn_copy_header.clicked.connect(self.copy_header_to_clipboard)
        self.btn_copy_header.setEnabled(False)
        self.btn_copy_header.setMinimumWidth(110)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_current_folder)
        btn_refresh.setMinimumWidth(90)

        top_layout.addWidget(btn_browse)
        top_layout.addSpacing(12)
        #top_layout.addWidget(QLabel("Current Folder"))
        top_layout.addWidget(self.folder_label)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_copy_csv)
        top_layout.addWidget(self.btn_copy_header)
        top_layout.addWidget(btn_refresh)

        main_layout.addLayout(top_layout)
        main_splitter = QSplitter(Qt.Horizontal)
        left_splitter = QSplitter(Qt.Vertical)

        explorer_widget = QWidget()
        explorer_layout = QVBoxLayout(explorer_widget)
        explorer_layout.setContentsMargins(0, 0, 0, 0)

        label_explorer = QLabel("File Explorer")
        label_explorer.setStyleSheet("color: #CCCCCC; font-weight: bold;")
        explorer_layout.addWidget(label_explorer)

        self.file_explorer = QTreeView()
        self.file_model = QFileSystemModel()
        self.file_model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot | QDir.AllDirs)
        self.file_explorer.setModel(self.file_model)
        self.file_explorer.setColumnWidth(0, 280)
        self.file_explorer.doubleClicked.connect(self.on_explorer_double_clicked)
        explorer_layout.addWidget(self.file_explorer)
        left_splitter.addWidget(explorer_widget)

# HEADER 
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        files_layout.setContentsMargins(0, 0, 0, 0)

        files_header = QHBoxLayout()
        files_header.addWidget(QLabel("DICOM Files (.dcm / DICOMDIR)"))
        files_header.addStretch()
        self.lbl_file_count = QLabel("0 files")
        files_header.addWidget(self.lbl_file_count)
        files_layout.addLayout(files_header)

        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.show_file_header)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_list_context_menu)
        files_layout.addWidget(self.file_list)
        left_splitter.addWidget(files_widget)
        left_splitter.setSizes([500, 380])

        main_splitter.addWidget(left_splitter)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        header_header = QHBoxLayout()
        label_header = QLabel("DICOM Header")
        label_header.setStyleSheet("color: #CCCCCC; font-weight: bold;")
        header_header.addWidget(label_header)
        header_header.addStretch()
        right_layout.addLayout(header_header)

        self.header_tree = QTreeWidget()
        self.header_tree.setHeaderLabels(["Tag", "Name", "VR", "Value"])
        self.header_tree.setColumnWidth(0, 140)
        self.header_tree.setColumnWidth(1, 340)
        self.header_tree.setColumnWidth(2, 70)
        self.header_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.header_tree.customContextMenuRequested.connect(self.show_header_context_menu)
        right_layout.addWidget(self.header_tree)

        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([600, 800])
        main_layout.addWidget(main_splitter)

# FOOTER
        footer_frame = QFrame()
        footer_frame.setFixedHeight(40)
        footer_frame.setFrameShape(QFrame.NoFrame)          

        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(8, 4, 8, 4)

        logo_path = Path(__file__).parent / "canon.png"   
        self.logo_label = QLabel()

        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaledToHeight(32, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pixmap)
        else:
            self.logo_label.setText("")
            self.logo_label.setStyleSheet("color: #CCCCCC; font-style: italic;")

        self.logo_label.setFixedWidth(400)
        self.logo_label.setStyleSheet("border: none; background: transparent;")
        footer_layout.addWidget(self.logo_label)
        footer_layout.addStretch()

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self.clear_all)
        btn_clear.setMinimumWidth(90)
        footer_layout.addWidget(btn_clear)
        main_layout.addWidget(footer_frame)
        self.statusBar().showMessage("Ready")
# -------------------------------------------------------------
    def clear_all(self):
        self.current_folder = None
        self.folder_label.setText("No Folder Selected")
        self.file_list.clear()
        self.dicom_files = []
        self.lbl_file_count.setText("0 files")
        self.header_tree.clear()
        self.btn_copy_header.setEnabled(False)
        self.btn_copy_csv.setEnabled(False)
        self.file_model.setRootPath("")
        self.file_explorer.setRootIndex(QModelIndex())
        self.statusBar().showMessage("Ready")
# -------------------------------------------------------------
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select DICOM Folder", str(self.current_folder) if self.current_folder else "C:\\"
        )
        if folder:
            self.load_folder(Path(folder))
# -------------------------------------------------------------
    def refresh_current_folder(self):
        if self.current_folder:
            self.load_folder(self.current_folder)
# -------------------------------------------------------------
    def load_folder(self, folder_path: Path):
        self.current_folder = folder_path
        self.folder_label.setText(str(folder_path))
        self.file_model.setRootPath(str(folder_path))
        self.file_explorer.setRootIndex(self.file_model.index(str(folder_path)))
        self.load_dicom_files()
        self.statusBar().showMessage(f"Loaded folder: {folder_path}")
# -------------------------------------------------------------
    def on_explorer_double_clicked(self, index):
        path = Path(self.file_model.filePath(index))
        if path.is_dir():
            self.load_folder(path)
        elif path.is_file() and (self.is_likely_dicom(path) or path.suffix.lower() == ".dcm"):
            self.show_file_header_from_path(path)
# -------------------------------------------------------------
    def load_dicom_files(self):
        self.file_list.clear()
        self.dicom_files = []
        if not self.current_folder:
            return
        try:
            for entry in os.scandir(self.current_folder):
                if entry.is_dir():
                    continue
                filepath = Path(entry.path)
                filename = entry.name
                is_candidate = (filename.lower().endswith(".dcm") or "." not in filename or filename.upper() == "DICOMDIR")
                if is_candidate and (self.is_likely_dicom(filepath) or filename.lower().endswith(".dcm")):
                    self.dicom_files.append(filename)
                    self.file_list.addItem(filename)
            self.lbl_file_count.setText(f"{len(self.dicom_files)} files")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to scan folder:\n{str(e)}")
# -------------------------------------------------------------
    def is_likely_dicom(self, filepath: Path) -> bool:
        try:
            with open(filepath, "rb") as f:
                f.seek(128)
                return f.read(4) == b"DICM"
        except:
            return False
# -------------------------------------------------------------
    def show_file_header(self, item):
        filepath = self.current_folder / item.text()
        self._load_and_display_header(filepath)
# -------------------------------------------------------------
    def show_file_header_from_path(self, filepath: Path):
        for i in range(self.file_list.count()):
            if self.file_list.item(i).text() == filepath.name:
                self.file_list.setCurrentRow(i)
                break
        self._load_and_display_header(filepath)
# -------------------------------------------------------------
    def _load_and_display_header(self, filepath: Path):
        self.header_tree.clear()
        self.btn_copy_header.setEnabled(False)
        self.btn_copy_csv.setEnabled(False)
        try:
            import pydicom
            ds = pydicom.dcmread(filepath, force=True)

            top = QTreeWidgetItem(self.header_tree, ["FILE INFORMATION", "", "", ""])
            QTreeWidgetItem(top, ["Filename", "", "", filepath.name])
            QTreeWidgetItem(top, ["Full Path", "", "", str(filepath)])
            QTreeWidgetItem(top, ["File Size", "", "", f"{filepath.stat().st_size:,} bytes"])
            top.setExpanded(True)

            for elem in ds:
                self.add_dicom_element(self.header_tree, elem)

            self.header_tree.expandToDepth(1)
            self.btn_copy_header.setEnabled(True)
            self.btn_copy_csv.setEnabled(True)
            self.statusBar().showMessage(f"Loaded: {filepath.name}")
        except Exception as e:
            QTreeWidgetItem(self.header_tree, ["ERROR", "", "", str(e)])
# -------------------------------------------------------------
    def add_dicom_element(self, parent, elem):
        tag = f"({elem.tag.group:04X},{elem.tag.element:04X})"
        name = getattr(elem, "name", "Unknown")
        vr = getattr(elem, "VR", "")
        if elem.VR == "SQ" and hasattr(elem, "value"):
            item = QTreeWidgetItem(parent, [tag, name, vr, f"Sequence ({len(elem.value)} items)"])
            for i, sub_ds in enumerate(elem.value):
                sub_item = QTreeWidgetItem(item, [f"Item {i+1}", "", "", ""])
                for sub_elem in sub_ds:
                    self.add_dicom_element(sub_item, sub_elem)
        else:
            value = str(elem.value)
            if len(value) > 300:
                value = value[:297] + "..."
            QTreeWidgetItem(parent, [tag, name, vr, value])
# -------------------------------------------------------------
    def copy_header_to_clipboard(self):
        if self.header_tree.topLevelItemCount() == 0:
            return
        text = self._tree_widget_to_text(self.header_tree.invisibleRootItem())
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("Header Copied to Clipboard", 3000)
# -------------------------------------------------------------
    def copy_header_as_csv(self):
        if self.header_tree.topLevelItemCount() == 0:
            return
        import csv
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Tag", "Name", "VR", "Value"])
        self._tree_to_csv_rows(self.header_tree.invisibleRootItem(), writer)
        QApplication.clipboard().setText(output.getvalue())
        self.statusBar().showMessage("Header copied as CSV", 3000)
# -------------------------------------------------------------
    def _tree_to_csv_rows(self, item, writer, path_prefix=""):
        for i in range(item.childCount()):
            child = item.child(i)
            tag = child.text(0)
            name = child.text(1)
            vr = child.text(2)
            value = child.text(3).replace("\n", " ").replace("\r", " ")
            current_path = f"{path_prefix} > {name}" if path_prefix else name
            if tag.startswith("Item ") or tag.startswith("FILE INFORMATION"):
                current_path = name or tag
            writer.writerow([tag, current_path, vr, value])
            if child.childCount() > 0:
                self._tree_to_csv_rows(child, writer, current_path)
# -------------------------------------------------------------
    def _tree_widget_to_text(self, item, indent=0):
        lines = []
        for i in range(item.childCount()):
            child = item.child(i)
            prefix = "  " * indent
            line = f"{prefix}{child.text(0)}  {child.text(1)}  [{child.text(2)}]  {child.text(3)}".strip()
            if line:
                lines.append(line)
            if child.childCount() > 0:
                lines.append(self._tree_widget_to_text(child, indent + 1))
        return "\n".join(lines)
# -------------------------------------------------------------
    def show_file_list_context_menu(self, position):
        item = self.file_list.itemAt(position)
        if not item:
            return
        menu = QMenu()
        menu.addAction("Copy Filename", lambda: QApplication.clipboard().setText(item.text()))
        menu.addAction("Show Header", lambda: self.show_file_header(item))
        menu.exec_(self.file_list.mapToGlobal(position))
# -------------------------------------------------------------
    def show_header_context_menu(self, position):
        menu = QMenu()
        menu.addAction("Copy Header to Clipboard", self.copy_header_to_clipboard)
        menu.addAction("Copy as CSV (for Excel)", self.copy_header_as_csv)
        menu.addSeparator()
        menu.addAction("Expand All", self.header_tree.expandAll)
        menu.addAction("Collapse All", self.header_tree.collapseAll)
        menu.exec_(self.header_tree.mapToGlobal(position))
# -------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = DICOMHeaderViewer()
    viewer.show()
    sys.exit(app.exec_())
# -------------------------------------------------------------
