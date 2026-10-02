#!/usr/bin/env python3
"""fcitx5 搜狗皮肤安装器 —— 程序入口。

也可以直接用模块方式启动::

    python -m fcitx5_skin_installer
"""

import sys

from fcitx5_skin_installer.app import main

if __name__ == "__main__":
    sys.exit(main())
