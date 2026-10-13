"""「相关单位」页（与工作台同级的独立页面）。

同一段劳动关系里可能涉及多家单位 —— 现实中「签合同的公司」「缴社保的公司」
「发工资的公司」「实际干活的单位」常常不是同一家（集团 / 分公司 / 劳务派遣 /
社保代缴 / 工资代发等）。本页按类型（见 :data:`model.UNIT_ROLES`）分开登记
名称与统一社会信用代码，便于核对责任主体、社保连续性与工龄。

**同一类型可以有多家**（例如先后 / 同时签过多份劳动合同的单位）：每行都可改类型、
可增可删，行顺序即显示顺序。内置类型之外的单位选「其他相关单位」，具体是什么写在
**名称**栏。

**与月份无关**：相关单位是「单位档案」，全月共用一份，只存在应用设置里
（``settings.json`` 的 ``units``）—— 切月不会变，本页也不显示月份操作条，
**不读也不写月度存档**，也**不参与「参数」页的参数模板**（存 / 套模板都不动单位表）。
全新安装时按**内置类型各列一行**（不含「其他相关单位」），
空的直接填；同一类型的第二家 / 自定义单位用「＋ 添加单位」。

**锁定**：只有**本页自己的锁**（卡片标题栏右侧的 🔒 按钮，会话级）能让它只读 ——
顶部的「月份锁定」不影响本页（数据根本不在月份里）。只读时名称 / 编号 / 增删都冻结，
但 **「🔍 去搜索」仍然可用**（它只查外部网站，不改数据）。
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QComboBox, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMenu, QPushButton, QVBoxLayout)

from . import model
from .ui import (make_lock_banner, make_lock_button, set_lock_button_state,
                 show_lock_banner)
from .widgets import Card

# 表头文字（与数据行同一网格的第 0 行）
_HEADERS = ("类型", "单位名称", "统一社会信用代码（选填）")

# 本页自己的锁的横幅文案（月份锁定与本页无关，所以只有这一种）
UNITS_LOCK_BANNER_TEXT = ("🔒  单位登记表已锁定 · 名称 / 编号已冻结，增删已屏蔽"
                          "（🔍 去搜索仍可用）；点标题栏右侧按钮可解锁")

# 「🔍 去搜索」用的两个公开查询站点（可在菜单里切换）。
# ⚠ 两站都是 JS 应用、不支持 URL 带关键词（实测抓到的只是壳页），所以做法是
# 「把关键词复制到剪贴板 + 打开站点」，用户粘到搜索框即可。
UNIT_SEARCH_SITES = (
    ("gsxt", "国家企业信用信息公示系统", "https://www.gsxt.gov.cn/index.html"),
    ("credit", "信用中国", "https://www.creditchina.gov.cn/"),
)

# 类型 → 顺序（内置类型在表里的先后）：新行按它排序插入，只算一次
_ROLE_ORDER = {key: i for i, key in enumerate(model.UNIT_ROLE_KEYS)}
# 「＋ 添加单位」菜单里代表「其他相关单位」的那一项（不是真类型 key）
_CUSTOM_MENU_KEY = "__custom__"


class _UnitRow:
    """单位登记表里的一行：一条 ``RelatedUnit`` + 该行的 5 个控件。

    控件与 ``unit`` 一一对应，所以「改控件 → 写回 unit」不必再去列表里按类型查找。
    ``action_btn`` 是行尾动作按钮：普通单位是「🔍 去搜索」，
    **工资代发银行**行是「📋 复制」（名称 + 联行号 / 账号一起复制，
    联行号在那两个信用查询站里查不到）。
    """

    __slots__ = ("unit", "role", "name", "code", "action_btn", "del_btn")

    def __init__(self, unit: model.RelatedUnit, role: QComboBox, name: QLineEdit,
                 code: QLineEdit, action_btn: QPushButton, del_btn: QPushButton):
        self.unit = unit
        self.role = role
        self.name = name
        self.code = code
        self.action_btn = action_btn
        self.del_btn = del_btn

    def widgets(self) -> tuple:
        """按列顺序返回 5 个控件（类型 / 名称 / 编号 / 行尾动作 / 删除）。"""
        return (self.role, self.name, self.code, self.action_btn, self.del_btn)


class UnitsPageMixin:
    """相关单位页 mixin（由 MainWindow 多继承）。"""

    # 会话级状态（切页 / 切月重建页面都要保留）：类属性只作默认值，实例上再赋值
    _units_locked = False        # 本页自己的锁
    _units_cache = None          # 全局单位表的内存副本（懒加载，见 _units_list）
    _unit_search_last = None     # 上次用过的查询站点 key

    def _fill_units(self):
        """构建相关单位页（切月 / 重建时重新填充，避免残留旧控件）。"""
        root = self.units_root
        if not hasattr(self, "_units_lay"):
            self._units_lay = QVBoxLayout(root)
            self._units_lay.setContentsMargins(20, 16, 20, 20)
            self._units_lay.setSpacing(12)
        lay = self._units_lay
        self._clear_layout(lay)

        # —— 只读提示横幅（只有本页自己的锁；月份锁定与本页无关）——
        self._units_lock_banner = make_lock_banner(UNITS_LOCK_BANNER_TEXT)
        lay.addWidget(self._units_lock_banner)

        lay.addWidget(self._make_units_card())
        lay.addStretch(1)
        self._relayout_unit_rows()
        self._refresh_units_lock_ui()

    # ---------- 全局单位表的读写 ----------

    def _units_list(self) -> list[model.RelatedUnit]:
        """全局相关单位（与月份无关；首次访问时从 settings 读一次并缓存在内存）。

        全新安装（设置里**没有** units 键）→ 按内置类型**各列一行**（名称 / 编号留空，
        直接填）；一旦保存过就以存的那份为准 —— **删掉的行不会自己回来**。
        返回的就是内部列表本身，调用方可直接增删改（改完调 :meth:`_save_units`）。
        """
        if self._units_cache is None:
            if self.store.UNITS_KEY in self.store.load_settings():
                self._units_cache = self.store.load_units()
            else:
                self._units_cache = model.default_units()
        return self._units_cache

    def _save_units(self) -> None:
        """单位表改动 → 写 settings.json。

        **不碰月度存档**（相关单位与月份无关）：所以顶部的月份锁不会拦住它，
        也不会让当前月份变成「有未保存改动」。settings.json 很小、单位也不是
        高频输入，就**直接落盘**（不做防抖：避免切页 / 关窗时丢掉未落盘的改动）。
        """
        if not self._units_ready():
            return
        ok = self.store.save_units(self._units_list())
        # background=True：逐字输入时不去顶掉其它业务提示（如「已复制到剪贴板…」）
        self._set_status(("单位表已保存 " + datetime.now().strftime("%H:%M:%S")) if ok
                         else "单位表保存失败，请检查数据目录权限",
                         ok, background=True)

    def _make_units_card(self) -> Card:
        """「单位登记表」卡片：表头 + 行网格 + 空状态提示 + 按钮行。

        ⚠ 表头（第 0 行）与数据行必须在**同一个网格**里 —— 两个独立网格的列宽不会对齐。
        """
        card = Card("单位登记表",
                    hint="已按内置类型各列一行，空的直接填；同一类型可以有多家时点「＋ 添加单位」"
                         "（例如先后 / 同时签过多份劳动合同）；列表里没有的类型选「其他相关单位」，"
                         "具体是什么写在「单位名称」栏",
                    toolbar=True)
        # 本页自己的锁（会话级）：与月份无关，顶部的月份锁定不影响本页。
        self._units_lock_btn = make_lock_button(
            "锁定 / 解锁「单位登记表」：\n"
            "· 锁定时名称、编号、增删都不可改，但「🔍 去搜索」仍可用\n"
            "· 相关单位与月份无关，顶部的「月份锁定」不影响本页",
            self._toggle_units_lock)
        card.add_toolbar_widget(self._units_lock_btn)
        self._units_grid = QGridLayout()
        self._units_grid.setHorizontalSpacing(12)
        self._units_grid.setVerticalSpacing(8)
        self._units_grid.setColumnStretch(1, 3)
        self._units_grid.setColumnStretch(2, 3)
        card.add_layout(self._units_grid)
        self._units_head_labels = []
        for text in _HEADERS:
            lab = QLabel(text)
            lab.setObjectName("fldLabel")
            self._units_head_labels.append(lab)
        # 每行绑定一条全局 RelatedUnit；行顺序即显示顺序
        self._unit_rows: list[_UnitRow] = [self._make_unit_row(u) for u in self._units_list()]

        self._units_empty_hint = QLabel("单位表是空的 —— 点下面「＋ 添加单位」选一个类型"
                                        "（列表里没有的类型就选「✏️ 自定义（填在名称栏）…」）")
        self._units_empty_hint.setObjectName("secHint")
        self._units_empty_hint.setToolTip(
            "选「＋ 添加单位」→ 选一个类型（列表里没有就选「✏️ 自定义（填在名称栏）…」），再填名称")
        card.add_widget(self._units_empty_hint)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        add_btn = QPushButton("＋ 添加单位")
        add_btn.setObjectName("primary")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setToolTip("先选一个单位类型；列表里没有的选「✏️ 自定义（填在名称栏）…」")
        add_btn.clicked.connect(self._open_add_unit_menu)
        self._add_unit_btn = add_btn
        btns.addWidget(add_btn)
        btns.addStretch(1)
        card.add_layout(btns)
        self._units_card = card
        return card

    def _units_is_locked(self) -> bool:
        """单位登记表是否被**自己的锁**锁住（会话级状态，不写进存档）。"""
        return bool(self._units_locked)

    def _units_ready(self) -> bool:
        """页面是否可用（重建过程中忽略交互）。

        相关单位是**全局**数据（不在月份里）→ 不看 `_book` / `_is_locked`。
        """
        return not self._loading

    def _refresh_units_lock_ui(self) -> None:
        """按**本页自己的锁**刷新：卡片可写控件禁用 + 横幅 + 锁按钮文案。

        两个**只读**动作在锁定时仍须可用（同「锁定月仍可导出 Excel」的口径）：
        · 行尾按钮：🔍 去搜索 / 📋 复制，都不改数据；
        · 锁按钮自己 —— `Card.set_locked` 会把它一并禁用，不放行就再也解不开了。
        """
        locked = self._units_is_locked()
        self._units_card.set_locked(locked)
        for w in (*[r.action_btn for r in self._unit_rows], self._units_lock_btn):
            try:
                w.setEnabled(True)
            except RuntimeError:      # 极端情况：行 / 按钮已被销毁
                pass
        set_lock_button_state(self._units_lock_btn, locked)
        show_lock_banner(self._units_lock_banner, locked)

    def _toggle_units_lock(self) -> None:
        """切换单位登记表自己的锁（不写盘，也不影响当前月份）。"""
        self._units_locked = not self._units_is_locked()
        self._refresh_units_lock_ui()
        if self._units_locked:
            self._set_status("单位登记表已锁定：名称 / 编号不可修改，「🔍 去搜索」仍可用", True)
        else:
            self._set_status("单位登记表已解锁：可以增删 / 修改单位", True)

    # ---------- 行的构建 / 布局 ----------

    @staticmethod
    def _code_placeholder(role: str) -> str:
        """编号栏占位提示（工资代发银行填联行号 / 账号，其余填统一社会信用代码）。"""
        return f"{model.UNIT_ROLE_CODE_LABELS.get(role, '统一社会信用代码')}（选填）"

    def _units_can_edit(self) -> bool:
        """相关单位是否可改：页面可用且本页自己的锁没锁上（与月份无关）。"""
        return self._units_ready() and not self._units_is_locked()

    def _make_unit_row(self, u: model.RelatedUnit) -> _UnitRow:
        """建一行：类型（下拉，**不可编辑**）+ 名称 + 编号 + 行尾动作 + 删除。

        控件都绑定同一个 ``RelatedUnit``；行尾按钮的行为按类型定（见
        :meth:`_refresh_unit_row_action`）。「其它单位」不靠手打类型：
        类型选「其他相关单位」，具体是什么写在**名称**栏。
        """
        role = QComboBox()
        role.addItems([model.UNIT_ROLE_LABELS[k] for k in model.UNIT_SELECTABLE_KEYS])
        idx = role.findText(u.type_name())
        # 兜底：类型名万一不在列表里（不应发生）就落到最后一项「其他相关单位」
        role.setCurrentIndex(idx if idx >= 0 else role.count() - 1)
        role.setMinimumWidth(180)
        role.setToolTip(model.UNIT_ROLE_HINTS.get(u.role, ""))

        name = QLineEdit(u.name)
        name.setPlaceholderText("单位名称")
        name.setMinimumWidth(200)

        code = QLineEdit(u.code)
        code.setPlaceholderText(self._code_placeholder(u.role))
        code.setMinimumWidth(160)

        action_btn = QPushButton("🔍")
        action_btn.setObjectName("ghost")
        action_btn.setFixedWidth(34)
        action_btn.setCursor(Qt.PointingHandCursor)

        del_btn = QPushButton("✕")
        del_btn.setObjectName("ghost")
        del_btn.setToolTip("删除这一行（只删这一条单位，不影响其他行）")
        del_btn.setFixedWidth(34)
        del_btn.setCursor(Qt.PointingHandCursor)

        row = _UnitRow(u, role, name, code, action_btn, del_btn)
        # textEdited 只在**用户输入**时触发 → 代码里 setText（回填 / 重建）不会反向触发保存
        name.textEdited.connect(lambda _t, r=row: self._sync_unit_row(r))
        code.textEdited.connect(lambda _t, r=row: self._sync_unit_row(r))
        role.currentTextChanged.connect(lambda _t, r=row: self._on_unit_type_changed(r))
        action_btn.clicked.connect(lambda _checked=False, r=row: self._on_unit_row_action(r))
        del_btn.clicked.connect(lambda _checked=False, r=row: self._remove_unit_row(r))
        # 行尾按钮的行为 / 图标 / 提示由类型决定（银行行是复制，其余是搜索）
        self._refresh_unit_row_action(row)
        return row

    def _refresh_unit_row_action(self, row: _UnitRow) -> None:
        """按当前类型刷新行尾按钮：银行 → 「📋 复制」，其它 → 「🔍 去搜索」。"""
        if row.unit.role == model.UNIT_ROLE_BANK:
            row.action_btn.setText("📋")
            row.action_btn.setToolTip(
                "复制这一行的两个值到剪贴板（各占一行）：银行名称 + 联行号 / 账号\n"
                "只填了一个就只复制那一个；银行不在「国家企业信用信息公示系统」 / "
                "「信用中国」里查，所以这里是复制")
        else:
            row.action_btn.setText("🔍")
            row.action_btn.setToolTip(
                "去查这家单位（可切换站点）：\n"
                "· 国家企业信用信息公示系统\n· 信用中国\n"
                "优先复制「统一社会信用代码」（没填则用「单位名称」），粘到网站搜索框即可")

    def _on_unit_row_action(self, row: _UnitRow) -> None:
        """行尾按钮：工资代发银行行是**复制**（两个值一起），其余行是**去搜索**。"""
        if row.unit.role == model.UNIT_ROLE_BANK:
            self._copy_unit_values(row)
        else:
            self._open_unit_search_menu(row)

    def _copy_unit_values(self, row: _UnitRow) -> None:
        """把这一行的**两个值都**复制到剪贴板（银行名称 + 联行号 / 账号，各占一行）。

        用户 2026-10-13 要求银行一次复制两个（填进银行回单 / 付款表单时两个都要用）；
        只填了其中一个时只复制那一个，都没填则只提示、不动剪贴板。
        **只读**动作：与本页的锁无关，锁定时也允许（所以不看 _units_can_edit）。
        """
        if not self._units_ready():
            return
        values = [v for v in (row.unit.name.strip(), row.unit.code.strip()) if v]
        if not values:
            self._set_status("请先填写「银行名称」或「联行号 / 账号」，再复制", False)
            return
        QApplication.clipboard().setText("\n".join(values))
        self._set_status("已复制到剪贴板：" + " / ".join(values), True,
                         hold_ms=self.STATUS_HOLD_MS_CLIP)

    def _relayout_unit_rows(self) -> None:
        """按 ``self._unit_rows`` 的顺序重排网格（增 / 删行后调用）。

        表头（第 0 行）与数据行在**同一个网格**里，列宽才能对齐。
        """
        grid = getattr(self, "_units_grid", None)
        if grid is None:
            return
        while grid.count():
            grid.takeAt(0)
        for col, lab in enumerate(getattr(self, "_units_head_labels", [])):
            grid.addWidget(lab, 0, col)
        rows = getattr(self, "_unit_rows", [])
        for i, r in enumerate(rows):
            for col, w in enumerate(r.widgets()):
                grid.addWidget(w, i + 1, col)
        hint = getattr(self, "_units_empty_hint", None)
        if hint is not None:
            hint.setVisible(not rows)
        # 锁定态下新加的行也必须禁用（Card 只追踪 layout，新增后要重新施加一次）
        if self._units_is_locked():
            self._refresh_units_lock_ui()

    def _insert_pos_for_role(self, role: str) -> int:
        """新行的插入位置：紧跟同一类型的最后一行；没有同类型行时按类型顺序插。"""
        target = _ROLE_ORDER.get(role, len(_ROLE_ORDER))
        pos = 0
        for i, r in enumerate(self._unit_rows):
            if r.unit.role == role or _ROLE_ORDER.get(r.unit.role, len(_ROLE_ORDER)) < target:
                pos = i + 1
        return pos

    def _insert_unit(self, pos: int, unit: model.RelatedUnit) -> _UnitRow:
        """在 pos 处同时插入行与全局单位（``_unit_rows`` 与全局列表必须按下标平行）。"""
        row = self._make_unit_row(unit)
        self._unit_rows.insert(pos, row)
        self._units_list().insert(pos, unit)
        return row

    def _drop_unit_row(self, row: _UnitRow) -> None:
        """从行列表与全局单位表里同时摘掉（按**对象身份**定位，同值对象不能按值删）。"""
        for i, r in enumerate(self._unit_rows):
            if r is row:
                del self._unit_rows[i]
                break
        for j, u in enumerate(self._units_list()):
            if u is row.unit:
                del self._units_list()[j]
                break

    # ---------- 增 / 删 / 改 ----------

    def _open_unit_search_menu(self, row: _UnitRow) -> None:
        """「🔍」→ 选一个站点去查这家单位（两个站点随时切换）。

        关键词**优先用统一社会信用代码**（唯一、精确），没填则用单位名称。
        ⚠ 两站都不支持 URL 带关键词，所以是「复制关键词到剪贴板 + 打开站点」；
        上次用过的站点会在菜单里打勾（再点另一个就是切换）。
        **只读**动作：与本页的锁无关，锁定时也允许（所以不看 _units_can_edit）。
        """
        if not self._units_ready():
            return
        btn = row.action_btn
        term = row.unit.code.strip() or row.unit.name.strip()
        if not term:
            self._set_status("请先填写「统一社会信用代码」或「单位名称」，再去搜索", False)
            return
        menu = QMenu(self)
        menu.addSection(f"去搜索：{term}")
        for key, label, _url in UNIT_SEARCH_SITES:
            act = menu.addAction(label)
            act.setData(key)
            act.setCheckable(True)
            act.setChecked(key == self._unit_search_last)   # 打勾 = 上次用的站点
        chosen = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if chosen is None:
            return  # 点了空白处 / Esc
        key = chosen.data()
        label, url = next((lab, u) for k, lab, u in UNIT_SEARCH_SITES if k == key)
        self._unit_search_last = key
        QApplication.clipboard().setText(term)
        QDesktopServices.openUrl(QUrl(url))
        # 提醒得说清楚「东西已经进剪贴板了」——浏览器一弹出来偷走焦点，
        # 用户回到软件时如果只看到「已保存」就不知道该粘什么了。
        # ⚠ 不写按键名字（用户 2026-10-13：「不要提示按键」）。
        self._set_status(
            f"已复制到剪贴板：{term} —— 在打开的「{label}」搜索框里粘贴即可",
            True, hold_ms=self.STATUS_HOLD_MS_CLIP)

    def _open_add_unit_menu(self) -> None:
        """「＋ 添加单位」→ 先选类型（11 个内置类型 + 「✏️ 自定义（填在名称栏）…」）。"""
        btn = getattr(self, "_add_unit_btn", None)
        if btn is None or not self._units_can_edit():
            return
        menu = QMenu(self)
        for key in model.UNIT_ROLE_KEYS:
            act = menu.addAction(model.UNIT_ROLE_LABELS[key])
            act.setData(key)
            act.setToolTip(model.UNIT_ROLE_HINTS.get(key, ""))
        menu.addSeparator()
        custom = menu.addAction("✏️ 自定义（填在名称栏）…")
        custom.setData(_CUSTOM_MENU_KEY)
        custom.setToolTip("加一行「其他相关单位」，光标会落在「单位名称」栏 —— "
                          "直接把具体单位写在那里，例如「补充医疗保险公司」")
        chosen = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if chosen is None:
            return  # 用户点了空白处 / Esc
        key = chosen.data()
        if key == _CUSTOM_MENU_KEY:
            self._add_unit_row(model.UNIT_ROLE_OTHER)
        else:
            self._add_unit_row(key)

    def _add_unit_row(self, role: str = model.UNIT_ROLE_DEFAULT) -> None:
        """新增一行（类型由调用方给出），并把焦点放到「单位名称」框。"""
        if not self._units_can_edit():
            return
        unit = model.RelatedUnit(
            role=role if role in model.UNIT_ROLE_LABELS else model.UNIT_ROLE_OTHER)
        row = self._insert_unit(self._insert_pos_for_role(unit.role), unit)
        self._relayout_unit_rows()
        self._save_units()
        try:
            row.name.setFocus()
        except RuntimeError:      # 极端情况：行已被销毁
            pass

    def _remove_unit_row(self, row: _UnitRow) -> None:
        """删除一行（只删这一条单位，同值的其它行不受影响）。"""
        if not self._units_can_edit():
            return
        self._drop_unit_row(row)
        for w in row.widgets():
            w.setParent(None)
            w.deleteLater()
        self._relayout_unit_rows()
        self._save_units()

    def _sync_unit_row(self, row: _UnitRow) -> None:
        """名称 / 编号输入改动 → 写回该行绑定的相关单位并保存。"""
        if not self._units_can_edit():
            return
        row.unit.name = row.name.text().strip()
        row.unit.code = row.code.text().strip()
        self._save_units()

    def _on_unit_type_changed(self, row: _UnitRow) -> None:
        """类型下拉改变 → 写回单位表（自定义内容在「名称」栏，不在这里）。"""
        if not self._units_can_edit():
            return
        key = model.resolve_unit_role(row.role.currentText())
        if key == row.unit.role:
            return
        row.unit.role = key
        row.role.setToolTip(model.UNIT_ROLE_HINTS.get(key, ""))
        row.code.setPlaceholderText(self._code_placeholder(key))
        self._refresh_unit_row_action(row)      # 改成 / 改出「工资代发银行」时按钮要跟着变
        self._save_units()
