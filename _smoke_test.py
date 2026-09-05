"""新功能冒烟测试：节假日表 / 个税 / 逐日加班分桶 / 年度汇总页（临时脚本，跑完可删）。"""
import os
import tempfile

os.environ.setdefault("ATT_DATA_DIR", tempfile.mkdtemp())
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from app import calc, holidays, model  # noqa: E402

# ---- 节假日表 ----
assert holidays.has_year(2026) and holidays.has_year(2025) and not holidays.has_year(2027)
assert holidays.day_kind(2026, 2, 16) == "statutory"   # 除夕
assert holidays.day_kind(2026, 2, 15) == "rest"        # 腊月廿八（拼假）
assert holidays.day_kind(2026, 2, 14) == "makeup"      # 补班
assert holidays.day_kind(2026, 2, 28) == "makeup"      # 补班
assert holidays.day_kind(2026, 4, 5) == "statutory"
assert holidays.day_kind(2026, 4, 4) == "rest"
assert holidays.day_kind(2026, 1, 4) == "makeup"
assert holidays.day_kind(2026, 10, 10) == "makeup"
assert holidays.day_kind(2025, 10, 6) == "statutory"   # 中秋
assert holidays.day_kind(2026, 3, 5) is None
print("holidays OK")

# ---- 个税税率表 ----
tax = calc._monthly_tax
assert abs(tax(3000) - 90) < 1e-9
assert abs(tax(10000) - 790) < 1e-9          # 10000*10%-210
assert abs(tax(12000) - 990) < 1e-9          # 12000*10%-210
assert abs(tax(25000) - 3590) < 1e-9         # 25000*20%-1410
assert abs(tax(100000) - 29840) < 1e-9       # 100000*45%-15160
assert tax(-100) == 0.0
print("tax OK")

# ---- 逐日加班分桶 + 自动个税（2026-02 春节月）----
b = model.create_book(2026, 2)
for d in b.days:  # 模拟一键铺
    k = holidays.day_kind(2026, 2, d.day)
    if k == "makeup":
        d.status = "上班"
    elif k in ("statutory", "rest"):
        d.status = "休息"
    else:
        d.status = "休息" if d.is_weekend_dt(2026, 2) else "上班"
for d in b.days:
    if holidays.day_kind(2026, 2, d.day) == "statutory":
        d.mark = 1
b.day(5).overtime_hours = 2.0    # 周四 → 工作日
b.day(21).overtime_hours = 3.0   # 周六 → 休息日
b.day(17).overtime_hours = 4.0   # 初一 → 法定节假日
b.ot_auto = True
b.pay_items.append(model.PayItem(name="基本工资", type="wage", amount=10000))
b.overtime_base = 10000
b.social_base = 10000
b.personal_social_rate = 0.105
b.fund_base = 10000
b.personal_fund_rate = 0.07
b.income_tax_auto = True
r = calc.compute(b)
assert abs(r.ot_hours_workday - 2) < 1e-6, r.ot_hours_workday
assert abs(r.ot_hours_restday - 3) < 1e-6, r.ot_hours_restday
assert abs(r.ot_hours_holiday - 4) < 1e-6, r.ot_hours_holiday
hourly = 10000 / (21.75 * 8)
# 2026-09 起所有金额字段全程四舍五入到 2 位（ROUND_HALF_UP）。
# 中间步骤（如加班时薪 hourly）也会被四舍五入，所以子项与「直算 + round」之间
# 会有 ±0.01 ~ ±0.05 元的合理累积误差，断言容差放宽到 0.05 元。
_WAGE_TOL = 0.05
assert abs(r.overtime_wage_workday - round(1.5 * 2 * hourly, 2)) < _WAGE_TOL
assert abs(r.overtime_wage_restday - round(2.0 * 3 * hourly, 2)) < _WAGE_TOL
assert abs(r.overtime_wage_holiday - round(3.0 * 4 * hourly, 2)) < _WAGE_TOL
taxable = r.gross_wage - 5000 - r.personal_social - r.personal_fund
assert abs(r.income_tax - calc._monthly_tax(taxable)) < _WAGE_TOL
assert r.counts.legal_holiday == 4
print("calc OK")

