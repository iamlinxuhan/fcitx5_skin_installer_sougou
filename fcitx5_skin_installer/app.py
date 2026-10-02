"""应用启动逻辑。

单独成模块，这样 ``skin_installer.py`` 入口和 ``python -m fcitx5_skin_installer``
共用同一份初始化代码。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from . import APP_NAME, APP_TITLE, __version__
from .main_window import MainWindow
from .resources import app_icon


def _ensure_qt_plugin_path() -> None:
    """兜底修正 Qt 的平台插件搜索路径。

    Qt 靠 QLibraryInfo 定位 PyQt5 自带的插件目录，这条路径在含非 ASCII 字符
    的目录下会被破坏（例如把「桌面」变成「??」），于是启动时报
    ``Could not find the Qt platform plugin "xcb"``。显式给出我们实际导入的
    那份 PyQt5 的插件目录即可绕开这个探测。

    打包产物由 PyInstaller 自行处理插件路径，不需要也不应该介入；用户若已
    自行指定也一律尊重。
    """
    if getattr(sys, "frozen", False):
        return
    if os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH") or os.environ.get("QT_PLUGIN_PATH"):
        return

    try:
        import PyQt5
    except ImportError:
        return

    plugins = Path(PyQt5.__file__).parent / "Qt5" / "plugins"
    if not plugins.is_dir():
        return

    os.environ["QT_PLUGIN_PATH"] = str(plugins)
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins / "platforms")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv

    # 必须在任何 QApplication 之前，自检同样要建 QApplication
    _ensure_qt_plugin_path()

    # 打包产物的自检入口，见 selftest 模块
    if "--self-test" in argv:
        from .selftest import run

        return run()

    # 高分屏支持：必须在创建 QApplication 之前设置
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_NAME)
    app.setWindowIcon(app_icon())

    window = MainWindow()
    window.show()
    return app.exec_()
