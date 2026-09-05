"""统一的卡片框架：所有页面卡片都通过 :class:`Card` 构造。

设计目标
--------
* 5 种视觉变体（variant）—— 直接对应 ``style.py`` 已有的 CSS 选择器，无需新增样式：
    - ``"default"`` → ``QFrame#card``  （参数卡、报表卡、合规卡、备注卡……）
    - ``"hero"``    → ``QFrame#heroCard``（渐变背景大卡）
    - ``"stat"``    → ``QFrame#statCard``（小统计块）
    - ``"quick"``   → ``QFrame#quickCard``（快捷入口）
    - ``"row"``     → ``QFrame#pirow``   （工资项单行）
* 统一的「标题 + 可选 hint + 可选右侧工具槽 + 内容区」结构。
* **统一参与锁定状态机** —— :meth:`Card.set_locked` 一键禁用卡片内所有可交互控件，
  各页面 ``_set_xxx_locked`` 不再重复写 ``for w in widgets: w.setEnabled(False)``。
* 自动追踪卡片内通过 :meth:`add_widget` / :meth:`add_layout` 加入的可交互控件，
  用于锁定时批量禁用；同时不破坏 Qt 的父子对象管理。

使用模式
--------
::

    card = Card(parent, "计薪与请假", hint="...", variant="default")
    card.add_widget(spin)
    card.add_layout(row_layout)
    card.add_toolbar_widget(lock_button)   # 顶部右侧
    card.set_locked(True)                  # 一键禁用内部所有交互控件
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractSpinBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QVBoxLayout, QWidget,
)


# variant → (objectName, title objectName, value objectName)
# 与 style.py 中的 QSS 选择器一一对应；改动其中一个就要同步另一个。
_VARIANT_CSS = {
    "default": ("card",        "cardTitle",   None),
    "hero":    ("heroCard",    "heroTitle",   "heroValue"),
    "stat":    ("statCard",    "statTitle",   "statValue"),
    "quick":   ("quickCard",   "quickTitle",  None),
    "row":     ("pirow",       None,          None),
}

# 卡片内可交互控件类型（用于锁定时禁用）。
# 锁定语义是「不允许再触发 valueChanged / 选中 / 编辑等」；
# 因此 spin / combo / lineedit / pushbutton / checkbox / table 都纳入。
_INTERACTIVE_TYPES = (
    QAbstractSpinBox, QComboBox, QLineEdit,
)


class Card(QFrame):
    """统一的卡片容器。

    参数
    ----
    title:
        卡片标题，传空字符串则不渲染标题栏。
    hint:
        副标题/说明文字，显示在标题右侧。
    variant:
        视觉变体；见模块顶部说明。
    parent:
        Qt 父对象（通常是页面根 QWidget）。为 keyword-only，避免与 title 混淆。
    toolbar:
        ``True`` 时在标题栏右侧预留一块可放置工具按钮的槽位，
        通过 :meth:`add_toolbar_widget` 填充。
    margins:
        卡片内边距 ``(左, 上, 右, 下)``，None 用变体默认值。
    """

    def __init__(
        self,
        title: str = "",
        hint: str = "",
        variant: str = "default",
        *,
        parent: QWidget | None = None,
        toolbar: bool = False,
        margins: tuple[int, int, int, int] | None = None,
    ):
        super().__init__(parent)
        if variant not in _VARIANT_CSS:
            raise ValueError(f"未知 Card variant: {variant!r}")
        obj_name, title_obj, _ = _VARIANT_CSS[variant]
        self.setObjectName(obj_name)
        self._variant = variant

        # 主体布局
        outer = QVBoxLayout(self)
        if margins is None:
            # 变体默认内边距 —— 与既有手搓卡片保持一致
            margins = {
                "default": (18, 14, 18, 14),
                "hero":    (18, 12, 18, 12),
                "stat":    (16, 10, 16, 10),
                "quick":   (16, 12, 16, 12),
                "row":     (10, 8,  10, 8),
            }[variant]
        outer.setContentsMargins(*margins)
        outer.setSpacing(10 if variant == "default" else 6 if variant == "row" else 8)

        # 标题栏（可选）
        self._toolbar_layout: QHBoxLayout | None = None
        if title or hint or toolbar:
            head = QHBoxLayout()
            head.setSpacing(8)
            if title:
                t = QLabel(title)
                if title_obj is not None:
                    t.setObjectName(title_obj)
                head.addWidget(t)
            if hint:
                s = QLabel(hint)
                s.setObjectName("secHint")
                # hint 默认放最右侧靠左对齐；标题与 hint 之间留 stretch
                head.addStretch(1)
                head.addWidget(s)
            if toolbar:
                # 右侧工具槽：默认有一个 stretch 把工具按钮推到最右
                self._toolbar_layout = QHBoxLayout()
                self._toolbar_layout.setSpacing(6)
                self._toolbar_layout.addStretch(1)
                head.addLayout(self._toolbar_layout)
            outer.addLayout(head)

        # 内容区 —— add_widget / add_layout 都往这里塞
        self._body = QVBoxLayout()
        self._body.setSpacing(8 if variant == "default" else 4)
        self._body.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self._body)

        # 锁定状态追踪
        self._locked = False
        # 这里只记录「被显式 add 进卡片的可交互控件」，不递归遍历子对象
        # —— 因为：1) 避免锁定递归过深（子容器有自己的 set_locked）；
        # 2) 与 PayItemList 那种"内部已自带 set_locked"的复合控件解耦。
        self._tracked: list[QWidget] = []

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    @property
    def variant(self) -> str:
        return self._variant

    def body_layout(self) -> QVBoxLayout:
        """返回内容区 layout，需要做 GridLayout / HBoxLayout 时请用 add_layout。"""
        return self._body

    def add_widget(self, w: QWidget) -> QWidget:
        """往卡片内容区加一个 widget；同步追踪以便锁定时禁用。"""
        self._body.addWidget(w)
        self._track(w)
        return w

    def add_layout(self, lay) -> None:
        """往卡片内容区加一个 layout（QGridLayout / QHBoxLayout 等）。"""
        self._body.addLayout(lay)
        # layout 本身不是 widget，但里面若有可交互控件，调用方应自行管理
        # 锁定 —— 通常 layout 内的控件会被调用方持有引用并独立 disable。
        # 这里仅记录「该 layout 整体」以便锁定时调用方可以遍历。
        self._tracked.append(lay)  # type: ignore[arg-type]

    def add_toolbar_widget(self, w: QWidget) -> QWidget:
        """往标题栏右侧工具槽加一个 widget（仅 toolbar=True 时可用）。"""
        if self._toolbar_layout is None:
            raise RuntimeError("Card 未启用 toolbar=True，无法 add_toolbar_widget")
        # toolbar_layout 已经有 stretch；插入位置 -2 让新按钮在 stretch 之前
        self._toolbar_layout.insertWidget(self._toolbar_layout.count() - 1, w)
        # toolbar 内的控件也参与锁定
        self._track(w)
        return w

    def add_widget_untracked(self, w: QWidget) -> QWidget:
        """把 widget 加到 body 但**不**参与 set_locked 批量禁用。

        用于：导出 Excel、复制链接、查看日志 等「锁定时仍应可用」的操作按钮。
        """
        self._body.addWidget(w)
        return w

    def track_extra(self, w) -> None:
        """把已经放进 body（但不是通过 add_widget/add_layout 加入）的 widget 或 layout
        也纳入本卡片的锁定追踪。

        适用于：
        * 卡片构造完后才追加的子项
        * 嵌在嵌套 layout 里、需要单独锁定的 widget / layout
        """
        if w in self._tracked:
            return
        self._tracked.append(w)
        # 如果当前已经处于锁定态，立即把锁作用到新追踪的项上
        if self._locked:
            self._apply_lock_to(w, True)

    # ------------------------------------------------------------------
    # 锁定状态机
    # ------------------------------------------------------------------
    def set_locked(self, locked: bool) -> None:
        """一键禁用卡片内所有可交互控件。

        不会触碰：
        * toolbar 槽位的「非交互性」控件（如纯 QLabel）
        * 卡片自身的标题 / hint
        * 那些自带 set_locked 的子容器（如 PayItemListWidget），由调用方单独调用。
        """
        self._locked = bool(locked)
        for w in self._tracked:
            self._apply_lock_to(w, self._locked)

    def is_locked(self) -> bool:
        return self._locked

    def iter_tracked_widgets(self):
        """迭代所有被本卡片追踪的可交互 widget。

        主要供测试 / 调试使用，验证锁定态确实作用到所有控件上。
        不保证顺序；返回的是扁平化的可交互 widget 列表。
        """
        seen: set[int] = set()
        out: list[QWidget] = []

        def visit(item):
            if hasattr(item, "count") and hasattr(item, "itemAt"):
                for i in range(item.count()):
                    it = item.itemAt(i)
                    if it is None:
                        continue
                    if it.widget() is not None:
                        visit(it.widget())
                    elif it.layout() is not None:
                        visit(it.layout())
                return
            if isinstance(item, _INTERACTIVE_TYPES) or hasattr(item, "setCheckable"):
                if id(item) not in seen:
                    seen.add(id(item))
                    out.append(item)

        for w in self._tracked:
            visit(w)
        return out

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _track(self, w: QWidget) -> None:
        # 同一控件被多次 add 时只在列表里留一份
        if w in self._tracked:
            return
        self._tracked.append(w)

    def _apply_lock_to(self, w, locked: bool) -> None:
        """把锁定态作用到一个 tracked 控件 / layout。"""
        # layout：只递归禁用其内可交互控件（layout 本身无 setEnabled）
        if hasattr(w, "count") and hasattr(w, "itemAt"):
            for i in range(w.count()):
                it = w.itemAt(i)
                if it is None:
                    continue
                if it.widget() is not None:
                    self._apply_lock_to(it.widget(), locked)
                elif it.layout() is not None:
                    self._apply_lock_to(it.layout(), locked)
            return
        if not isinstance(w, QWidget):
            return
        # 控件：先按类型判定是否是交互型；非交互型（QLabel/QFrame）直接跳过。
        is_interactive = (
            isinstance(w, _INTERACTIVE_TYPES)
            or hasattr(w, "setCheckable")          # QPushButton / QCheckBox 等
        )
        if not is_interactive:
            return
        try:
            w.setEnabled(not locked)
        except Exception:
            pass
