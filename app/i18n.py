"""Qt 内置文案的简体中文化（右键菜单、对话框按钮等）。

应用自己写的界面文字本来就是中文，但 **Qt 框架自带的字符串**不在其中：

- 输入框 / 文本框右键菜单的「撤消 / 重做 / 剪切 / 复制 / 粘贴 / 删除 / 全选」
- `QMessageBox` 的「确定 / 取消 / 是 / 否」等标准按钮
- `QFileDialog` / `QColorDialog` 等标准对话框的按钮

它们来自 Qt 自带的翻译文件（`qtbase_zh_CN.qm`），**必须显式 `QTranslator.load()` +
`QApplication.installTranslator()` 才会生效**，否则界面上会中英混杂
（例如右键菜单显示 Undo / Redo / Copy）。

用法（启动时调用一次）::

    app = QApplication(sys.argv)
    install_qt_translations(app)     # 翻译器以 app 为父对象，引用不会丢

本模块**无条件装中文**：软件界面只有中文一种语言，与系统区域设置无关。
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QLibraryInfo, QTranslator

# `qtbase_zh_CN` 含 QtCore / QtGui / QtWidgets 的控件文案（右键菜单与对话框按钮就在这里）；
# `qt_zh_CN` 是汇总目录。两个都装上，保证覆盖面完整。
_QM_NAMES = ("qtbase_zh_CN", "qt_zh_CN")


def translation_dirs() -> list[str]:
    """返回候选翻译目录（去重，按优先级排序），兼容开发模式与 PyInstaller 打包模式。"""
    import PySide6  # 延迟导入：只有需要兜底路径时才用得上

    candidates = [
        QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
        os.path.join(os.path.dirname(os.path.abspath(PySide6.__file__)), "translations"),
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:  # 打包模式：spec 会把 PySide6/translations 一起收进 _internal
        candidates.append(os.path.join(meipass, "PySide6", "translations"))

    dirs: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        if not path or not os.path.isdir(path):
            continue
        # ⚠ 必须 normcase+normpath 去重：QLibraryInfo 给的是 `/` 路径，
        #    PySide6.__file__ 给的是 `\` 路径，字面比较会当成两个不同目录。
        key = os.path.normcase(os.path.normpath(path))
        if key not in seen:
            seen.add(key)
            dirs.append(path)
    return dirs


def install_qt_translations(app) -> list[QTranslator]:
    """把 Qt 自带的简体中文翻译装到 `app` 上，返回成功安装的 `QTranslator` 列表。

    翻译器以 `app` 为父对象 → C++ 侧持有所有权，不会被垃圾回收（回收后翻译会失效）。
    翻译文件缺失（精简 PySide6 / 打包漏收文件）时只跳过，不抛异常：
    界面顶多退回英文文案，不该因此起不来。
    """
    installed: list[QTranslator] = []
    dirs = translation_dirs()
    for name in _QM_NAMES:
        for path in dirs:
            translator = QTranslator(app)
            if translator.load(name, path) and app.installTranslator(translator):
                installed.append(translator)
                break
    return installed
