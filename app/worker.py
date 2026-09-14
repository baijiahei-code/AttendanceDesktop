"""后台任务工具：把耗时的阻塞调用（网络请求、API 查询）放到线程池执行。

为什么需要：wages.fetch / fetch_holidays / test_connection 都是同步的
urllib 请求（超时 15 秒）。如果直接在 Qt 主线程调用，整个界面会在等待
期间冻结（无法拖动、无法点击、无响应），用户感受就是“软件卡死”。

用法（回调都在主线程执行，可以安全地更新界面）::

    self._api_call = run_async(
        lambda: wages.fetch(...),          # 在工作线程执行
        on_done=self._on_wage_result,      # 成功 → 主线程
        on_failed=lambda msg: ...,         # 异常 → 主线程
        on_finished=lambda: btn.setEnabled(True),  # 无论如何都执行
    )

注意：AsyncCall 需被引用持有（如 self._api_call），否则可能被提前回收；
模块内部另有一份 _ACTIVE 集合兜底，直到任务结束才释放。
"""
from __future__ import annotations

import traceback
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _JobSignals(QObject):
    """承载跨线程信号（QObject 必须在主线程创建，故与 QRunnable 分离）。"""

    done = Signal(object)   # 任务返回值
    failed = Signal(str)    # 异常描述


class _Job(QRunnable):
    """在线程池里执行一次函数调用。"""

    def __init__(self, fn: Callable[[], object], signals: _JobSignals):
        super().__init__()
        self._fn = fn
        self._signals = signals
        self.setAutoDelete(True)

    def run(self):  # 工作线程
        try:
            result = self._fn()
        except Exception as ex:  # noqa: BLE001 - 后台异常必须回传而不是吞掉
            traceback.print_exc()
            self._signals.failed.emit(str(ex) or ex.__class__.__name__)
            return
        self._signals.done.emit(result)


# 兜底保活：任务结束前不让 AsyncCall 被垃圾回收
_ACTIVE: set["AsyncCall"] = set()


class AsyncCall:
    """一次后台调用的句柄：持有信号对象，直到任务结束。"""

    def __init__(self, fn: Callable[[], object],
                 on_done: Callable[[object], None] | None = None,
                 on_failed: Callable[[str], None] | None = None,
                 on_finished: Callable[[], None] | None = None):
        self._on_finished = on_finished
        self._signals = _JobSignals()
        if on_done is not None:
            self._signals.done.connect(on_done)
        if on_failed is not None:
            self._signals.failed.connect(on_failed)
        # 连接顺序在用户回调之后：保证收尾逻辑最后执行
        self._signals.done.connect(self._finish)
        self._signals.failed.connect(self._finish)
        self._job = _Job(fn, self._signals)
        self._cancelled = False

    def start(self) -> "AsyncCall":
        _ACTIVE.add(self)
        QThreadPool.globalInstance().start(self._job)
        return self

    def cancel(self):
        """放弃结果处理（请求本身无法中断，仅忽略回调）。"""
        self._cancelled = True

    def _finish(self, *_args):
        _ACTIVE.discard(self)
        if self._on_finished is None or self._cancelled:
            return
        try:
            self._on_finished()
        except RuntimeError:
            # 目标控件已销毁（例如设置对话框被关闭）——忽略
            pass


def run_async(fn: Callable[[], object],
              on_done: Callable[[object], None] | None = None,
              on_failed: Callable[[str], None] | None = None,
              on_finished: Callable[[], None] | None = None) -> AsyncCall:
    """在后台线程执行 fn()，结果通过回调送回主线程（回调可省略，即静默）。"""
    return AsyncCall(fn, on_done=on_done, on_failed=on_failed,
                     on_finished=on_finished).start()


def cancel_all():
    """放弃所有在跑任务的结果处理（窗口关闭时调用）。

    注意：已发出的 HTTP 请求无法中断，但回调不会再触动界面。
    """
    for call in list(_ACTIVE):
        call.cancel()
