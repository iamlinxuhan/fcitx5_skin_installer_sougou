"""搜狗 .ssf 皮肤 -> fcitx5 主题的核心转换逻辑。

本模块刻意不依赖任何 GUI 框架，可以单独测试，也可以被命令行工具复用。
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import tempfile
import warnings
from pathlib import Path
from typing import Callable, Iterable

# skin.ini 里引用到的、需要参与大小写修正的图片后缀
IMAGE_EXTS = {".png", ".bmp", ".jpg", ".jpeg", ".gif"}

# 主题名会直接作为目录名，剔除文件系统不接受的字符
_UNSAFE_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

Logger = Callable[[str], None]


class SkinError(Exception):
    """皮肤处理失败。"""


class ThemeExistsError(SkinError):
    """目标目录已存在同名主题。"""

    def __init__(self, path: Path):
        super().__init__(f"主题已存在: {path}")
        self.path = path


def _noop(_message: str) -> None:
    pass


def _load_ssfconv():
    """延迟导入 ssfconv。

    直接用它 ``convert.out`` / ``extract.ssf`` 里的函数，而不是走命令行：
    ``ssfconv.cli`` 的 ``conv()`` 结尾调用了 ``exit()``，在 GUI 进程里会直接
    把整个程序干掉。
    """
    try:
        from ssfconv.convert.out import ssf2fcitx5
        from ssfconv.extract.ssf import extract_ssf
    except ImportError as exc:  # pragma: no cover - 取决于运行环境
        raise SkinError(
            "缺少 ssfconv 依赖，无法转换皮肤。\n"
            "源码运行时请先执行：pip install pycryptodomex pillow numpy，\n"
            "再安装 ssfconv（详见 README 的「从源码运行」一节）。"
        ) from exc
    return extract_ssf, ssf2fcitx5


def default_theme_dir() -> Path:
    """fcitx5 主题目录，遵循 XDG 规范。"""
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "fcitx5" / "themes"


def safe_theme_name(name: str) -> str:
    """把文件名转成安全的目录名。"""
    cleaned = _UNSAFE_NAME_CHARS.sub("_", name).strip().strip(".")
    return cleaned or "theme"


def _case_insensitive_map(folder: Path) -> dict[str, Path]:
    """建立 小写文件名 -> 实际文件名 的映射。"""
    return {p.name.lower(): p for p in folder.iterdir() if p.is_file()}


def normalize_ssf_dir(folder: Path) -> list[str]:
    """修正皮肤包内文件名的大小写。

    搜狗皮肤包多在 Windows 上打包，包内文件名的大小写常与 ssfconv 的硬编码
    不一致（例如包内是 ``Skin.ini``，而 ssfconv 只找 ``skin.ini``），在大小写
    敏感的文件系统上会直接导致转换失败。这里统一修正。

    返回被改名的文件名列表。
    """
    fixed: list[str] = []

    # 1. skin.ini —— ssfconv 写死了小写名
    mapping = _case_insensitive_map(folder)
    ini = mapping.get("skin.ini")
    if ini is not None and ini.name != "skin.ini":
        target = ini.with_name("skin.ini")
        ini.rename(target)
        fixed.append(f"{ini.name} -> skin.ini")
        ini = target

    if ini is None:
        raise SkinError("皮肤包内没有 skin.ini，可能不是有效的搜狗皮肤。")

    # 2. skin.ini 里引用的图片 —— 实际文件名的大小写要和 ini 中的写法对齐
    try:
        content = ini.read_text(encoding="utf-16")
    except UnicodeError:
        content = ini.read_text(encoding="utf-8", errors="ignore")

    mapping = _case_insensitive_map(folder)
    for raw in content.splitlines():
        if "=" not in raw:
            continue
        value = raw.split("=", 1)[1].strip()
        if Path(value).suffix.lower() not in IMAGE_EXTS:
            continue
        if (folder / value).exists():
            continue
        actual = mapping.get(value.lower())
        if actual is not None:
            actual.rename(folder / value)
            fixed.append(f"{actual.name} -> {value}")

    return fixed


def install_ssf(
    ssf_path: Path | str,
    dest_root: Path | str,
    *,
    overwrite: bool = False,
    log: Logger | None = None,
) -> Path:
    """把单个 .ssf 皮肤转换成 fcitx5 主题并安装到 ``dest_root``。

    Args:
        ssf_path: .ssf 皮肤文件。
        dest_root: 主题根目录，通常是 :func:`default_theme_dir`。
        overwrite: 目标主题已存在时是否覆盖。
        log: 接收进度文本的回调。

    Returns:
        安装后的主题目录。

    Raises:
        ThemeExistsError: 目标已存在且 ``overwrite`` 为 False。
        SkinError: 解包或转换失败。
    """
    emit = log or _noop
    extract_ssf, ssf2fcitx5 = _load_ssfconv()

    ssf_path = Path(ssf_path)
    dest_root = Path(dest_root)
    target = dest_root / safe_theme_name(ssf_path.stem)

    if target.exists() and not overwrite:
        raise ThemeExistsError(target)

    if not ssf_path.is_file():
        raise SkinError(f"皮肤文件不存在: {ssf_path}")

    # 临时目录放在系统 tmp，避免污染工作目录，也避免从只读目录启动时崩溃
    tmp_root = Path(tempfile.mkdtemp(prefix="fcitx5-skin-"))
    try:
        work = tmp_root / "skin"
        work.mkdir()

        emit(f"  解包 {ssf_path.name}")
        captured = io.StringIO()
        try:
            with contextlib.redirect_stderr(captured):
                extract_ssf(ssf_path, work)
        except Exception as exc:
            raise SkinError(
                captured.getvalue().strip() or f"解包失败: {exc}"
            ) from exc

        if not any(work.iterdir()):
            raise SkinError(captured.getvalue().strip() or "解包后没有任何文件，皮肤包可能已损坏。")

        fixed = normalize_ssf_dir(work)
        if fixed:
            emit(f"  修正文件名大小写: {', '.join(fixed)}")

        emit("  转换为 fcitx5 主题")
        captured = io.StringIO()
        try:
            # ssf2fcitx5 内部用字符串拼接路径（skin_dir + os.sep + name），
            # 必须传 str，传 Path 会 TypeError。
            with contextlib.redirect_stderr(captured), warnings.catch_warnings():
                # ssfconv 的 getImageAvg 用 uint8 累加像素，溢出告警是上游的
                # 已知噪音，对结果没有影响，但会淹没真正有用的日志。
                warnings.simplefilter("ignore", RuntimeWarning)
                err = ssf2fcitx5(str(work))
        except Exception as exc:
            # ssfconv 对结构不完整的皮肤包会抛 KeyError 之类的裸异常，
            # 这里统一包装成带上下文的 SkinError。
            detail = captured.getvalue().strip()
            raise SkinError(
                detail or f"转换失败，皮肤包结构可能不完整（{type(exc).__name__}: {exc}）"
            ) from exc

        detail = captured.getvalue().strip()
        if detail:
            emit(f"  {detail}")
        if err:
            raise SkinError(detail or f"转换失败（错误码 {err}）")

        dest_root.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(work, target)

        emit(f"  已安装到 {target}")
        return target
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def find_existing_themes(
    ssf_files: Iterable[Path | str], dest_root: Path | str
) -> list[Path]:
    """返回列表中会在 ``dest_root`` 里撞名的主题目录。"""
    dest_root = Path(dest_root)
    return [
        dest_root / safe_theme_name(Path(f).stem)
        for f in ssf_files
        if (dest_root / safe_theme_name(Path(f).stem)).exists()
    ]