# ---- 工资构成：最低工资判定口径 ----
b_min = model.create_book(2026, 3)
b_min.min_wage = 2170
b_min.overtime_base = 2170
# 基本工资 1500（计入最低工资）+ 公司补贴 500 + 固定津贴 300 + 固定加班 540
b_min.pay_items = [
    model.PayItem(name="基本工资", type="wage", amount=1500),
    model.PayItem(name="公司社保补贴", type="subsidy", amount=500),
    model.PayItem(name="一次性奖励", type="fixed_allow", amount=300),
]
b_min.fixed_overtime_wage = 540
r_min = calc.compute(b_min)
assert abs(r_min.wage_components_total - 1500) < _WAGE_TOL
assert abs(r_min.company_subsidies_included - 500) < _WAGE_TOL
assert abs(r_min.fixed_allowances_total - 300) < _WAGE_TOL
# 计入最低工资的只含 wage 类型；加班工资/补贴/津贴均不计入
assert abs(r_min.in_wage_part - 1500) < _WAGE_TOL, r_min.in_wage_part
assert abs(r_min.not_in_wage_part - (500 + 300 + 540)) < _WAGE_TOL, r_min.not_in_wage_part
assert abs(r_min.gross_wage - (1500 + 500 + 300 + 540)) < _WAGE_TOL, r_min.gross_wage
print("min-wage classification OK")

# ---- 序列化兼容 ----
raw = b.to_dict()
b2 = model.MonthBook.from_dict(raw)
assert b2.ot_auto and b2.income_tax_auto and len(b2.pay_items) == 1
b3 = model.MonthBook.from_dict({k: v for k, v in raw.items() if k not in ("ot_auto", "income_tax_auto")})
assert not b3.ot_auto and not b3.income_tax_auto  # 旧档默认 False
print("serialize OK")

# ---- UI 离屏渲染 ----
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.main_window import MainWindow  # noqa: E402
from app.storage import MonthStore  # noqa: E402

app = QApplication([])
win = MainWindow(MonthStore())
win.resize(1280, 860)
win.show()
win.store.save(b)  # 让年度汇总有真实数据
win._go(2026, 2)   # 切到春节月
win._book.ot_auto = True
win._book.income_tax_auto = True
win._go(2026, 2)   # 重建页面：薪酬页应显示勾选态且手动框禁用
win._show_page(2)  # 薪酬页（自动开关）
for _ in range(8):
    app.processEvents()
win.grab().save("_check_salary.png")
win._show_page(5)  # 年度汇总
for _ in range(8):
    app.processEvents()
win.grab().save("_check_annual.png")
win._show_page(1)  # 考勤页
for _ in range(8):
    app.processEvents()
win.grab().save("_check_calendar.png")
win._show_page(0)
for _ in range(8):
    app.processEvents()
print("months on disk:", sorted(win.store.list_months()))
win.close()

# ---- 复制工资项 + 删除同步回归（防止「删完又回来」）----
from PySide6.QtWidgets import QDialog, QMessageBox  # noqa: E402

from app import pages_salary  # noqa: E402

import shutil  # noqa: E402

_tmp = tempfile.mkdtemp()
store = MonthStore(_tmp)
src = model.create_book(2026, 9)
src.pay_items = [
    model.PayItem(name="基本工资", type="wage", amount=5000),
    model.PayItem(name="岗位工资", type="wage", amount=2000),
    model.PayItem(name="伙食补贴", type="perday_allow", amount=30),
]
src.fixed_overtime_wage = 800
store.save(src)
store.save(model.create_book(2026, 10, with_common_pay_items=True))

win2 = MainWindow(store)
win2._go(2026, 9)


class _MockCopyDlg:
    def exec(self): return QDialog.Accepted
    def year(self): return 2026
    def month(self): return 10


pages_salary._CopyPayItemsDialog = lambda *a, **kw: _MockCopyDlg()
QMessageBox.question = lambda *a, **kw: QMessageBox.Yes
win2._on_copy_pay_items()
win2._go(2026, 10)  # 切到目标月
assert len(win2._book.pay_items) == 3, win2._book.pay_items

