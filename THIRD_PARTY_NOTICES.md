# 第三方组件声明

本项目以 GPL-3.0 发布，因为发布的可执行产物中包含了以 GPL-3.0 许可的
[ssfconv](https://github.com/RadND/ssfconv)。

以下组件随打包产物一同分发。

---

## ssfconv

- **用途**：`.ssf` 皮肤包的解包与到 fcitx5 主题格式的转换
- **来源**：https://github.com/RadND/ssfconv
- **版本**：1.2.2（commit `9fdbed9cb80907044917e53383216952675f1037`）
- **许可证**：GPL-3.0-or-later
- **版权**：nihui、VOID001、fkxxyz、RadND 及贡献者

本项目的构建脚本以如下方式安装该依赖：

```
pip install "ssfconv @ git+https://github.com/RadND/ssfconv.git@9fdbed9cb80907044917e53383216952675f1037"
```

GPL-3.0 要求分发衍生作品时提供对应源码。ssfconv 的完整源码可在上述仓库的
对应 commit 处获取，未经修改。

---

## PyQt5

- **用途**：图形界面
- **来源**：https://riverbankcomputing.com/software/pyqt/
- **许可证**：GPL-3.0
- **版权**：Riverbank Computing Limited

---

## Qt 5

- **用途**：PyQt5 底层的界面工具库
- **来源**：https://www.qt.io/
- **许可证**：LGPL-3.0 / GPL-3.0
- **版权**：The Qt Company Ltd. 及贡献者

---

## Pillow

- **用途**：皮肤包内图片的解码与重绘
- **来源**：https://python-pillow.org/
- **许可证**：MIT-CMU
- **版权**：Secret Labs AB、Fredrik Lundh 及贡献者

---

## NumPy

- **用途**：像素数值计算
- **来源**：https://numpy.org/
- **许可证**：BSD-3-Clause
- **版权**：NumPy Developers

---

## pycryptodomex

- **用途**：加密 `.ssf` 皮肤包的 AES 解密
- **来源**：https://www.pycryptodome.org/
- **许可证**：BSD-2-Clause 与 Public Domain（详见其 LICENSE.rst）
- **版权**：Legrandin 及贡献者

---

## PyInstaller

- **用途**：生成免安装的可执行产物（仅构建期使用，不随产物分发其代码）
- **来源**：https://pyinstaller.org/
- **许可证**：GPL-2.0-or-later 附例外条款，允许打包私有/其他许可的程序
- **版权**：PyInstaller Development Team

---

## AppImageKit

- **用途**：生成 AppImage 产物（仅构建期使用）
- **来源**：https://github.com/AppImage/AppImageKit
- **许可证**：MIT
