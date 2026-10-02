"""支持 ``python -m fcitx5_skin_installer``。"""

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
