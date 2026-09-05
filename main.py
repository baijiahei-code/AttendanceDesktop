"""工资考勤表 · Python 桌面版入口。"""
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

# 保证从仓库根以 `python main.py` 启动时 `app` 包可导入（兼容其它工作目录启动）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main_window import MainWindow  # noqa: E402
from app.storage import MonthStore  # noqa: E402


def _icon_path() -> str:
    """返回 app/icon.ico 的绝对路径，兼容开发模式与 PyInstaller 打包模式。

    - 开发模式：app/icon.ico（相对本文件，仓库根 main.py）
    - 打包模式：sys._MEIPASS/app/icon.ico（由 spec 的 datas 打进包内）
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "app", "icon.ico")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "icon.ico")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("工资考勤表")
    icon_file = _icon_path()
    if os.path.exists(icon_file):
        app.setWindowIcon(QIcon(icon_file))
    data_dir = os.environ.get("ATT_DATA_DIR") or None
    try:
        store = MonthStore(data_dir)
    except Exception as ex:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None, "启动失败",
            f"无法创建数据目录：{ex}\n\n请检查环境变量 ATT_DATA_DIR 或 %LOCALAPPDATA% 的权限。")
        return 1
    win = MainWindow(store)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