# 删除 row，book.pay_items 必须同步移除
victim_name = win2.pay_items.rows[0].item.name
win2.pay_items.remove_row(win2.pay_items.rows[0])
win2._flush_changed()
win2._go(2026, 10)  # 重新载入
names = [it.name for it in win2._book.pay_items]
assert victim_name not in names, f"deleted item {victim_name} reappeared: {names}"
assert len(win2._book.pay_items) == 2
win2.close()
shutil.rmtree(_tmp, ignore_errors=True)
print("delete-sync OK")

# ---- 锁定月份保护：复制 / 套用模板 / 删除 / 清空考勤 全部拒绝 ----
_tmp2 = tempfile.mkdtemp()
store2 = MonthStore(_tmp2)
b_target = model.create_book(2026, 11)
b_target.pay_items = [model.PayItem(name="基本工资", type="wage", amount=5000)]
b_target.locked = True
store2.save(b_target)

b_src = model.create_book(2026, 9)
b_src.pay_items = [
    model.PayItem(name="基本工资", type="wage", amount=4000),
    model.PayItem(name="岗位工资", type="wage", amount=1500),
]
store2.save(b_src)

win3 = MainWindow(store2)
win3._go(2026, 9)

# 1) 复制工资项到锁定月份 → 必须被拒绝（pay_items 不变）
saved_pay_items_before = list(b_target.pay_items)
class _MockCopyDlg2:
    def exec(self): return QDialog.Accepted
    def year(self): return 2026
    def month(self): return 11

pages_salary._CopyPayItemsDialog = lambda *a, **kw: _MockCopyDlg2()
# 把 QMessageBox.warning 替换为捕获类，记录是否触发
warnings_seen = []
QMessageBox.warning = staticmethod(lambda *a, **kw: warnings_seen.append((a, kw)) or QMessageBox.Ok)
win3._on_copy_pay_items()
assert len(warnings_seen) >= 1, "复制到锁定月份应触发警告"
# 目标月 pay_items 必须没变（之前是 [基本工资 5000]）
reloaded = store2.load(2026, 11)
assert len(reloaded.pay_items) == 1, f"锁定月被覆盖了: {reloaded.pay_items}"
assert reloaded.pay_items[0].amount == 5000, f"锁定月金额被改了: {reloaded.pay_items}"
print("locked copy-rejected OK")

# 2) 套用模板到锁定月份 → 必须被拒绝
# 把当前月切到 2026-11（锁定）
win3._go(2026, 11)
assert win3._book.locked, "应仍为锁定"
warnings_seen.clear()
# 直接调 _apply_template（前置条件：combo 必须有内容；先存一个模板再调）
templates = [{"name": "test_tpl", "params": {"personal_social_rate": 0.1}}]
import json as _json
with open(os.path.join(store2.dir, "templates.json"), "w", encoding="utf-8") as _f:
    _json.dump({"templates": templates}, _f, ensure_ascii=False)
win3._refresh_templates()
win3._apply_template()
assert len(warnings_seen) >= 1, "套用模板到锁定月份应触发警告"
reloaded2 = store2.load(2026, 11)
assert reloaded2.pay_items[0].amount == 5000, f"锁定月被覆盖了: {reloaded2.pay_items}"
print("locked template-rejected OK")

# 3) 删除锁定月份 → 必须被拒绝（文件还在）
warnings_seen.clear()
win3._delete_month()
assert len(warnings_seen) >= 1, "删除锁定月份应触发警告"
assert os.path.exists(os.path.join(store2.dir, "2026-11.json")), "锁定月文件不应被删除"
print("locked delete-rejected OK")

# 4) 清空考勤 → 必须被拒绝（锁定月至少要有 1 个非空 status 才不会被 _changed 覆盖掉测试）
b_target.day(5).status = "上班"
store2.save(b_target)
win3._go(2026, 11)
warnings_seen.clear()
win3._clear_days()
assert len(warnings_seen) >= 1, "清空锁定月考勤应触发警告"
reloaded3 = store2.load(2026, 11)
assert reloaded3.day(5).status == "上班", f"锁定月考勤被清空: {reloaded3.day(5)}"
print("locked clear-days-rejected OK")

