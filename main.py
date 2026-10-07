"""工作考勤表 · Python 桌面版入口。"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

# 保证从仓库根以 `python main.py` 启动时 `app` 包可导入（兼容其它工作目录启动）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main_window import MainWindow  # noqa: E402
from app.single_instance import InstanceServer, allow_multi_instance, notify_existing  # noqa: E402
from app.storage import MonthStore  # noqa: E402


def _icon_path() -> str:
    """返回 app/icon.ico 的绝对路径，兼容开发模式与 PyInstaller 打包模式。

    - 开发模式：app/icon.ico（相对本文件，仓库根 main.py）
    - 打包模式：sys._MEIPASS/app/icon.ico（由 spec 的 datas 打进包内）
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "app", "icon.ico")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "icon.ico")


def _bring_to_front(win: MainWindow) -> None:
    """第二个实例启动时，把已在运行的窗口显示并置前（不新建窗口）。

    ⚠ `raise_()` / `activateWindow()` 单独用不够：窗口若被最小化，
    Windows 会拒绝把它激活 → 必须先清掉 WindowMinimized 状态位。
    """
    state = win.windowState() & ~Qt.WindowState.WindowMinimized
    win.setWindowState(state | Qt.WindowState.WindowActive)
    win.show()
    win.raise_()
    win.activateWindow()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("工作考勤表")
    icon_file = _icon_path()
    if os.path.exists(icon_file):
        app.setWindowIcon(QIcon(icon_file))

    # 单实例：已经有一个窗口在跑时，把那个窗口调到前台后直接退出。
    # 多个窗口同时编辑同一个月会互相覆盖存档（各自内存副本 + 防抖保存）。
    if not allow_multi_instance() and notify_existing():
        return 0

    data_dir = os.environ.get("ATT_DATA_DIR") or None
    try:
        store = MonthStore(data_dir)
    except Exception as ex:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None, "启动失败",
            f"无法创建数据目录：{ex}\n\n"
            "请检查环境变量 ATT_DATA_DIR，或用户数据目录（Windows 为 %LOCALAPPDATA%，"
            "其它平台为 $XDG_DATA_HOME）的权限。")
        return 1
    win = MainWindow(store)

    # IPC 服务端（持有引用：被回收就监听不到后续实例了）。
    # 建不起来（权限/名字被占）不算致命错误 —— 退化为"可多开"，不阻止使用。
    if not allow_multi_instance():
        server = InstanceServer(lambda: _bring_to_front(win), win)
        if not server.start():
            print("提示：单实例通道创建失败，本次启动可能允许多开窗口。", file=sys.stderr)

    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
