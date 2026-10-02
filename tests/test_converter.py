#!/usr/bin/env python3
"""转换核心的端到端测试。

不依赖 pytest，直接 ``python tests/test_converter.py`` 即可运行，
CI 里也是这么调的（不需要显示器）。

测试用的 .ssf 是现场合成的：一个 zip，内含 UTF-16 编码的 ``Skin.ini`` 和
``BG.PNG``。故意使用大写文件名，用来复现 Windows 上打包的皮肤包在大小写
敏感文件系统上的失败场景。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fcitx5_skin_installer.converter import (  # noqa: E402
    SkinError,
    ThemeExistsError,
    find_existing_themes,
    install_ssf,
    safe_theme_name,
)
from fcitx5_skin_installer.selftest import (  # noqa: E402
    SKIN_INI,
    background_png,
    make_test_skin,
)

# 测试夹具与 --self-test 共用一份实现
make_ssf = make_test_skin

_failures: list[str] = []


def check(label: str, condition: bool, extra: str = "") -> None:
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {extra}")
        _failures.append(label)


def test_install_and_normalize(work: Path) -> None:
    print("\n[1] 安装 + 大小写修正")
    dest = work / "themes"
    ssf = make_ssf(work / "测试皮肤.ssf")

    logs: list[str] = []
    target = install_ssf(ssf, dest, log=logs.append)

    check("主题目录已创建", target.is_dir(), str(target))
    check("theme.conf 已生成", (target / "theme.conf").is_file())
    check("skin.ini 已改为小写", (target / "skin.ini").is_file())
    check("原大写 Skin.ini 不复存在", not (target / "Skin.ini").exists())
    check("引用的图片已对齐 ini 中的写法", (target / "bg.png").is_file())
    check("日志里报告了改名", any("skin.ini" in line for line in logs))

    conf = (target / "theme.conf").read_text(encoding="utf-8")
    for section in ("[Metadata]", "[InputPanel]", "[Menu/Background]", "[InputPanel/Background]"):
        check(f"theme.conf 含 {section}", section in conf)

    check("没有残留 numpy 噪音告警", not any("RuntimeWarning" in line for line in logs))


def test_overwrite_guard(work: Path) -> None:
    print("\n[2] 覆盖保护")
    dest = work / "themes2"
    ssf = make_ssf(work / "重复皮肤.ssf")

    install_ssf(ssf, dest)

    check("能检测到同名主题", [p.name for p in find_existing_themes([ssf], dest)] == ["重复皮肤"])

    try:
        install_ssf(ssf, dest)
        check("默认拒绝覆盖", False, "没有抛出 ThemeExistsError")
    except ThemeExistsError:
        check("默认拒绝覆盖", True)

    target = install_ssf(ssf, dest, overwrite=True)
    check("overwrite=True 时可覆盖", target.is_dir())


def test_broken_skin(work: Path) -> None:
    print("\n[3] 损坏/不完整的皮肤包")
    dest = work / "themes3"

    # 缺少 skin.ini
    no_ini = work / "没有ini.ssf"
    with zipfile.ZipFile(no_ini, "w") as zf:
        zf.writestr("readme.txt", "not a skin")
    try:
        install_ssf(no_ini, dest)
        check("缺少 skin.ini 时报错", False, "没有抛异常")
    except SkinError as exc:
        check("缺少 skin.ini 时报错", "skin.ini" in str(exc), str(exc))

    # 结构不完整：ssfconv 内部会抛裸 KeyError，应被包装成 SkinError
    partial = work / "不完整.ssf"
    truncated = SKIN_INI.split("[Scheme_V1]")[0]
    with zipfile.ZipFile(partial, "w") as zf:
        zf.writestr("skin.ini", truncated.encode("utf-16"))
        zf.writestr("bg.png", background_png())
    try:
        install_ssf(partial, dest)
        check("结构不完整时报错", False, "没有抛异常")
    except SkinError as exc:
        check("结构不完整时报错", "转换失败" in str(exc), str(exc))

    # 文件不存在
    try:
        install_ssf(work / "根本不存在.ssf", dest)
        check("文件不存在时报错", False, "没有抛异常")
    except SkinError as exc:
        check("文件不存在时报错", "不存在" in str(exc), str(exc))


def test_temp_cleanup(work: Path) -> None:
    print("\n[4] 临时目录清理")
    dest = work / "themes4"
    ssf = make_ssf(work / "临时.ssf")

    import tempfile as _tempfile

    before = set(Path(_tempfile.gettempdir()).glob("fcitx5-skin-*"))
    install_ssf(ssf, dest)
    after = set(Path(_tempfile.gettempdir()).glob("fcitx5-skin-*"))
    check("成功后不残留临时目录", before == after, str(after - before))

    # 失败路径同样不能残留
    broken = work / "坏的.ssf"
    with zipfile.ZipFile(broken, "w") as zf:
        zf.writestr("readme.txt", "x")
    try:
        install_ssf(broken, dest)
    except SkinError:
        pass
    after2 = set(Path(_tempfile.gettempdir()).glob("fcitx5-skin-*"))
    check("失败后不残留临时目录", before == after2, str(after2 - before))


def test_safe_names() -> None:
    print("\n[5] 主题名安全化")
    check("剔除路径分隔符", "/" not in safe_theme_name("a/b"))
    check("剔除 .. 穿越", safe_theme_name("..") == "theme")
    check("空名有兜底", safe_theme_name("...") == "theme")
    check("中文名保留", safe_theme_name("蒲公英的思念") == "蒲公英的思念")


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="ssfconv-test-"))
    try:
        test_install_and_normalize(work)
        test_overwrite_guard(work)
        test_broken_skin(work)
        test_temp_cleanup(work)
        test_safe_names()
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    if _failures:
        print(f"❌ {len(_failures)} 项失败: {', '.join(_failures)}")
        return 1
    print("✅ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