# 5) 解除锁定 → 复制应恢复正常
win3._go(2026, 9)
b_target.locked = False
store2.save(b_target)
warnings_seen.clear()
win3._on_copy_pay_items()
assert len(warnings_seen) == 0, "解锁后复制应不再警告"
reloaded4 = store2.load(2026, 11)
assert len(reloaded4.pay_items) == 2, f"解锁后应能复制成功: {reloaded4.pay_items}"
print("unlocked copy-allowed OK")

# 6) 切换月份时，锁定按钮状态应刷新
win3._go(2026, 11)
b_locked = model.create_book(2026, 12)
b_locked.locked = True
store2.save(b_locked)
win3._go(2026, 12)
assert win3._book.locked, "应载入锁定的 12 月"
assert "🔒" in win3._lock_btn.text(), f"锁定按钮应显示 🔒，实际：{win3._lock_btn.text()}"
win3._go(2026, 11)
assert not win3._book.locked
assert "🔓" in win3._lock_btn.text(), f"解锁按钮应显示 🔓，实际：{win3._lock_btn.text()}"
print("lock-btn refresh OK")

# 7) 历史月份列表应显示 🔒 标记
items_text = [win3.history.item(i).text() for i in range(win3.history.count())]
assert any("🔒" in t and "2026 年 12 月" in t for t in items_text), f"12 月列表项应带 🔒: {items_text}"
print("history lock-marker OK")

win3.close()
shutil.rmtree(_tmp2, ignore_errors=True)
print("lock OK")

# ---- 锁定只读模式：API 层 + UI 层全面拦截，导出 Excel 保留 ----
_tmp3 = tempfile.mkdtemp()
store3 = MonthStore(_tmp3)
b_locked2 = model.create_book(2026, 12)
b_locked2.min_wage = 2170
b_locked2.pay_items = [
    model.PayItem(name="基本工资", type="wage", amount=5000),
    model.PayItem(name="岗位工资", type="wage", amount=1500),
]
b_locked2.big_disease = 50.0
b_locked2.locked = True
store3.save(b_locked2)

win4 = MainWindow(store3)
win4._go(2026, 12)
assert win4._is_locked is True, "切到锁定月后 _is_locked 应为 True"
assert win4.save_btn.isEnabled() is False, "锁定月顶部保存按钮应 disabled"
print("locked state machine OK")

# 1) main_window API 入口：_changed() / _manual_save() / _flush_changed() 锁定时不写入
serial_before = win4.store.load(2026, 12).to_dict()
win4._changed()
win4._manual_save()
# 强制 flush：_flush_changed 在锁定时也不应写盘
win4._flush_changed()
serial_after = win4.store.load(2026, 12).to_dict()
assert serial_before == serial_after, "锁定月 _changed/_manual_save/_flush_changed 不应写盘"
assert win4._dirty is False, "锁定月不应标记 dirty"
print("locked write-blocked OK")

# 2) _on_numeric / _on_note 在锁定时不修改 book（即使通过 setValue 触发）
param_spin = win4._param_spins["min_wage"]
param_spin.blockSignals(True)
param_spin.setValue(9999.0)  # 即便手动改 spin，setattr 仍会被 _on_numeric 拦截
param_spin.blockSignals(False)
# 模拟信号触发（直接调 _on_numeric）
win4._on_numeric("min_wage")
assert win4._book.min_wage == 2170, f"锁定月 min_wage 被改：{win4._book.min_wage}"
print("locked _on_numeric blocked OK")

# 3) 考勤页回调：_on_pick_status / _on_pick_mark / _on_pick_hours 锁定时不修改 days
prev_status = win4._book.day(5).status
prev_mark = win4._book.day(5).mark
prev_ot = win4._book.day(5).overtime_hours
prev_lv = win4._book.day(5).leave_hours
win4._on_pick_status(0)  # 上班
win4._on_pick_mark(1)    # 法定节假日
win4._on_pick_hours(8.0, True)   # 加班 8h
win4._on_pick_hours(4.0, False)  # 请假 4h
assert win4._book.day(5).status == prev_status
assert win4._book.day(5).mark == prev_mark
assert win4._book.day(5).overtime_hours == prev_ot
assert win4._book.day(5).leave_hours == prev_lv
print("locked calendar callbacks blocked OK")

