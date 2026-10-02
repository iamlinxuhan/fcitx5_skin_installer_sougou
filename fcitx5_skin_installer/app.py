"""应用启动逻辑。

单独成模块，这样 ``skin_installer.py`` 入口和 ``python -m fcitx5_skin_installer``
共用同一份初始化代码。
"""

from __future__ import annotations

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from . import APP_NAME, APP_TITLE, __version__
from .main_window import MainWindow
from .resources import app_icon


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv

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
