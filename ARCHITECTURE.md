# 架构说明（`app/`）

本文件描述代码层面的设计：模块职责、关键数据流、扩展点。
配合 [`README.md`](README.md) 使用 —— README 是用户视角，本文是开发者视角。

> 目录说明：源码已在仓库根目录，入口为根目录的 `main.py`，业务代码都在 `app/` 包内。

---

## 模块总览

```
main.py                    # 应用入口（仓库根：创建 QApplication / MonthStore / MainWindow）
app/
├── __init__.py              # 空，仅作 package 标记
├── model.py                 # 数据类：MonthBook, PayItem, DayEntry, ...
├── calc.py                  # 工资核算引擎（compute(book) -> Result）
├── storage.py               # 月份存档 + Settings（含 Windows DPAPI 加密）
├── holidays.py              # 法定节假日 / 调休表（按年查）+ API 调用
├── wages.py                 # 全国最低工资标准（省/地二级，查 + API 回填）
├── excel_style.py           # Excel 导出的统一样式（HEADER_FILL/BODY_FONT/...）
├── style.py                 # Qt 样式表（QSS）
├── config.py                # 应用级常量（按钮文案、tooltip、参数名）
├── ui.py                    # 通用 widget 工具（NumberSpin、ClickTile、PAGES 表）
├── pages_*.py               # 每个工作区一个 mixin（被 MainWindow 多继承）
└── widgets/
    ├── card.py              # 统一卡片框架：5 种 variant + set_locked
    ├── salary_strip.py      # 顶部应发/到手/扣除金额条
    ├── overtime_card.py     # 加班工资卡片（三档 + 锁按钮）
    ├── deduction_card.py    # 个人扣除卡片
    └── pay_item_list.py
        pay_item_row.py
        pay_item_menu.py    # 工资项列表（含 row 单条与 catalog 弹窗）
```

---

## 设计模式

### 1. Mixin-based 主窗口

`MainWindow` 由 6 个 mixin 组合：

```python
class MainWindow(OverviewPageMixin, CalendarPageMixin, SalaryPageMixin,
                 ParamsPageMixin, ReportPageMixin, AnnualPageMixin, QMainWindow):
```

每个 mixin 对应**一个工作区**，独占：

- 自己的 root widget（`overview_page` / `calendar_page` / `salary_root` / `params_root` / `report_page` / `annual_page`）
- `_fill_xxx()` 构造 UI 一次性方法（在 `_go()` 时调用）
- `_render_xxx(r)` 数据更新（懒渲染：只在当前页 + 数据版本号变化时执行）
- 业务回调（`_on_pick_status` / `_on_salary_attr` 等）

> Mixin 之间通过 `MainWindow` 上共享状态（`self._book`、`self._last_result`、`self._is_locked`、`self.store`）

**为什么不用组合 / 多窗口？** 同一个 `book` 需要被 6 个页同时观察，组合式会引入 controller 层来转发事件，重复更高。

### 2. Widget 回调对称模式

页 → widget 的反向通信不靠 "页去枚举 widget tree"，而是：

- **正向（数据→UI）**：页 `set_add_callback(cb)` / `set_remove_callback(cb)` 注册自己
- **反向（UI→数据）**：widget 在内部触发回调，**同时**调用 `changed` 信号

例：删除一条工资项
```python
# pages_salary.py 注册
self.pay_items.set_remove_callback(self._on_pay_item_removed)

# pages_salary.py 实现
def _on_pay_item_removed(self, item):
    try: self._book.pay_items.remove(item)
    except ValueError: pass
```

### 3. 统一卡片框架（Card）

所有页面卡片通过 `widgets.Card` 构造，统一 5 种视觉变体：

- `default` → `QFrame#card`（参数卡、报表卡、合规卡、备注卡……）
- `hero`    → `QFrame#heroCard`（渐变背景大卡）
- `stat`    → `QFrame#statCard`（小统计块）
- `quick`   → `QFrame#quickCard`（快捷入口）
- `row`     → `QFrame#pirow`（工资项单行）

```python
from app.widgets import Card

card = Card("社保 / 公积金", hint="五险一金基数与比例...")
card.add_layout(box)          # 把字段 box 加入内容区
card.set_locked(True)         # 一键禁用卡片内所有交互控件
```

锁定语义统一收口到 `Card.set_locked()`，各 mixin 只需调用 `card.set_locked(locked)`。

### 4. 锁定只读状态机

`MainWindow._is_locked: bool` 是核心状态，由 `book.locked` 派生。

```
切换月份 (_go)
  └── _apply_lock_state(book.locked)        ← 锁定模式入口
      ├── UI 层：禁用 修改类 widget（page.set_locked_mode）
      │            └── 现在由 Card.set_locked() 统一处理卡片内部
      └── API 层：_changed / _flush_changed / _manual_save 入口早返回
              ↑ 锁定时就算用户绕过 UI 也写不进去（双保险）

切换锁定状态 (_toggle_lock_current_month)
  ├── 二次确认
  └── 写 book.locked + store.save + _apply_lock_state + _refresh_history
```

锁定后保留：切换月份 / 查看历史 / **导出 Excel**。

> 导出按钮用 `card.add_widget_untracked(pbtn)` 加入卡片，使其不被 `set_locked()` 禁用，满足"锁定仍可导出"。

