# -------------------------------------------------------------
# DICOM Header Viewer (ew)
# Viewing and Batch Editing
# Version 1.01 Updated 07/24/26   
# -------------------------------------------------------------
import sys
import os
import time
from pathlib import Path
import shutil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QSplitter, QTreeView, QFileSystemModel, QMenu, QFrame,
    QInputDialog
)
from PyQt5.QtCore import Qt, QDir, QModelIndex
from PyQt5.QtGui import QPalette, QColor, QPixmap, QIcon
from mod_stylesheets import (
    BUTTON_STYLE,
    STD_LABEL_STYLE,
    FRAME_STYLE,
    MESSAGE_BOX_STYLE,
)
try:
    import pydicom
    from pydicom.fileset import FileSet
except ImportError:
    pydicom = None
BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "images"
LIST_TREE_STYLE = """
    QListWidget, QTreeWidget, QTreeView {
        background-color: #202020;
        color: #E0E0E0;
        border: 1px solid #606060;
        border-radius: 4px;
        outline: none;
        font-size: 12px;
    }
    QListWidget::item, QTreeWidget::item, QTreeView::item {
        padding: 3px 6px;
    }
    QListWidget::item:selected, QTreeWidget::item:selected, QTreeView::item:selected {
        background-color: #3A6EA5;
        color: #FFFFFF;
    }
    QListWidget::item:hover, QTreeWidget::item:hover, QTreeView::item:hover {
        background-color: #404040;
    }
    QHeaderView::section {
        background-color: #202020;
        color: #E0E0E0;
        padding: 4px;
        border: 1px solid #606060;
        font-weight: bold;
    }
"""
SPLITTER_STYLE = """
    QSplitter::handle {
        background-color: #404040;
    }
    QSplitter::handle:hover {
        background-color: #606060;
    }
"""
MAIN_WINDOW_STYLE = """
    QMainWindow, QWidget {
        background-color: #202020;
        color: #E0E0E0;
    }
"""

# -------------------------------------------------------------
class DICOMHeaderViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DICOM Header Viewer")
        self.setGeometry(100, 100, 1400, 920)
        self.setStyleSheet(MAIN_WINDOW_STYLE)

        icon_path = IMAGES_DIR / "dicom.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.current_folder = None
        self.dicom_files = []
        self.current_ds = None
        self.current_filepath = None
        self.is_current_dicomdir = False
        self.init_ui()

