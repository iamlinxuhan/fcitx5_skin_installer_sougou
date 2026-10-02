#!/usr/bin/env bash
#
# 把 PyInstaller 的 onedir 产物打包成单文件 AppImage。
#
# 用法:
#   packaging/build-appimage.sh <pyinstaller-dist-dir> <输出目录> <版本>
#
# 例:
#   packaging/build-appimage.sh dist/fcitx5-skin-installer dist 1.0.0
#
set -euo pipefail

SRC_DIR="${1:?需要 PyInstaller 产物目录}"
OUT_DIR="${2:?需要输出目录}"
VERSION="${3:-0.0.0}"

APP_NAME="fcitx5-skin-installer"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# AppImage 的架构命名与 uname -m 不一定一致
case "$(uname -m)" in
    x86_64|amd64)   ARCH="x86_64" ;;
    aarch64|arm64)  ARCH="aarch64" ;;
    *) echo "不支持的架构: $(uname -m)" >&2; exit 1 ;;
esac

OUTPUT="${OUT_DIR}/${APP_NAME}-${VERSION}-linux-${ARCH}.AppImage"
APPDIR="$(mktemp -d)/${APP_NAME}.AppDir"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/512x512/apps"

echo "==> 组装 AppDir（${ARCH}）"
cp -a "$SRC_DIR" "$APPDIR/usr/bin/$APP_NAME"
cp "$REPO_ROOT/packaging/${APP_NAME}.desktop" "$APPDIR/${APP_NAME}.desktop"
cp "$REPO_ROOT/packaging/${APP_NAME}.desktop" "$APPDIR/usr/share/applications/"
cp "$REPO_ROOT/packaging/icon.png" "$APPDIR/${APP_NAME}.png"
cp "$REPO_ROOT/packaging/icon.png" "$APPDIR/usr/share/icons/hicolor/512x512/apps/${APP_NAME}.png"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
# AppImage 入口：找到 AppDir 根，转交 PyInstaller 生成的可执行文件
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/fcitx5-skin-installer/fcitx5-skin-installer" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

echo "==> 下载 appimagetool"
TOOL_DIR="$(mktemp -d)"
TOOL="${TOOL_DIR}/appimagetool"
curl -fsSL -o "$TOOL" \
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"
chmod +x "$TOOL"

echo "==> 生成 ${OUTPUT}"
mkdir -p "$OUT_DIR"
# CI 容器里没有 FUSE，必须走 --appimage-extract-and-run
ARCH="$ARCH" "$TOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "$OUTPUT"

chmod +x "$OUTPUT"
echo "==> 完成: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
