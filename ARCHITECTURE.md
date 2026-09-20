# 架构说明（`app/`）

本文件描述代码层面的设计：模块职责、关键数据流、扩展点。
配合 [`README.md`](README.md) 使用 —— README 是用户视角，本文是开发者视角。

> 目录说明：源码已在仓库根目录，入口为根目录的 `main.py`，业务代码都在 `app/` 包内。

---

## 模块总览

```
main.py                    # 应用入口（仓库根：创建 QApplication / MonthStore / MainWindow）
app/
├── __init__.py              # 仅一行包说明（实际导入都在各模块显式写）
├── model.py                 # 数据类：MonthBook, PayItem, DayEntry, ...
├── calc.py                  # 工资核算引擎（compute(book) -> Result）
├── storage.py               # 月份存档 + Settings（读取缓存 + 文件权限收紧）
├── crypto.py                # 敏感字段加解密：DPAPI / 国密双后端 + 令牌格式
├── gm.py                    # 国密算法封装（SM2/SM3/SM4/KDF/HMAC-SM3）+ 自证清单
├── holidays.py              # 法定节假日 / 调休表（按年查）+ API 调用
├── wages.py                 # 全国最低工资标准（省/地二级，查 + API 回填）
├── worker.py                # 后台任务（QThreadPool）：网络请求不阻塞界面
├── excel_style.py           # Excel 导出的统一样式（HEADER_FILL/BODY_FONT/...）
├── style.py                 # Qt 样式表（QSS）
├── config.py                # 应用级常量（按钮文案、tooltip、参数名）
├── ui.py                    # 通用 widget 工具（NumberSpin、PAGES 表、锁按钮、
│                            #   字段级锁 / 只读横幅 / 忙碌按钮 / 导出默认路径等共享小件）
├── pages_*.py               # 每个工作区一个 mixin（被 MainWindow 多继承）
└── widgets/
    ├── card.py              # 统一卡片框架：5 种 variant + set_locked
    ├── salary_strip.py      # 顶部应发/到手/扣除金额条
    ├── overtime_card.py     # 加班工资卡片（三档 + 锁按钮）
    ├── deduction_card.py    # 个人扣除卡片
    ├── pay_item_list.py     # 工资项列表（容器）
    ├── pay_item_row.py      # 工资项单行
    └── pay_item_menu.py     # 添加工资项的分类目录弹窗
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

> Mixin 之间通过 `MainWindow` 上的共享状态通信（`self._book`、`self._last_result`、
> `self._is_locked`、`self.store`）。

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

**状态栏提示的驻留期**：`_set_status(text, ok, background=False)` 会给刚设的提示
记一个「驻留截止时间」（成功 3s / 失败 6s，见 `STATUS_HOLD_MS*` 常量）。自动保存
触发的 `_set_status(..., background=True)` 在驻留期内**不覆盖**状态栏 —— 否则用户
刚看到“已按 XX 拉取最低工资”，150 ms 后就被“已保存 12:34:56”顶掉。
用户主动点「保存」时走 `_manual_save`，它会无视驻留期给出回执。

### 6. Excel 样式单一来源

`pages_annual.py` 和 `pages_report.py` 都从 `app/excel_style.py` 取样式常量：

```python
from .excel_style import HEADER_FILL, BODY_FONT, MONEY_FMT, ...
```

改色 / 改字体 → 改 `excel_style.py`，两处导出自动同步。

> 历史：原来 `pages_report.py` 与 `pages_annual.py` 各自维护一套 `_EXCEL_*` / `_XL_*`
> 样式常量，重构后合并到 `excel_style.py` 单一来源。

---

## 跨平台与加密层

同一份代码要跑 Windows 与信创 Linux，平台差异集中在下列几处，其余模块不感知平台。

### 分层

```
pages_*.py / main_window.py    只调 store.load_settings() / save_settings()，不感知加密
        │
        ▼
storage.py                     存档与设置：定义「哪些字段敏感」(_SENSITIVE_KEYS)
        │                      并把数据目录/文件权限收紧到 700/600
        ▼
