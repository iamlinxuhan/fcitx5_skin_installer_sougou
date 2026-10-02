"""打包产物自检。

PyInstaller 很容易漏掉隐藏导入（特别是 Cryptodome / ssfconv 这类动态导入的
模块），而且在 CI 里这类问题只有用户运行到转换那一步才会暴露。因此提供
``--self-test``：现场合成一个皮肤包，跑完整的解包 → 转换 → 安装流程。

``tests/test_converter.py`` 复用这里的 :func:`make_test_skin`，保证测试夹具
只有一份实现。
"""

from __future__ import annotations

import io
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# 故意用大写文件名（Skin.ini / BG.PNG），复现 Windows 上打包的皮肤包在
# 大小写敏感文件系统上的失败场景。
SKIN_INI = """
[General]
skin_name=自检皮肤
skin_version=1.0
skin_author=selftest
skin_info=由 --self-test 生成

[Display]
pinyin_color=000000
zhongwen_first_color=FF0000
zhongwen_color=00FF00
font_size=16

[Scheme_H1]
pic=bg.png
layout_horizontal=0,10,10
layout_vertical=0,10,10
pinyin_marge=10,5,10,10
zhongwen_marge=5,10,10,10
separator=1

[Scheme_V1]
pic=bg.png
layout_horizontal=0,10,10
layout_vertical=0,10,10
pinyin_marge=10,10,10,10
zhongwen_marge=5,10,10,10
separator=1
"""


def background_png() -> bytes:
    """生成一张有拉伸边距意义的输入框背景图。"""
    from PIL import Image

    buf = io.BytesIO()
    img = Image.new("RGBA", (500, 48), (30, 30, 40, 255))
    for x in range(500):
        for y in range(48):
            if x < 3 or x > 496 or y < 3 or y > 44:
                img.putpixel((x, y), (90, 140, 230, 255))
    img.save(buf, "PNG")
    return buf.getvalue()


def make_test_skin(
    path: Path, *, ini_name: str = "Skin.ini", img_name: str = "BG.PNG"
) -> Path:
    """合成一个最小但结构完整的 .ssf 皮肤包。

    Args:
        path: 输出的 .ssf 路径。
        ini_name: 包内 ini 的文件名，用大写可测试大小写修正。
        img_name: 包内背景图文件名，同样用于测试大小写修正。
    """
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(ini_name, SKIN_INI.encode("utf-16"))
        zf.writestr(img_name, background_png())
    return path


def _check_converter(work: Path) -> list[str]:
    """跑一遍完整的转换流程，返回错误列表。"""
    from .converter import install_ssf

    errors: list[str] = []
    ssf = make_test_skin(work / "自检皮肤.ssf")
    dest = work / "themes"

    logs: list[str] = []
    try:
        target = install_ssf(ssf, dest, log=logs.append)
    except Exception as exc:
        return [f"转换流程失败: {type(exc).__name__}: {exc}"]

    if not (target / "theme.conf").is_file():
        errors.append("没有生成 theme.conf")
    if not (target / "skin.ini").is_file():
        errors.append("skin.ini 大小写未被修正")
    if not (target / "bg.png").is_file():
        errors.append("引用的图片未被同步改名")
    if any("RuntimeWarning" in line for line in logs):
        errors.append("日志里泄漏了 numpy 告警")

    conf = (target / "theme.conf").read_text(encoding="utf-8")
    for section in ("[Metadata]", "[InputPanel]", "[Menu/Background]"):
        if section not in conf:
            errors.append(f"theme.conf 缺少 {section}")

    return errors


def _check_gui() -> list[str]:
    """确认 GUI 能构建（需要 offscreen 平台插件）。"""
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError as exc:
        return [f"无法导入 PyQt5: {exc}"]

    from .main_window import MainWindow
    from .resources import app_icon

    app = QApplication.instance() or QApplication([sys.argv[0]])
    errors: list[str] = []

    window = MainWindow()
    if window.btn_install.isEnabled():
        errors.append("空列表时「开始安装」不应可用")
    if app_icon().isNull():
        errors.append("应用图标加载失败")
    window.close()

    del app
    return errors


def run(include_gui: bool = True) -> int:
    """执行自检，返回进程退出码。"""
    errors: list[str] = []
    work = Path(tempfile.mkdtemp(prefix="fcitx5-skin-selftest-"))
    try:
        print("==> 检查转换流程")
        errors += _check_converter(work)

        if include_gui:
            print("==> 检查 GUI")
            errors += _check_gui()
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if errors:
        print("\n❌ 自检失败:")
        for err in errors:
            print(f"   - {err}")
        return 1

    print("\n✅ 自检通过")
    return 0
