"""PyQt5 主窗口。"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QSettings, Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, APP_TITLE, __version__
from .converter import (
    SkinError,
    default_theme_dir,
    find_existing_themes,
    safe_theme_name,
)
from .resources import app_icon
from .worker import InstallWorker

SETTINGS_ORG = "iamlinxuhan"
SETTINGS_APP = "fcitx5-skin-installer"


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.skin_files: list[Path] = []
        self._known: set[Path] = set()
        self.worker: InstallWorker | None = None

        self.setWindowTitle(f"{APP_TITLE} v{__version__}")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(720, 620)
        self.setAcceptDrops(True)

        self._build_ui()
        self._restore_settings()
        self._update_actions()
        self.statusBar().showMessage("就绪")

    # ---------------------------------------------------------------- UI

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)

        # --- 皮肤列表 ---
        skin_box = QGroupBox("待安装皮肤")
        skin_layout = QVBoxLayout(skin_box)

        toolbar = QHBoxLayout()
        self.btn_add_files = QPushButton("添加文件…")
        self.btn_add_files.setToolTip("选择一个或多个 .ssf 皮肤文件")
        self.btn_add_files.clicked.connect(self.add_files)

        self.btn_add_folder = QPushButton("添加文件夹…")
        self.btn_add_folder.setToolTip("导入文件夹内所有 .ssf 皮肤")
        self.btn_add_folder.clicked.connect(self.add_folder)

        self.btn_remove = QPushButton("移除选中")
        self.btn_remove.clicked.connect(self.remove_selected)

        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.clicked.connect(self.clear_list)

        toolbar.addWidget(self.btn_add_files)
        toolbar.addWidget(self.btn_add_folder)
        toolbar.addWidget(self.btn_remove)
        toolbar.addWidget(self.btn_clear)
        toolbar.addStretch()

        self.btn_install = QPushButton("开始安装")
        self.btn_install.setDefault(True)
        self.btn_install.setMinimumWidth(120)
        self.btn_install.clicked.connect(self.on_install_clicked)
        toolbar.addWidget(self.btn_install)

        skin_layout.addLayout(toolbar)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemSelectionChanged.connect(self._update_actions)
        skin_layout.addWidget(self.list_widget)

        self.hint_label = QLabel("把 .ssf 文件或文件夹直接拖进窗口也可以添加。")
        self.hint_label.setStyleSheet("color: palette(mid);")
        skin_layout.addWidget(self.hint_label)

        root.addWidget(skin_box, stretch=3)

        # --- 安装位置 ---
        dest_box = QGroupBox("安装位置")
        dest_layout = QVBoxLayout(dest_box)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("主题目录:"))
        self.theme_dir_edit = QLineEdit()
        self.theme_dir_edit.setPlaceholderText(str(default_theme_dir()))
        self.theme_dir_edit.textChanged.connect(self._update_actions)
        dest_row.addWidget(self.theme_dir_edit, stretch=1)

        self.btn_browse_dir = QPushButton("浏览…")
        self.btn_browse_dir.clicked.connect(self.choose_theme_dir)
        dest_row.addWidget(self.btn_browse_dir)

        self.btn_default_dir = QPushButton("恢复默认")
        self.btn_default_dir.clicked.connect(self.reset_theme_dir)
        dest_row.addWidget(self.btn_default_dir)

        self.btn_open_dir = QPushButton("打开目录")
        self.btn_open_dir.clicked.connect(self.open_theme_dir)
        dest_row.addWidget(self.btn_open_dir)

        dest_layout.addLayout(dest_row)
        root.addWidget(dest_box)

        # --- 进度 ---
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m")
        root.addWidget(self.progress)

        # --- 日志 ---
        log_box = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_box)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Monospace", 9, QFont.TypeWriter))
        log_layout.addWidget(self.log_text)
        root.addWidget(log_box, stretch=2)

    # ---------------------------------------------------- 设置持久化

    def _restore_settings(self):
        saved_dir = self.settings.value("theme_dir", "", type=str)
        self.theme_dir_edit.setText(saved_dir or str(default_theme_dir()))
        self._last_dir = self.settings.value("last_dir", "", type=str) or str(Path.home())

    def _save_settings(self):
        default = str(default_theme_dir())
        current = self.theme_dir_edit.text().strip()
        # 只有明显偏离默认值时才记下来，这样用户改了 XDG_DATA_HOME 也能自动跟随
        self.settings.setValue("theme_dir", "" if current == default else current)
        self.settings.setValue("last_dir", getattr(self, "_last_dir", ""))
        self.settings.sync()

    def theme_root(self) -> Path:
        text = self.theme_dir_edit.text().strip()
        return Path(text).expanduser() if text else default_theme_dir()

    # ---------------------------------------------------- 列表操作

    def _append(self, paths) -> int:
        added = 0
        for path in paths:
            path = Path(path)
            try:
                key = path.resolve()
            except OSError:
                key = path
            if key in self._known or not path.is_file():
                continue
            self._known.add(key)
            self.skin_files.append(path)

            try:
                size = _human_size(path.stat().st_size)
            except OSError:
                size = "?"
            item = QListWidgetItem(f"{path.name}    ({size})")
            item.setToolTip(str(path))
            item.setData(Qt.UserRole, path)
            self.list_widget.addItem(item)
            added += 1
        if added:
            self._update_actions()
        return added

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择搜狗皮肤文件", self._last_dir, "搜狗皮肤 (*.ssf);;所有文件 (*)"
        )
        if files:
            self._last_dir = str(Path(files[0]).parent)
            self._append(files)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "选择包含 .ssf 的文件夹", self._last_dir
        )
        if not folder:
            return
        self._last_dir = folder
        found = sorted(Path(folder).glob("*.ssf"))
        added = self._append(found)
        if not added:
            QMessageBox.information(
                self, "没有找到皮肤", "该文件夹内没有可添加的 .ssf 文件。"
            )

    def remove_selected(self):
        for item in self.list_widget.selectedItems():
            path = Path(item.data(Qt.UserRole))
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)
            self.skin_files = [p for p in self.skin_files if p != path]
            try:
                self._known.discard(path.resolve())
            except OSError:
                self._known.discard(path)
        self._update_actions()

    def clear_list(self):
        self.list_widget.clear()
        self.skin_files.clear()
        self._known.clear()
        self._update_actions()

    def _update_actions(self):
        running = self.worker is not None and self.worker.isRunning()
        if running:
            return

        has_items = bool(self.skin_files)
        has_selection = bool(self.list_widget.selectedItems())
        has_dir = bool(self.theme_dir_edit.text().strip())

        self.btn_install.setEnabled(has_items and has_dir)
        self.btn_remove.setEnabled(has_selection)
        self.btn_clear.setEnabled(has_items)
        self.btn_add_files.setEnabled(True)
        self.btn_add_folder.setEnabled(True)
        self.btn_browse_dir.setEnabled(True)
        self.btn_default_dir.setEnabled(True)
        self.theme_dir_edit.setEnabled(True)

    # ---------------------------------------------------- 目录设置

    def choose_theme_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self, "选择 fcitx5 主题目录", str(self.theme_root())
        )
        if folder:
            self.theme_dir_edit.setText(folder)

    def reset_theme_dir(self):
        self.theme_dir_edit.setText(str(default_theme_dir()))

    def open_theme_dir(self):
        root = self.theme_root()
        if not root.exists():
            reply = QMessageBox.question(
                self,
                "目录不存在",
                f"{root}\n\n目录还不存在，要现在创建吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return
            try:
                root.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                QMessageBox.critical(self, "创建失败", str(exc))
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))

    # ---------------------------------------------------- 安装流程

    def on_install_clicked(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.btn_install.setEnabled(False)
            self.btn_install.setText("正在取消…")
            self.append_log("\n—— 已请求取消，等待当前皮肤处理完 ——")
            return
        self.start_install()

    def start_install(self):
        if not self.skin_files:
            QMessageBox.warning(self, "提示", "请先添加要安装的 .ssf 皮肤。")
            return

        dest_root = self.theme_root()
        if not str(dest_root).strip():
            QMessageBox.warning(self, "提示", "请先指定主题目录。")
            return

        overwrite = False
        existing = find_existing_themes(self.skin_files, dest_root)
        if existing:
            names = "\n".join(f"  · {p.name}" for p in existing[:10])
            more = f"\n  …… 另有 {len(existing) - 10} 个" if len(existing) > 10 else ""
            reply = QMessageBox.question(
                self,
                "主题已存在",
                f"以下 {len(existing)} 个主题已存在，继续安装会覆盖它们：\n\n"
                f"{names}{more}\n\n要覆盖吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            overwrite = True

        self.log_text.clear()
        self.progress.setMaximum(len(self.skin_files))
        self.progress.setValue(0)
        self._set_running(True)
        self.append_log(f"主题目录: {dest_root}\n")

        self.worker = InstallWorker(self.skin_files, dest_root, overwrite=overwrite, parent=self)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.update_progress)
        self.worker.done.connect(self.install_finished)
        self.worker.start()

    def _set_running(self, running: bool):
        self.btn_add_files.setEnabled(not running)
        self.btn_add_folder.setEnabled(not running)
        self.btn_remove.setEnabled(not running and bool(self.list_widget.selectedItems()))
        self.btn_clear.setEnabled(not running and bool(self.skin_files))
        self.btn_browse_dir.setEnabled(not running)
        self.btn_default_dir.setEnabled(not running)
        self.theme_dir_edit.setEnabled(not running)
        self.list_widget.setEnabled(not running)
        self.btn_install.setEnabled(True)
        self.btn_install.setText("取消安装" if running else "开始安装")
        self.statusBar().showMessage("安装中…" if running else "就绪")

    def append_log(self, text: str):
        self.log_text.appendPlainText(text)

    def update_progress(self, current: int, total: int):
        self.progress.setMaximum(total)
        self.progress.setValue(current)

    def install_finished(self, success: bool, message: str):
        self._set_running(False)
        self._update_actions()
        self.progress.setValue(self.progress.maximum())
        self.append_log(f"\n{message}")
        self.statusBar().showMessage(message)

        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "未完成", message)

        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

    # ---------------------------------------------------- 拖拽

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        for url in urls:
            path = Path(url.toLocalFile())
            if path.is_dir() or path.suffix.lower() == ".ssf":
                event.acceptProposedAction()
                return

    def dropEvent(self, event):
        added = 0
        rejected = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                added += self._append(sorted(path.glob("*.ssf")))
            elif path.suffix.lower() == ".ssf":
                added += self._append([path])
            else:
                rejected.append(path.name)

        event.acceptProposedAction()
        if added:
            self.statusBar().showMessage(f"已添加 {added} 个皮肤")
        elif rejected:
            QMessageBox.information(
                self, "无法添加", "只支持 .ssf 皮肤文件：\n" + "\n".join(rejected[:5])
            )

    # ---------------------------------------------------- 退出

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认退出",
                "安装正在进行，确定要退出吗？\n"
                "当前正在处理的皮肤会被中断。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.requestInterruption()
            self.worker.wait(5000)

        self._save_settings()
        event.accept()


def create_window() -> MainWindow:
    return MainWindow()
