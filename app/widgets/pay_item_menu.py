"""添加工资项的二级菜单 —— 替代原 SalaryPageMixin._pi_open_add_menu 巨方法。

二级菜单结构：
    ● 计入最低工资标准的工资   可选 N 项  ▸
            全部目录项（已添加置灰带 ✓ 已添加）
            ──────────
            ＋ 输入自定义名称…
    ● 公司补贴                          可选 M 项  ▸
    ...

外部只需要：
* 创建 :class:`PayItemCatalogMenu` 实例
* 调用 :meth:`popup` 在某个按钮下显示
* 连接 :attr:`item_chosen` 与 :attr:`custom_requested` 信号
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QPushButton

from .. import config, model

# 菜单全局样式（与 design token 一致），所有一级菜单 / 子菜单共用
_MENU_QSS = (
    "QMenu{background:#FFFFFF;border:1px solid #E6E8F0;border-radius:10px;"
    "padding:6px 2px;}"
    "QMenu::item{padding:5px 28px 5px 14px;border-radius:6px;}"
    "QMenu::item:selected{background:#EEF2FF;color:#4F46E5;}"
    "QMenu::item:disabled{color:#B4B9C7;}"
    "QMenu::separator{height:1px;background:#EEF0F6;margin:5px 10px;}"
    "QMenu::scroller{width:32px;}"
)


class PayItemCatalogMenu(QMenu):
    """二级分类菜单：列出全部 :data:`model.PAYITEM_CATALOG`。

    Signals
    -------
    item_chosen(str, str)
        type_key, name —— 用户选了一个标准项
    custom_requested(str)
        type_key —— 用户想输入自定义名称
    """

    item_chosen = Signal(str, str)
    custom_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_MENU_QSS)
        self.setToolTipsVisible(True)
        self._used: set[str] = set()

    def set_used_names(self, used: set[str]):
        """设置「已添加」的名称集合 —— 会在子菜单里显示 ✓ 已添加并置灰。"""
        self._used = set(used)

    def build(self):
        """构造菜单结构。可重复调用以刷新「已添加」状态。"""
        self.clear()
        used = self._used
        for t_key, t_name in model.PAYITEM_TYPES:
            sub = QMenu(self)
            sub.setStyleSheet(_MENU_QSS)
            sub.setToolTipsVisible(True)
            catalog = model.PAYITEM_CATALOG.get(t_key, [])
            head = sub.addAction(self._dot_icon(config.TYPE_DOT.get(t_key, "#98A2B3")),
                                 f"{t_name}（{len(catalog)} 项）")
            head.setEnabled(False)
            for cname in catalog:
                act = QAction("    " + cname, sub)
                if cname in used:
                    act.setEnabled(False)
                    act.setText(f"    {cname}    ✓ 已添加")
                else:
                    act.triggered.connect(
                        lambda _=False, k=t_key, n=cname: self.item_chosen.emit(k, n))
                sub.addAction(act)
            sub.addSeparator()
            custom = sub.addAction("    ＋ 输入自定义名称…")
            custom.setToolTip(model.PAYITEM_TYPE_DESC.get(t_key, ""))
            custom.triggered.connect(lambda _=False, k=t_key: self.custom_requested.emit(k))

            entry = self.addMenu(sub)
            color = config.TYPE_DOT.get(t_key, "#98A2B3")
            entry.setIcon(self._dot_icon(color, 10))
            free = sum(1 for n in catalog if n not in used)
            tip = model.PAYITEM_TYPE_DESC.get(t_key, "")
            tip = f"{tip}\n剩余可选 {free} / {len(catalog)}"
            entry.setToolTip(tip)
            entry.setText(
                f"{t_name}    已全部添加" if free == 0
                else f"{t_name}    可选 {free} 项  ▸"
            )

    def popup_for(self, btn: QPushButton):
        """绑定到具体按钮下方弹出。如未传按钮则 exec() 显示。"""
        self.build()
        if btn is not None:
            self.popup(btn.mapToGlobal(QPoint(0, btn.height() + 6)))
        else:
            self.exec_()

    @staticmethod
    def _dot_icon(color: str, d: int = 12) -> QIcon:
        """生成圆点图标（菜单表头的小色点）。"""
        pm = QPixmap(d, d)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        p.drawEllipse(1, 1, d - 2, d - 2)
        p.end()
        return QIcon(pm)
