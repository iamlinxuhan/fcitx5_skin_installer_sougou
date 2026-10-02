"""后台安装线程。

皮肤转换是 CPU 密集的（Pillow 重绘 + numpy 运算），放在主线程会让界面卡死，
因此丢进 QThread 执行，通过信号回报进度。
"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from .converter import SkinError, ThemeExistsError, install_ssf


class InstallWorker(QThread):
    """按顺序安装一批 .ssf 皮肤。

    取消采用协作式：调用 :meth:`requestInterruption`，循环在每处理完一个皮肤后
    检查并退出。不使用已废弃的 ``terminate()`` —— 它会在线程持有文件句柄时强杀，
    可能留下半个主题目录。
    """

    log = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total
    done = pyqtSignal(bool, str)  # success, message

    def __init__(self, files, dest_root, overwrite=False, parent=None):
        super().__init__(parent)
        self._files = [Path(f) for f in files]
        self._dest_root = Path(dest_root)
        self._overwrite = overwrite

    def run(self):
        total = len(self._files)
        if not total:
            self.done.emit(False, "没有可安装的皮肤。")
            return

        installed = 0
        skipped = 0

        for index, path in enumerate(self._files, start=1):
            if self.isInterruptionRequested():
                self.done.emit(
                    False, f"已取消，完成 {installed}/{total} 个皮肤。"
                )
                return

            self.progress.emit(index, total)
            self.log.emit(f"[{index}/{total}] {path.name}")

            try:
                install_ssf(
                    path,
                    self._dest_root,
                    overwrite=self._overwrite,
                    log=self.log.emit,
                )
                installed += 1
            except ThemeExistsError:
                skipped += 1
                self.log.emit("  ⏭ 已存在同名主题，跳过")
            except SkinError as exc:
                self.log.emit(f"  ❌ {exc}")
            except Exception as exc:  # 兜底，避免整个批次因单个皮肤中断
                self.log.emit(f"  ❌ 未预期的错误: {exc!r}")

        parts = [f"成功 {installed}/{total} 个皮肤"]
        if skipped:
            parts.append(f"跳过 {skipped} 个已存在的主题")
        self.done.emit(True, "安装完成！" + "，".join(parts) + "。")