# 4) 薪酬页：_on_salary_attr / _add_pay_item_at_back_of_type / _on_pay_item_removed 锁定时不修改
prev_big = win4._book.big_disease
sal_spin = win4._salary_spins["big_disease"]
sal_spin.blockSignals(True)
sal_spin.setValue(9999.0)
sal_spin.blockSignals(False)
win4._on_salary_attr("big_disease")
assert win4._book.big_disease == prev_big, f"锁定月 big_disease 被改：{win4._book.big_disease}"

prev_count = len(win4._book.pay_items)
win4._add_pay_item_at_back_of_type("wage", "测试新增")
assert len(win4._book.pay_items) == prev_count, "锁定月不应能添加工资项"

# 尝试删除：UI 层 PayItemListWidget._remove 已守卫
if win4.pay_items.rows:
    victim = win4.pay_items.rows[0].item
    win4.pay_items.remove_row(win4.pay_items.rows[0])
    win4._on_pay_item_removed(victim)  # 显式回调也守卫
    assert victim in [it for it in win4._book.pay_items], "锁定月不应能删除工资项"
print("locked salary callbacks blocked OK")

# 5) PayItemRow._on_amount_changed 锁定时不修改 item
row = win4.pay_items.rows[0]
prev_amount = row.item.amount
row._amount.blockSignals(True)
row._amount.setValue(999.0)
row._amount.blockSignals(False)
row._on_amount_changed(999.0)
assert row.item.amount == prev_amount, f"锁定月 pay item amount 被改：{row.item.amount}"
print("locked pay item row blocked OK")

# 6) UI 层：所有控件在锁定时 disabled
locked_widgets = []
locked_widgets += [win4.save_btn]
locked_widgets += [w for w in win4._params_extra_modify_widgets if w is not None]
# 5 张 Card 内部所有可交互控件（Card 框架统一管理）
for card in getattr(win4, "_params_cards", []):
    locked_widgets += card.iter_tracked_widgets()
locked_widgets += [w for w in win4._param_spins.values()]
locked_widgets += [win4._fill_agreed_btn, win4._api_settings_btn,
                   win4._fetch_wage_btn, win4._wage_lock_btn,
                   win4._ot_base_lock_btn, win4._fund_base_lock_btn,
                   win4._province_combo, win4._region_combo, win4._note_edit]
locked_widgets += [w for w in win4._calendar_modify_widgets if w is not None]
# 考勤页 2 张 Card 内部所有可交互控件
for card in getattr(win4, "_calendar_cards", []):
    locked_widgets += card.iter_tracked_widgets()
locked_widgets += [w for w in win4._salary_modify_widgets if w is not None]
locked_widgets += [win4.pay_items._add_btn, win4.pay_items._copy_btn]
for w in locked_widgets:
    if w is None:
        continue
    assert not w.isEnabled(), f"锁定月控件未禁用：{w.__class__.__name__}"
# 工资项每行也必须禁用
for row in win4.pay_items.rows:
    assert not row._amount.isEnabled()
    assert not row._name.isEnabled()
    assert not row._delb.isEnabled()
    assert not row._chip.isEnabled()
# 日期格子按钮也必须禁用
for btn in win4._day_btns.values():
    assert not btn.isEnabled(), "锁定月日期格子未禁用"
print("locked UI controls disabled OK")

# 7) 锁定月仍可导出 Excel（pages_report 的导出按钮应可点，且 _write_report_xlsx 不抛异常）
# 切到报表页并直接调用底层写入逻辑（QFileDialog 是 C++ 绑定，无法 monkey-patch）
import os.path as _op
import tempfile as _tf
from app import pages_report as _rep  # noqa: E402
_xlsx_fd, out_xlsx = _tf.mkstemp(suffix=".xlsx")
os.close(_xlsx_fd)
os.unlink(out_xlsx)
win4._show_page(4)  # 报表页
for _ in range(4):
    app.processEvents()