# -------------------------------------------------------------
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        top_layout = QHBoxLayout()

        self.btn_copy_csv = QPushButton("COPY as CSV")
        self.btn_copy_csv.setStyleSheet(BUTTON_STYLE)
        self.btn_copy_csv.clicked.connect(self.copy_header_as_csv)
        self.btn_copy_csv.setEnabled(False)

        self.btn_copy_header = QPushButton("COPY as TXT")
        self.btn_copy_header.setStyleSheet(BUTTON_STYLE)
        self.btn_copy_header.clicked.connect(self.copy_header_to_clipboard)
        self.btn_copy_header.setEnabled(False)

        btn_refresh = QPushButton("REFRESH")
        btn_refresh.setStyleSheet(BUTTON_STYLE)
        btn_refresh.clicked.connect(self.refresh_current_folder)

        btn_clear = QPushButton("CLEAR")
        btn_clear.setStyleSheet(BUTTON_STYLE)
        btn_clear.clicked.connect(self.clear_all)

        self.btn_save = QPushButton("SAVE CHANGES")
        self.btn_save.setStyleSheet(BUTTON_STYLE)
        self.btn_save.clicked.connect(self.save_changes)
        self.btn_save.setEnabled(False)

        top_layout.addStretch()
        top_layout.addWidget(self.btn_copy_csv)
        top_layout.addWidget(self.btn_copy_header)
        top_layout.addWidget(self.btn_save)
        top_layout.addWidget(btn_clear)
        top_layout.addWidget(btn_refresh)
        main_layout.addLayout(top_layout)

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setStyleSheet(SPLITTER_STYLE)

        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.setStyleSheet(SPLITTER_STYLE)

        explorer_widget = QWidget()
        explorer_layout = QVBoxLayout(explorer_widget)
        explorer_label = QLabel("File Explorer")
        explorer_label.setStyleSheet(STD_LABEL_STYLE)
        explorer_layout.addWidget(explorer_label)

        self.file_explorer = QTreeView()
        self.file_explorer.setStyleSheet(LIST_TREE_STYLE)
        self.file_model = QFileSystemModel()
        self.file_model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot | QDir.AllDirs)
        self.file_explorer.setModel(self.file_model)
        self.file_explorer.setColumnWidth(0, 280)
        self.file_explorer.doubleClicked.connect(self.on_explorer_double_clicked)
        self.file_model.setRootPath("")
        self.file_explorer.setRootIndex(QModelIndex())
        explorer_layout.addWidget(self.file_explorer)
        left_splitter.addWidget(explorer_widget)

        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        files_header = QHBoxLayout()
        files_label = QLabel("DICOM Files (.dcm / DICOMDIR)")
        files_label.setStyleSheet(STD_LABEL_STYLE)
        files_header.addWidget(files_label)
        files_header.addStretch()
        self.lbl_file_count = QLabel("0 files")
        self.lbl_file_count.setStyleSheet(STD_LABEL_STYLE)
        files_header.addWidget(self.lbl_file_count)
        files_layout.addLayout(files_header)

        self.file_list = QListWidget()
        self.file_list.setStyleSheet(LIST_TREE_STYLE)
        self.file_list.itemClicked.connect(self.show_file_header)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_list_context_menu)
        files_layout.addWidget(self.file_list)
        left_splitter.addWidget(files_widget)
        left_splitter.setSizes([500, 380])
        main_splitter.addWidget(left_splitter)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        header_label = QLabel("DICOM Header / Directory Structure")
        header_label.setStyleSheet(STD_LABEL_STYLE)
        right_layout.addWidget(header_label)

        self.header_tree = QTreeWidget()
        self.header_tree.setStyleSheet(LIST_TREE_STYLE)
        self.header_tree.setHeaderLabels(["Tag / Record", "Name / Type", "VR", "Value"])
        self.header_tree.setColumnWidth(0, 160)
        self.header_tree.setColumnWidth(1, 320)
        self.header_tree.setColumnWidth(2, 70)
        self.header_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.header_tree.customContextMenuRequested.connect(self.show_header_context_menu)
        self.header_tree.itemDoubleClicked.connect(self.edit_tree_item)
        right_layout.addWidget(self.header_tree)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([600, 800])
        main_layout.addWidget(main_splitter)

        footer_frame = QFrame()
        footer_frame.setFixedHeight(70)
        footer_frame.setStyleSheet(FRAME_STYLE)
        footer_layout = QHBoxLayout(footer_frame)

        logo_path = IMAGES_DIR / "canon.png"
        self.logo_label = QLabel()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path)).scaledToHeight(32, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
        footer_layout.addWidget(self.logo_label)
        footer_layout.addStretch()
        main_layout.addWidget(footer_frame)

# -------------------------------------------------------------
    def is_dicomdir(self, filepath: Path) -> bool:
        return filepath.name.upper() == "DICOMDIR"
# -------------------------------------------------------------
    def clear_all(self):
        self.current_folder = None
        self.file_list.clear()
        self.dicom_files = []
        self.lbl_file_count.setText("0 files")
        self.header_tree.clear()
        self.btn_copy_header.setEnabled(False)
        self.btn_copy_csv.setEnabled(False)
        self.file_model.setRootPath("")
        self.file_explorer.setRootIndex(QModelIndex())
# -------------------------------------------------------------
    def refresh_current_folder(self):
        if self.current_folder:
            self.load_folder(self.current_folder)
# -------------------------------------------------------------
    def load_folder(self, folder_path: Path):
        self.current_folder = folder_path
        self.file_model.setRootPath(str(folder_path))
        self.file_explorer.setRootIndex(self.file_model.index(str(folder_path)))
        self.load_dicom_files()
# -------------------------------------------------------------
    def on_explorer_double_clicked(self, index):
        path = Path(self.file_model.filePath(index))
        if path.is_dir():
            self.current_folder = path
            self.load_dicom_files()
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
            self.lbl_file_count.setText(f"{len(self.dicom_files)} Files")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to Scan Folder\n{str(e)}")
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

    def _build_dicomdir_structure(self, parent, ds):
        try:
            fs = FileSet(ds)
            for patient in fs.find(PatientID="*"):
                p_item = QTreeWidgetItem(parent, ["PATIENT", getattr(patient, 'PatientID', '?'), "", ""])
        except:
            if hasattr(ds, 'patient_records'):
                for rec in ds.patient_records:
                    QTreeWidgetItem(parent, ["PATIENT RECORD", rec.PatientID or "?", "", ""])
# -------------------------------------------------------------
    def _add_common_tags_batch(self, parent, ds):
        common_tags = {}
        if hasattr(ds, 'DirectoryRecordSequence'):
            for record in ds.DirectoryRecordSequence:
                for elem in record:
                    if elem.VR in ('SQ', 'OB', 'OW', 'UN') or elem.tag.is_private:
                        continue
                    key = (elem.tag.group, elem.tag.element)
                    if key not in common_tags:
                        common_tags[key] = []
                    common_tags[key].append((record, elem))
        sorted_tags = sorted(common_tags.items(), key=lambda x: len(x[1]), reverse=True)
        for (group, elem), occurrences in sorted_tags[:50]:
            tag_str = f"({group:04X},{elem:04X})"
            sample_elem = occurrences[0][1]
            name = getattr(sample_elem, 'name', 'Unknown')
            vr = sample_elem.VR
            value = str(sample_elem.value)[:200]
            item = QTreeWidgetItem(parent, [tag_str, name, vr, value])
            item.setData(0, Qt.UserRole, (tag_str, occurrences))
            item.setFlags(item.flags() | Qt.ItemIsEditable)
# -------------------------------------------------------------
    def _apply_batch_edits_to_dicomdir(self):
        root = self.header_tree.invisibleRootItem()
        for i in range(root.childCount()):
            batch_section = root.child(i)
            if batch_section.text(0) == "COMMON TAGS (BATCH EDIT)":
                for j in range(batch_section.childCount()):
                    item = batch_section.child(j)
                    data = item.data(0, Qt.UserRole)
                    if data and len(data) == 2:
                        tag_str, occurrences = data
                        new_value = item.text(3)
                        for record, original_elem in occurrences:
                            tag = original_elem.tag
                            if tag in record:
                                record[tag] = new_value
# -------------------------------------------------------------
    def show_dicomdir_structure(self, filepath: Path):
        top = QTreeWidgetItem(self.header_tree, ["DICOMDIR STRUCTURE", "", "", str(filepath)])
        top.setExpanded(True)
        try:
            fs = FileSet(filepath)
            for patient in fs.find(PatientID="*"):
                p_item = QTreeWidgetItem(top, ["PATIENT", patient.PatientID or "?", "", ""])
            ds = pydicom.dcmread(filepath, force=True)
            self.current_ds = ds
            raw_item = QTreeWidgetItem(top, ["RAW TAGS (below)", "", "", ""])
            for elem in ds:
                self.add_dicom_element(raw_item, elem)
        except Exception as e:
            QTreeWidgetItem(top, ["ERROR", "", "", str(e)])
# -------------------------------------------------------------
    def edit_tree_item(self, item, column):
        if column != 3:
            return
        data = item.data(0, Qt.UserRole)
        if data and isinstance(data, tuple):
            new_value, ok = QInputDialog.getText(self, "Batch Edit Tag",
                                               f"Update Value For All Matching Records:", text=item.text(3))
            if ok:
                item.setText(3, new_value)
        else:
            new_value, ok = QInputDialog.getText(self, "Edit Value", "New Value:", text=item.text(3))
            if ok:
                item.setText(3, new_value)

# -------------------------------------------------------------
    def _add_file_info(self, ds, filepath):
        top = QTreeWidgetItem(self.header_tree, ["FILE INFORMATION", "", "", ""])
        QTreeWidgetItem(top, ["Filename", "", "", filepath.name])
        QTreeWidgetItem(top, ["Full Path", "", "", str(filepath)])
        QTreeWidgetItem(top, ["File Size", "", "", f"{filepath.stat().st_size:,} bytes"])
        top.setExpanded(True)
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
        self.btn_save.setEnabled(False)
        self.current_ds = None
        self.current_filepath = filepath
        self.is_current_dicomdir = self.is_dicomdir(filepath)
        if not pydicom:
            QTreeWidgetItem(self.header_tree, ["ERROR", "", "", "pydicom not installed"])
            return
        try:
            ds = pydicom.dcmread(filepath, force=True)
            self.current_ds = ds
            if self.is_current_dicomdir:
                batch_top = QTreeWidgetItem(self.header_tree, ["COMMON TAGS (BATCH EDIT)", "", "", ""])
                batch_top.setExpanded(True)
                self._add_common_tags_batch(batch_top, ds)
                struct_item = QTreeWidgetItem(self.header_tree, ["DIRECTORY STRUCTURE", "", "", ""])
                self._build_dicomdir_structure(struct_item, ds)
                struct_item.setExpanded(True)
            raw_top = QTreeWidgetItem(self.header_tree, ["RAW FULL TAGS", "", "", ""])
            self._add_file_info(ds, filepath)
            for elem in ds:
                self.add_dicom_element(raw_top, elem)
            self.header_tree.expandToDepth(1)
        except Exception as e:
            QTreeWidgetItem(self.header_tree, ["ERROR", "", "", str(e)])
        self.btn_copy_header.setEnabled(True)
        self.btn_copy_csv.setEnabled(True)
        self.btn_save.setEnabled(True)
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
            prefix = " " * indent
            line = f"{prefix}{child.text(0)} {child.text(1)} [{child.text(2)}] {child.text(3)}".strip()
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
    def save_changes(self):
        if not self.current_filepath or not self.current_ds:
            return
        if QMessageBox.question(self, "Confirm Save",
                               f"Save changes to {self.current_filepath.name}?\nA backup will be created.") != QMessageBox.Yes:
            return
        try:
            backup = self.current_filepath.with_suffix(self.current_filepath.suffix + f".bak_{int(time.time())}")
            shutil.copy2(self.current_filepath, backup)
            if self.is_current_dicomdir:
                self._apply_batch_edits_to_dicomdir()
            self.current_ds.save_as(self.current_filepath)
            QMessageBox.information(self, "Success", f"Changes saved!\nBackup: {backup.name}")
            self.refresh_current_folder()
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))
# -------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = DICOMHeaderViewer()
    viewer.show()
    sys.exit(app.exec_())
# -------------------------------------------------------------