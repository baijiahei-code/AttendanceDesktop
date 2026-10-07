"""单实例保护：同一用户只允许运行一个「工作考勤表」窗口。

为什么需要：程序的数据是「一个月一个 JSON 文件」（`MonthStore`），
多个窗口同时打开同一个月时，各自持有内存副本 + 防抖自动保存，
后写的一方会把先写的一方覆盖掉（丢用户改的考勤/工资）。
⇒ 第二个实例不再新建窗口，而是把已在运行的窗口调到前台。

实现原理（Qt 自带的本地 IPC，不依赖第三方库、不写磁盘锁文件）：

* 第一个实例创建 `QLocalServer` 并监听一个名字唯一的管道 / socket；
* 后续实例先用 `QLocalSocket` 去连接它 —— 连上说明"已经有一个在跑"，
  发一个字节表示"请把窗口显示出来"，然后自己立刻退出（退出码 0）。

平台差异：Windows 用命名管道（进程退出即回收），Linux/macOS 用
`$TMPDIR` 下的 socket 文件 —— 上一实例被强杀时文件会残留，
`InstanceServer.start()` 遇到「名字被占」会先探一次：真有人在跑就让位，
只是残留文件才 `removeServer()` 清掉重来。

逃生开关：设环境变量 `ATT_ALLOW_MULTI=1` 可关掉单实例保护（用于对照/调试）。
"""

import getpass
import os

from PySide6.QtNetwork import QAbstractSocket, QLocalServer, QLocalSocket

# 服务名：带版本号，将来改通信格式时可以直接换名字（新旧版本互不干扰）
_SERVER_BASE = "AttendanceDesktop-instance-v1"

# 第二个实例发来的内容（当前只有"请显示窗口"一种请求，内容不参与判断）
_ACTIVATE_REQUEST = b"activate\n"

# 连接 / 收发数据的最长等待毫秒数：本机 IPC，正常都在毫秒级
_TIMEOUT_MS = 500


def allow_multi_instance() -> bool:
    """是否允许同时开多个窗口（环境变量 `ATT_ALLOW_MULTI`）。"""
    return os.environ.get("ATT_ALLOW_MULTI", "").strip().lower() in {"1", "true", "yes", "on"}


def server_name() -> str:
    """IPC 服务名：按用户名区分，避免同一台机器上不同用户的会话互相抢占。"""
    try:
        user = getpass.getuser()
    except Exception:  # 极少数环境取不到用户名（无 HOME 等）→ 退化为公共名
        user = ""
    return f"{_SERVER_BASE}-{user}" if user else _SERVER_BASE


def notify_existing(timeout_ms: int = _TIMEOUT_MS) -> bool:
    """尝试唤醒已运行的实例。

    返回 True = 已有一个在跑（且已请求它把窗口调到前台），本次启动应当退出；
    返回 False = 没有实例在跑，可以正常启动。
    """
    sock = QLocalSocket()
    sock.connectToServer(server_name())
    if not sock.waitForConnected(timeout_ms):
        # 连不上：没有实例在跑（或上一实例残留的 socket 文件已失效）
        sock.abort()
        return False
    sock.write(_ACTIVATE_REQUEST)
    sock.flush()
    sock.waitForBytesWritten(timeout_ms)
    sock.disconnectFromServer()
    # 对端可能已经先断开（届时 socket 已是 Unconnected）→ 直接等会刷 Qt 警告
    if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        sock.waitForDisconnected(timeout_ms)
    return True


class InstanceServer(QLocalServer):
    """第一个实例的 IPC 服务端：收到后续实例的连接就回调 `on_activate`。

    ⚠ 调用方必须持有本对象的引用（挂到窗口上或存模块级变量）——
    QLocalServer 被垃圾回收后监听就没了，单实例保护会静默失效。
    """

    def __init__(self, on_activate, parent=None):
        super().__init__(parent)
        self._on_activate = on_activate
        self.newConnection.connect(self._handle_connections)

    def start(self) -> bool:
        """开始监听。返回 False 表示 IPC 通道建不起来（不阻止程序启动）。"""
        if self.listen(server_name()):
            return True
        if self.serverError() != QAbstractSocket.SocketError.AddressInUseError:
            return False
        # 名字被占用，两种可能：
        #  ① 真的还有实例在跑 → 让位（本实例不该抢）；
        #  ② 上一实例被强杀，Linux/macOS 残留了 socket 文件 → 清掉再来。
        if notify_existing():
            return False
        QLocalServer.removeServer(server_name())
        return self.listen(server_name())

    # ---- 内部 ----

    def _handle_connections(self) -> None:
        while self.hasPendingConnections():
            conn = self.nextPendingConnection()
            if conn is not None:
                # 只关心"有人连过来"这个事实，请求内容不参与判断；
                # 把连接收下并等它自然断开后回收，避免 socket 悬着。
                conn.disconnected.connect(conn.deleteLater)
            self._on_activate()