### 5. 懒渲染 + 150ms 合并保存

`MainWindow` 维护：

- `self._current_page_idx: int`  ← 当前页（哪个 mixin 可见）
- `self._data_version: int`     ← 每次 calc 后 +1
- `self._rendered_versions: dict[int, int]` ← 每页"画到哪个版本号"

切换时：
```python
# 当前页需要重画 ↔ 当前页渲染版本 != 数据版本
```

写入入口：
```python
self._change_timer.start()   # 150ms 单触发
def _flush_changed():
    self._change_timer.stop()
    if self._is_locked: return
    r = calc.compute(self._book)
    self._render_all(r)        # 全页刷一遍（轻量）
    self.store.save(self._book)
```

> 150ms 合并：连续改 5 个字段只触发 1 次 compute + save，避免写盘抖动。

### 6. Excel 样式单一来源

`pages_annual.py` 和 `pages_report.py` 都从 `app/excel_style.py` 取样式常量：

```python
from .excel_style import HEADER_FILL, BODY_FONT, MONEY_FMT, ...
```

改色 / 改字体 → 改 `excel_style.py`，两处导出自动同步。

> 历史：原来两份 `_EXCEL_*` / `_XL_*` 镜像存在一处；重构合并。

---

## 数据流（一次"用户改了一项"）

```
用户拖拽 spin
   │
   ▼
spin.valueChanged  →  `_on_salary_attr(attr)`
                          │
                          ├── setattr(book, attr, value)
                          ├── _changed()         # 立即算 + 更新可见统计 + 启动 150ms 定时器
                          ▼
                     _flush_changed()
                          ├── r = calc.compute(book)         # pure function
                          ├── self._render_all(r)            # 增量更新可见页
                          ├── self.store.save(book)           # 写盘（带 .bak 备份）
                          └── 状态栏 "已保存 HH:MM:SS"
```

`calc.compute(book)` 是纯函数（除常量与 book 外无副作用），单测覆盖良好。

---

## 关键不变量

- **写入拦截**：锁定月进入 UI 后，**所有** setattr(write_attr) 入口都会被主窗口或 widget 层拒掉
- **`r.counts.normal_labor_days`** 与左侧"提供正常劳动天数"spin 永远同步（参数页"一键填入"按钮会拉 calc 结果回填）
- **加班费计算基数**：用户锁定时，不再随最低工资变化联动（参数页三个锁按钮独立）
- **节假日**：日历优先用 API，失败用本地表（`holidays.py`），最终状态可被 UI 改写

---

## 常见修改场景

| 想做的事 | 去看 |
| --- | --- |
| 调整 Excel 颜色 / 字体 / 边框 | `app/excel_style.py` |
| 加一个工作区（例如"公积金台账"） | 新建 `pages_xxx.py` mixin + `main_window.py` 多继承 |
| 修改最低工资数据 | `app/wages.py`（每个省一个 `_XX_GRADEn` + `_XX_DATA`） |
| 添加工资项类型 | `app/model.py:PayItem` + `app/ui.py:PAYITEM_TYPES` + 各行 _refresh_chip |
| 修改锁定行为 | `main_window._apply_lock_state` + `Card.set_locked()` |
| 改工资计算规则 | `app/calc.py`，单测在 `_smoke_test.py` 的 `calc OK` 段 |

---

## 设计权衡

| 选择 | 替代 | 选它的原因 |
| --- | --- | --- |
| Mixin（6 继承） | 单文件 / Page class 组合 | 单一 book 6 处观察，组合要写 controller，转发重复 |
| `book.locked` 顶层字段 | 单独的 `_locked_months.json` | 跟着月份存档走，无 lock 字段时默认 False 自然回退 |
| DPAPI（Windows-only） | 直接明文存 | 防用户备份误传导致 API key 泄露；非 Windows 平台走 fallback |
| openpyxl 直接写 cell | 用 pandas | 单 sheet / 简单版式够用，pandas 增加 ~30MB 依赖 |
| 150ms 合并保存 | 实时保存 | 连续改 N 个字段只触发 1 次写盘与 1 次重算 |

---

## 已修复的"采坑点"

1. **Python 内置 `round()` 是银行家舍入** + IEEE 754 浮点误差 → 0.105×4227 期望 443.84 显示 443.83。改用 `Decimal.quantize(..., ROUND_HALF_UP)`（`calc._round2`）
2. **删除工资项后又被加回来**：`pay_item_list._remove` 只移 UI row，没碰 book。引入 `set_remove_callback` 让页同步 `book.pay_items.remove(item)`
3. **复制工资项漏掉固定加班工资 / 大病医疗补助**：这两字段在 `MonthBook` 顶层、不在 `pay_items` 列表。`_on_copy_pay_items` 显式复制
4. **QFileDialog.getSaveFileName 是 C++ 绑定**，不能 monkey-patch（赋值会让进程 SIGTERM）。测试用底层 `_write_report_xlsx(path, r, b)`
5. **`wintypes.DWORD` 等只在 Windows 上有**：storage.py 在 `ctypes.windll.crypt32` 这一行只在 Windows 下能 import；非 Windows 平台 fallback 到明文存