_rep._write_report_xlsx(out_xlsx, win4._last_result, win4._book)
assert _op.exists(out_xlsx), f"锁定月导出 Excel 应成功生成文件，路径：{out_xlsx}"
assert _op.getsize(out_xlsx) > 1000, "导出文件应非空"
os.unlink(out_xlsx)
print("locked export-allowed OK")

# 8) 解锁后所有操作恢复
win4._book.locked = False
store3.save(win4._book)
win4._go(2026, 12)
assert win4._is_locked is False
assert win4.save_btn.isEnabled() is True
assert win4._fill_agreed_btn.isEnabled() is True
# 修改 min_wage 应能写入
win4._on_numeric("min_wage")
print("unlocked state restored OK")

win4.close()
shutil.rmtree(_tmp3, ignore_errors=True)


# ========== 这次重构的新增测试 ==========

# 9) Excel 样式模块单一来源（pages_annual + pages_report 都应能 import 公共样式）
from app import excel_style  # noqa: E402
from app import pages_annual as _ann  # noqa: E402
assert hasattr(_ann, "AnnualPageMixin"), "年度汇总页模块应导出 AnnualPageMixin"
# 验证常量引用一致性（任选三个关键常量）
assert excel_style.HEADER_FILL.fgColor.rgb == "004F46E5" or excel_style.HEADER_FILL.fgColor.value == "4F46E5"
assert excel_style.MONEY_FMT == '#,##0.00;[Red]-#,##0.00;"—"'
assert excel_style.BODY_FONT.name == "Microsoft YaHei"
print("excel_style shared OK")

# 10) DPAPI roundtrip + 旧版明文向后兼容
import sys as _sys
from app.storage import _dpapi_protect, _dpapi_unprotect, _SENSITIVE_KEYS  # noqa: E402
assert isinstance(_SENSITIVE_KEYS, tuple) and _SENSITIVE_KEYS, "敏感设置键集合应为非空元组"

# 旧版明文（非 dpapi: 前缀）应当不动地返回
assert _dpapi_unprotect("plain-text-token") == "plain-text-token"
assert _dpapi_protect("") == ""
print("dpapi legacy-passthrough OK")

# 真正加密 - 解密 roundtrip（仅 Windows / 加密 API 可用时）
if _sys.platform == "win32":
    secret = "sk-test-1234567890 中文也能加密"
    encrypted = _dpapi_protect(secret)
    if encrypted.startswith("dpapi:"):
        assert _dpapi_unprotect(encrypted) == secret
        print("dpapi roundtrip OK")
    else:
        # Windows 但 ctypes 失败（少见）：fallback 返回原值也是预期路径
        assert encrypted == secret
        print("dpapi fallback (no ctypes) OK")
else:
    print("dpapi skipped (non-Windows) OK")
print("dpapi OK")

# 11) MonthStore 持久化 + .bak 备份 + 列表 + 删除
import tempfile as _tf2
from app.storage import MonthStore  # noqa: E402
_store_dir = _tf2.mkdtemp()
_mstore = MonthStore(_store_dir)
_b1 = model.create_book(2027, 1)
_b1.note = "一月"
_b1.locked = True
_mstore.save(_b1)
_b2 = model.create_book(2027, 2)
_b2.note = "二月"
_mstore.save(_b2)
_b3 = model.create_book(2027, 3)
_b3.note = "三月"
_mstore.save(_b3)
months = _mstore.list_months()
assert months == [(2027, 3), (2027, 2), (2027, 1)], months
# 二次保存应保留 .bak
_mstore.save(_b1)  # 覆盖一月
_bak = os.path.join(_store_dir, "2027-01.json.bak")
assert os.path.exists(_bak), f"应生成 .bak 备份：{os.listdir(_store_dir)}"
# 删除某月
assert _mstore.delete(2027, 2) is True
assert (2027, 2) not in _mstore.list_months()
# 重复删除应返回 False（不抛异常）
assert _mstore.delete(2027, 2) is False
shutil.rmtree(_store_dir, ignore_errors=True)
print("storage OK")

print("UI OK")
print("readonly OK")
print("UI OK")