crypto.py                      令牌格式 + 后端分派 + SM2 密钥文件管理
        │
        ├── Windows  → DPAPI（CryptProtectData，密钥由系统账户托管，不落盘）
        └── 其他平台 → 国密（下层 gm.py）
                ▼
            gm.py              SM2 / SM3 / SM4 / SM3-KDF / HMAC-SM3（薄封装 gmssl）
```

### 令牌三形态（`settings.json` 里字段的值）

| 形态 | 含义 |
| --- | --- |
| `dpapi:<b64>` | Windows DPAPI 密文（历史数据，继续可解） |
| `gm1:<b64>.<b64>.<b64>.<b64>` | 国密混合加密：`ek . iv . ct . mac` |
| 无前缀 | 更早版本的明文 —— **原样返回**，永不改写 |

### `gm1` 的构造（Encrypt-then-MAC）

```
k_master = 16 随机字节                      # SM4 主密钥
k_enc    = SM3(k_master ‖ 0x01)[:16]        # 加密密钥
k_mac    = SM3(k_master ‖ 0x02)             # MAC 密钥
iv       = 16 随机字节
ct       = SM4-CBC-PKCS7(k_enc, iv, 明文)
mac      = HMAC-SM3(k_mac, iv ‖ ct)
ek       = SM2-公钥加密(k_master)            # 密文顺序 C1C3C2
```

- **为什么还要外层 HMAC**：`gmssl` 的 `CryptSM2.decrypt()` 算出完整性哈希却**不比较 C3**，
  而 SM4-CBC 自身也没有完整性保护 —— 于是机密性交给 SM4-CBC、完整性交给 HMAC-SM3。
- **为什么给随机数源打补丁**：`gmssl.func.random_hex` 用的是 `random.choice`（非密码学安全），
  而 `CryptSM2.encrypt()` 的随机数 k 正由它生成 → `gm.py` 在导入时把它换成 `os.urandom` 版本；
  SM2 签名也一律显式传入 `os.urandom`。
- **`CryptSM2(private_key, public_key, ...)` 的位置参数顺序与直觉相反**（私钥在前），
  因此代码里一律用关键字参数调用。

### 密钥与权限

- SM2 私钥：`<数据目录>/keys/sm2_private.hex`，`O_EXCL` 原子创建，权限 `0600`
- 密钥缓存**按密钥文件路径分桶**（`crypto._keypairs`）—— 同进程多个 `MonthStore` 互不干扰
- 数据目录 `700`、数据文件 `600`（`storage.secure_path()`；`ATT_PERMS=off` 可关闭）
- Windows 不走国密，因此**没有密钥文件**（DPAPI 的密钥由系统托管）

### 平台分支清单（改动时注意）

| 位置 | 分支依据 | 说明 |
| --- | --- | --- |
| `crypto.dpapi_available()` | `sys.platform == "win32"` | 决定默认后端 |
| `crypto._dpapi_call()` | 同上 | **必须函数内延迟 import** `ctypes.wintypes` |
| `storage.default_data_dir()` | 同上 | `%LOCALAPPDATA%` vs `$XDG_DATA_HOME` |
| `storage.secure_path()` | `os.name == "posix"` | 权限收紧只在 POSIX 生效 |
| `main.py` 图标路径 | `sys._MEIPASS` | 开发 / PyInstaller 两种布局 |
| `scripts/pack_all.py` | `os.name` | 统一打包入口：按平台分派到下面两个实现，平台不符直接拒绝（退出码 2） |
| `scripts/pack_windows.py` / `pack_deb.py` | `sys.platform` | Windows 用 Inno Setup，Linux 用 dpkg-deb |

### 国密自证（交付取证）

`python -m app.gm`（或 `gm.selftest()`）打印 10 项：SM3 两个 GB/T 32905 标准向量、
SM4 的 GB/T 32907 A.1 向量、SM3-KDF、HMAC-SM3、**与 OpenSSL 的 SM3/HMAC-SM3 逐字节对拍**、
SM2 往返与签名负向用例、私钥范围、随机数源加固 —— 需要“使用国密算法”的可复现证据时用它，
不靠口头声明。

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
| 添加工资项类型 | `app/model.py:PayItem` + `app/model.py:PAYITEM_TYPES` + 各行 _refresh_chip |
| 改加密后端 / 令牌格式 | `app/crypto.py`（+ `app/gm.py` 算法层）；自证清单在 `gm.selftest()` |
| 改数据目录位置 / 权限 | `app/storage.py` 的 `default_data_dir()` / `secure_path()` |
| 改导出默认目录 | `app/ui.py:default_export_path()`（默认系统「文档」，回退 `~`） |
| 改打包入口 / 平台分派 | `scripts/pack_all.py`（唯一入口）；薄壳：`一键打包.bat`（ASCII）/ `一键打包.sh`（LF） |
| 改 Windows 打包 | `scripts/pack_windows.py`（PyInstaller + Inno Setup） |
| 改 Linux deb 打包 / 验证 | `scripts/pack_deb.py`（构建）、`scripts/verify_deb.sh`（免 root 验证）、`scripts/setup_linux.sh`（环境） |
| 修改锁定行为 | `main_window._apply_lock_state` + `Card.set_locked()` |
| 改工资计算规则 | `app/calc.py`，单测在 `scripts/smoke_test.py` 的 `calc OK` / `calc leave-fold edge OK` 段 |

---

## 设计权衡

| 选择 | 替代 | 选它的原因 |
| --- | --- | --- |
| Mixin（6 继承） | 单文件 / Page class 组合 | 单一 book 6 处观察，组合要写 controller，转发重复 |
| `book.locked` 顶层字段 | 单独的 `_locked_months.json` | 跟着月份存档走，无 lock 字段时默认 False 自然回退 |
| 加密分双后端：Windows 用 DPAPI、信创用国密 | 全平台统一用一种 | DPAPI 在 Windows 上是系统级、无需密钥文件；国密满足信创要求且不依赖外部服务 |
| 国密加密不交给系统密钥环（keyring） | 用 Secret Service 托管 | 那把“使用国密算法”这个需求本身消解了；且引入 dbus 依赖、无桌面会话时不可用 |
| 数据目录名保留中文「工作考勤表」 | 目录名用 ASCII | 与 Windows 版一致、用户一眼能认；需要 ASCII 时用 `ATT_DATA_DIR` 覆盖即可 |
| openpyxl 直接写 cell | 用 pandas | 单 sheet / 简单版式够用，pandas 增加 ~30MB 依赖 |
| 150ms 合并保存 | 实时保存 | 连续改 N 个字段只触发 1 次写盘与 1 次重算 |

---

## 已修复的"采坑点"

1. **Python 内置 `round()` 是银行家舍入** + IEEE 754 浮点误差 → 0.105×4227 期望 443.84 显示 443.83。改用 `Decimal.quantize(..., ROUND_HALF_UP)`（`calc._round2`）
2. **删除工资项后又被加回来**：`pay_item_list._remove` 只移 UI row，没碰 book。引入 `set_remove_callback` 让页同步 `book.pay_items.remove(item)`
3. **复制工资项漏掉固定加班工资 / 大病医疗补助**：这两字段在 `MonthBook` 顶层、不在 `pay_items` 列表。`_on_copy_pay_items` 显式复制
4. **QFileDialog.getSaveFileName 是 C++ 绑定**，不能 monkey-patch（赋值会让进程 SIGTERM）。测试用底层 `_write_report_xlsx(path, r, b)`
5. **`ctypes.windll` / `ctypes.wintypes` 只在 Windows 存在**：早期 `storage.py` 在**模块顶层**就写
   `ctypes.windll.crypt32.CryptProtectData`，导致非 Windows 平台**导入即崩**（注释里声称的
   “退化为明文”其实永远执行不到）。已改为在 `crypto._dpapi_call()` 内**延迟 import** + 平台守卫
6. **权限默认过宽（POSIX）**：`os.makedirs()` / `open()` 不指定 mode 时受 umask 影响，桌面发行版
   （umask 002）会写出 `775`/`664` → 同机其他用户能直接读工资数据。已用 `storage.secure_path()`
   统一收紧（目录 700 / 文件 600），并在启动时补修历史文件
7. **`QStandardPaths` 返回正斜杠路径**：与 `os.path.join` 拼出的 Windows 路径会**混用分隔符**
   （`C:/…/Documents\名.xlsx`）→ 导出默认路径处用 `os.path.normpath` 归一化
