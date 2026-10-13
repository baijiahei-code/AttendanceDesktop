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
├── model.py                 # 数据类：MonthBook, PayItem, RelatedUnit, DayEntry, ...
├── calc.py                  # 工资核算引擎（compute(book) -> Result）
├── storage.py               # 月份存档 + Settings（读取缓存 + 文件权限收紧）
├── crypto.py                # 敏感字段加解密：DPAPI / 国密双后端 + 令牌格式
├── gm.py                    # 国密算法封装（SM2/SM3/SM4/KDF/HMAC-SM3）+ 自证清单
├── holidays.py              # 法定节假日 / 调休表（按年查，本地表与 API 两个独立入口）
├── i18n.py                  # Qt 内置文案汉化（右键菜单 / 对话框标准按钮；启动时装一次）
├── wages.py                 # 全国最低工资标准（省/地二级；本地表与 API 两个独立入口）
├── worker.py                # 后台任务（QThreadPool）：网络请求不阻塞界面
├── single_instance.py       # 单实例保护（QLocalServer/Socket）：第二次启动只唤醒已有窗口
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

`MainWindow` 由 7 个 mixin 组合：

```python
class MainWindow(OverviewPageMixin, UnitsPageMixin, CalendarPageMixin, SalaryPageMixin,
                 ParamsPageMixin, ReportPageMixin, AnnualPageMixin, QMainWindow):
```

每个 mixin 对应**一个工作区**，独占：

- 自己的 root widget（`overview_page` / `units_root` / `calendar_page` / `salary_root` / `params_root` / `report_page` / `annual_page`）
  ⚠️ 页面顺序即导航顺序，索引一律从 `ui.PAGE_INDEX[key]` 取（**不要写死数字**，插页会错位）
  ⚠️ 侧栏的**显示分组**由 `ui.NAV_GROUPS` 单独定义（不改页面索引）：第一组无标题，
  只放「相关单位」（单位档案性质的独立入口，不随月份走）；「功 能」组放其余 6 个页面。
  `_build_sidebar` 按分组渲染，但 `nav_btns` 仍按**页面索引顺序**填（`_show_page` 用 enumerate 反查选中项）。
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

**唯一的一类例外：只读动作**（不会被锁定禁用，各页在 `_set_xxx_locked` 里再 `setEnabled(True)`）：

- 报表页「导出 Excel」（`card.add_widget_untracked(pbtn)`）
- 相关单位页的「🔍 去搜索」（只查外部网站）与**页内自己的锁按钮**
  （不放开就再也解不开了）

**「相关单位」页不在 `_is_locked` 的管辖范围内** —— 它的数据是**全局**的
（与月份无关，存在 `settings.json` 的 `units`，见下）。可改性只由它自己那把锁
（`pages_units._units_lock_btn`，会话级）控制：

- `_apply_lock_state` 的钩子里**没有** `_set_units_locked`（只 参数 / 考勤 / 薪酬 三页）；
- 所以整月锁定时本页照常可编辑，改动只写 `settings.json`、**不碰月度存档**
  （`_save_units` → `store.save_units`），底部状态栏会提示「单位表已保存」。
- 该页**根本没有月份操作条**（上月 / 月份 / 锁定 / 下月 / 删除本月）：页面归属由
  `ui.NO_MONTH_BAR_KEYS` 声明（与 `PAGES` / `NAV_GROUPS` 放一起），
  `MainWindow._sync_month_bar()` 在切页与切月时执行 —— 命中该表的页面
  **`layout.removeWidget(bar)` + `hide()`（真摘掉，不是 `setVisible(False)`）**，
  离开时再 `insertWidget(页面栈之前)` + `show()`；
  只读动作与锁按钮由 `pages_units._refresh_units_lock_ui()` 在锁定后重新 `setEnabled(True)`。

### 4.1 全局相关单位（与月份无关）

单位档案（劳动合同签订 / 社保缴纳 / 工资发放 …涉及的公司）**不按月存**：

```
settings.json  { "units": [ {"role": "contract", "name": "…", "code": "…"}, … ], … }
```

- 读写：`MonthStore.load_units()` / `save_units()`（读回来的对象可直接改，改完存回；
  写单位不会顶掉其它设置 —— 内部是「读设置 → 改 `units` 键 → 存回」）；
- **不读也不写月度存档**：`MonthBook` 里**已没有 `units` 字段**，老存档里残留的 `units` 键
  会被直接忽略（**没有自动迁移**，用户 2026-10-13 明确要求删掉）；
- 种子：全新安装（设置里**没有** `units` 键）时页面按 `model.default_units()`
  **内置类型各列一行**（名称 / 编号留空，**不含**「其他相关单位」）；`_units_list()`
  只把这份种子放在内存里，**首次修改才落盘**。设置里一旦有 `units` 键（哪怕只剩空表）
  就以存的那份为准 —— **删掉的行不会自己回来**（`_save_units` 每次改动都会写盘）；
- 页面：`pages_units._units_list()` 是内存里的那一份，行控件绑定其中的 `RelatedUnit`；
- **不参与参数模板**：`pages_params._collect_params()` 不再写 `units`，`_apply_template()`
  也不再调 `_apply_units_from_template`（该方法已删）—— 旧模板里残留的 `units` 键会被忽略
  （用户 2026-10-13：「这个和套用参数模板也无关」）；
- 行尾动作按钮（`_UnitRow.action_btn`）**按类型变**：普通单位是「🔍 去搜索」，
  **工资代发银行**（`model.UNIT_ROLE_BANK`）是「📋 复制」——
  `_on_unit_row_action()` 分流到 `_open_unit_search_menu()` / `_copy_unit_values()`——
  银行那行**一次复制两个值**（银行名称 + 联行号 / 账号，`"\n"` 连接，只填一个就只复制一个），
  `_refresh_unit_row_action()` 在**建行时**与**改类型时**各刷一次图标 / tooltip。
  两个动作都是**只读**的：锁定时仍可用（`_refresh_units_lock_ui` 会把按钮重新打开）；
- 查询辅助：没有了 —— `model.units_of()` / `first_unit_name()` 已删（前者随字段降级、
  后者随「一键同劳动合同签订单位」功能一起移除）；现在每家的名称 / 编号都只能手填。

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

### 7. 单实例保护（`single_instance.py`）

**为什么必须有**：数据是「一个月一个 JSON」+ 全量内存副本 + 150ms 合并保存。
两个窗口同时打开同一个月时，各自持有独立副本，**后保存的一方会把先保存的覆盖掉**
（用户看到的是"改了没生效/数字跳回去"）。所以同一用户只允许一个窗口。

机制（Qt 自带本地 IPC，无第三方依赖、不写锁文件）：

| 角色 | 动作 |
|---|---|
| 第一个实例 | `InstanceServer.start()` → `QLocalServer.listen(<名字>)`，并**持有引用** |
| 后续实例 | `notify_existing()` 先用 `QLocalSocket` 连一次；连上 → 发 1 个字节 → **自己立刻退出**（退出码 0） |
| 第一个实例收到连接 | 回调 `main.py::_bring_to_front(win)`：清 `WindowMinimized` → `show/raise_/activateWindow` |

要点：

- 服务名 `AttendanceDesktop-instance-v1-<用户名>`：带版本号（将来改通信格式可直接换名，
  新旧版本互不干扰）+ 带用户名（同机不同用户互不抢占）。名字由 `server_name()` 单点定义。
- **`InstanceServer` 被回收 = 监听消失**，所以 `main.py` 里它以 `win` 为 parent 持有；
  测试里也必须存变量。
- 「名字被占」分两种情况，`start()` 会自己分辨：真有人在跑 → 返回 `False` 让位；
  上一实例被强杀（Linux/macOS 残留 socket 文件）→ `removeServer()` 清掉重试。
- 建不起 IPC 通道**不算致命错**：打印一行提示后照常启动（退化为可多开），
  不让"保护机制"反而把程序卡在打不开。
- 逃生开关：环境变量 `ATT_ALLOW_MULTI=1` 直接关掉保护（对照/调试用）。
- ⚠ 平台差异：Windows 上 Qt 允许同名命名管道再 `listen` 成功（不报 `AddressInUse`），
  所以**不能**依赖"第二个实例 listen 一定失败"来保证唯一 —— 真正生效的是
  「先探后启」这个顺序（`main.py` 里 `notify_existing()` 在 `InstanceServer` 之前）。

---

## 跨平台与加密层

同一份代码要跑 Windows 与 Linux，平台差异集中在下列几处，其余模块不感知平台。

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
| `scripts/pack_all.py` | `os.name` | 统一打包入口：按平台 / 格式分派（`win` / `deb` / `rpm` / `all`），平台不符直接拒绝（退出码 2） |
| `scripts/pack_windows.py` | `sys.platform` | Windows 用 Inno Setup |
| `scripts/pack_deb.py` / `pack_rpm.py` | `sys.platform` | Linux 分别用 `dpkg-deb` / `rpmbuild`；**两者共用同一套 PyInstaller 产物与裁剪逻辑**（`pack_rpm.py` 直接复用 `pack_deb.py` 的函数） |

### 国密自证（交付取证）

`python -m app.gm`（或 `gm.selftest()`）打印 10 项：SM3 两个 GB/T 32905 标准向量、
SM4 的 GB/T 32907 A.1 向量、SM3-KDF、HMAC-SM3、**与 OpenSSL 的 SM3/HMAC-SM3 逐字节对拍**、
SM2 往返与签名负向用例、私钥范围、随机数源加固 —— 需要“使用国密算法”的可复现证据时用它，
不靠口头声明。

### Linux 兼容性基线（glibc）

PyInstaller **不能交叉编译**，而且会把构建机的 `libpython`、`libstdc++`、GTK/GLib 等
动态库一并收进包内 —— 这些库的**符号版本**就是产物的安装下限。也就是说，一个 deb
「能装到哪些系统」由**构建机**决定，与项目代码无关。

实测（2026-09-20，构建机 Deepin 25 / glibc 2.38）：

| 项目 | 值 |
| --- | --- |
| 产物最高 GLIBC 符号 | `GLIBC_2.38`（24 个文件引用；另有 2.36×4、2.35×5、2.34×34） |
| 产物最高 GLIBCXX 符号 | `GLIBCXX_3.4.32` |
| `Architecture` | `amd64`（仅 x86_64） |

各系统基线对照（麒麟取自其官方源 `dists/<代号>/main/binary-amd64/Packages.gz` 里
`libc6` 的版本；Deepin / openEuler / Ubuntu 取自 DistroWatch）：

| 系统 | glibc | 能否安装本包 |
| --- | --- | --- |
| 银河麒麟 V10 | 2.23 | ❌ |
| 银河麒麟 4.0.2 SP3 | 2.23 | ❌ |
| 银河麒麟 V10 SP1 | 2.31 | ❌ |
| 统信 UOS 20 | ≈ 2.28（公开资料；源需授权，未实测） | ❌ |
| Ubuntu 20.04 / 22.04 | 2.31 / 2.35 | ❌ |
| Deepin 20.9 | 2.28 | ❌ |
| openEuler 24.03-SP3 / 25.09 | 2.38 | ✅ |
| Deepin 23.1 / 25.2 | 2.38 | ✅ |

**要覆盖旧基线，必须同时做两件事**（缺一不可）：

1. **在低 glibc 容器内构建**：`python:3.11-slim-bullseye`（glibc 2.31）、
   `python:3.11-slim-buster`（glibc 2.28）；
2. **把 PySide6 降到 ≤ 6.7** —— PySide6 6.11 的 wheel 标签是 `manylinux_2_34`，
   在 2.31 / 2.28 的容器里连 `pip install` 都过不去，只换构建环境是无效的：

   | 框架 | wheel 标签 | 最低 glibc |
   | --- | --- | --- |
   | PySide6 6.11.2（当前） | `manylinux_2_34` | 2.34 |
   | PySide6 6.7.0 / 6.5.0 | `manylinux_2_28` | 2.28 |
   | PyQt6 6.7.0 | `manylinux_2_28` | 2.28 |
   | PyQt5 5.15.11 | `manylinux_2_17` | 2.17 |

麒麟 V10 的 glibc 2.23 低于 Qt6 全家（≥ 2.28）的下限 —— 要支持它只能换 Qt5 技术栈。

目标机自查：`getconf GNU_LIBC_VERSION`、`ldd --version | head -1`、`uname -m`。

### Linux 包格式（deb / rpm）

同一份产物要投递到两类包管理体系，因此有两个**平级**的组装脚本。PyInstaller 构建与运行时
裁剪**只做一次**——`pack_rpm.py` 直接复用 `pack_deb.py` 里的函数（`trim_bundle` /
`normalize_perms` / `read_version` / `sm3_of` 等），避免两处逻辑漂移。

|  | deb（`pack_deb.py`） | rpm（`pack_rpm.py`） |
| --- | --- | --- |
| 组装方式 | 组装 `DEBIAN/` 目录树 | 组装安装后文件树 + 自动生成 `.spec` |
| 打包命令 | `dpkg-deb --build --root-owner-group` | `rpmbuild -bb --define "_topdir …"` |
| 架构字段 | `amd64` / `arm64`（`dpkg --print-architecture`） | `x86_64` / `aarch64`（`ARCH_MAP` 映射） |
| 依赖字段 | `Depends:` / `Recommends:`（Debian 包名） | `Requires:` / `Recommends:`（RPM 包名，**由 deb 侧清单自动映射**：`libc6`→`glibc`、`libgl1`→`mesa-libGL`、`libdbus-1-3`→`dbus-libs`、`libxcb-cursor0`→`xcb-util-cursor` …） |
| glibc 版本下限 | `Depends: libc6 (>= 构建机 glibc)` | `Requires: glibc >= 构建机 glibc` |
| 软依赖特例 | `Recommends:` 里的 xcb 组件与 CJK 字体 | `xcb-util-cursor` **只能写 `Recommends`** —— 它仅在 openEuler 的 EPOL 仓库，写成 `Requires` 会让未启用 EPOL 的机器**整包装不上**（该库是 Qt6 xcb 插件的硬需求，故 README 单独说明补装方式） |
| 许可文件 | `/usr/share/doc/<pkg>/copyright`（Debian 政策 §12.5） | `/usr/share/licenses/<pkg>/COPYING`（`%license`） |
| 变更记录 | `changelog.gz`（§12.7） | `.spec` 的 `%changelog` 段 |
| 入口 | `./一键打包.sh`（默认） | `./一键打包.sh rpm` |
| 一次出齐 | `./一键打包.sh all`（两者各跑一遍 PyInstaller，耗时翻倍） | |
| 工具链 | `dpkg-deb`（Debian 系自带） | `rpmbuild`（`sudo apt install -y rpm`） |

⚠ **rpm 必须 `AutoReqProv: no`**：PyInstaller 产物内含数十个自带 `.so`，若放任自动依赖探测，
它们会被全部登记成系统依赖，生成一长串目标机必然不满足的 `libX.so.1()(64bit)`，
安装时报「依赖不满足」。关掉后改为显式声明：`Requires` = glibc 版本下限 + 缺了必然起不来的
Qt 运行时库（`libxkbcommon-x11` / `mesa-libGL` / `mesa-libEGL` / `fontconfig` / `dbus-libs`），
可选组件与 `xcb-util-cursor` 放 `Recommends`。

两种格式各有一个免 root 的验证脚本：`verify_deb.sh`（`dpkg-deb -I/-c/-x`）与
`verify_rpm.sh`（`rpm -qpi/-qpl/-qplv` + `rpm2cpio | cpio -idm`；⚠ 不用 `rpm2archive`，
它默认产出 `.tgz`、不保留安装路径树）。

#### rpm 的软依赖与 EPOL 仓库（实测）

Qt 6.5 起 `xcb` 平台插件需要 `libxcb-cursor.so.0`，它在 RPM 体系里叫 **`xcb-util-cursor`**，
且**只存在于 openEuler 的 EPOL 仓库**（`OS` / `everything` 里都没有）—— 这正是它只能写
`Recommends` 的原因：未启用 EPOL 的机器根本取不到它，写成 `Requires` 会让**整包装不上**。

| 安装命令 | 实测结果（openEuler 24.03-LTS） |
| --- | --- |
| `sudo dnf install ./xxx.rpm` | 退出码 0；连 EPOL 一起解析，**自动装入 28 个包**（含 `xcb-util-cursor`、`mesa-libGL/EGL`、`google-noto-sans-cjk-ttc-fonts`），开箱可用 |
| `sudo rpm -ivh xxx.rpm` | 退出码 0 但**不处理 `Recommends`** → 启动报 `ImportError: libGL.so.1: cannot open shared object file`（缺 `mesa-libGL`；缺 `libxcb-cursor` 同理） |

- openEuler 24.03-LTS **默认已启用** `EPOL` 与 `EPOL-update`（`dnf repolist --all` 实测）；
  若被禁用：`sudo dnf --enablerepo=EPOL install xcb-util-cursor`。
- 用 `rpm -ivh` 装完后手动补齐：
  `sudo dnf install mesa-libGL mesa-libEGL libxkbcommon-x11 fontconfig dbus-libs xcb-util-cursor`
- 中文字体对应 RPM 包名是 **`google-noto-sans-cjk-ttc-fonts`**（缺了界面中文会显示成方块；
  注意不是 `...-sans-cjk-fonts`，那个包在 openEuler 里不存在）。

**实测记录（openEuler 24.03-LTS 容器 / glibc 2.38 / x86_64）**：`rpm -ivh` 与 `dnf install`
退出码均为 0；`rpm -V` 完整性校验通过、共 **292 个文件**、属主 root:root；`rpm -e` 卸载无残留；
程序在 `offscreen` 与真实 **`xcb`** 后端下均能正常启动（后者用 Xvfb 虚拟显示验证，持续运行未崩溃）。
deb 侧在 **Deepin 25** 实测 `dpkg -i` 成功安装并可正常运行。

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

## 内置数据更新流程（最低工资 / 节假日）

目标：把「找数据 → 抄数字 → 检查地图」变成一条命令 + 一次人工确认。

### 最低工资

```bash
.venv\Scripts\python.exe scripts\update_minwage.py      # 自动抓最新一期（人社部 IP 镜像）
.venv\Scripts\python.exe scripts\update_minwage.py --list    # 只列出镜像上各期文章
.venv\Scripts\python.exe scripts\update_minwage.py --file saved.html   # 用本地保存的页面（离线/可复现）
```

- **数据源**：人社部《全国各省、自治区、直辖市最低工资标准情况（截至 YYYY-MM-01）》，
  每季度一期；`www.mohrss.gov.cn` 有 WAF，脚本走同一服务器的 **IP 镜像**
  `http://114.255.111.180/SYrlzyhshbzb/laodongguanxi_/fwyd/` 并自动选最新一期。
- **输出**：官方各档的月/时数值 + 与内置表的比对结果：
  `[错]` = 某市用的数值不在官方档位里（映射写错/过期，**必须修**）；
  `[缺]` = 官方表里没有该省（省名写法变了或解析失败）；
  `[注]` = 官方有但内置没用的低档（一般只适用部分县，属于正常）。
- **退出码**：只在出现 `[错]/[缺]` 时返回 1，适合放进发布前检查。
- 改完数字后照旧跑一遍脚本确认 0 处 `[错]`，再跑 `scripts/smoke_test.py`。

### 节假日

- 公告：gov.cn「国务院办公厅关于 YYYY 年部分节假日安排的通知」（惯例上年 11 月发布）。
- 内置表：`app/holidays.py` 的 `_YEAR_DATA`（`statutory` 法定日 / `ranges` 放假区间 / `makeup` 补班日），
  未公布的年份不要凭「预测」写进去；日历页的「📋 铺本地表」只认这张表。
- 核对方式：把公告里每个节日的“放假区间”和“X月X日上班”逐条对上 `ranges` / `makeup`，
  法定日按「元旦当夭、除夕+初一到初三、清明当天、5/1&5/2、端午当天、中秋当天、10/1~10/3」核。

---

## 关键不变量

- **写入拦截**：锁定月进入 UI 后，**所有** setattr(write_attr) 入口都会被主窗口或 widget 层拒掉
- **`r.counts.normal_labor_days`** 与左侧"提供正常劳动天数"spin 永远同步（参数页"一键填入"按钮会拉 calc 结果回填）
- **加班费计算基数**：用户锁定时，不再随最低工资变化联动（参数页三个锁按钮独立）
- **节假日**：日历页有「📋 铺本地表」（内置 `holidays.py`，不联网）与「🌐 API 一键铺」（只走 API，失败直接报错不回退）两个独立入口，最终状态可被 UI 改写
- **节假日日型判定只有一处**：`holidays.classify_day()`（优先级：法定 → 补班 → 放假），
  内置表（`day_kind`）与 API 铺设（`pages_calendar._apply_holidays`）都调它；
  要拿原始集合用公开的 `holidays.year_sets()`

---

## 常见修改场景

| 想做的事 | 去看 |
| --- | --- |
| 调整 Excel 颜色 / 字体 / 边框 | `app/excel_style.py` |
| 加一个工作区（例如"公积金台账"） | 新建 `pages_xxx.py` mixin + `main_window.py` 多继承 |
| 修改最低工资数据 | 先跑 `python scripts/update_minwage.py` 看官方最新一期与内置表的差异，再改 `app/wages.py`（每个省一个 `_XX_GRADEn` + `_CITY_XX_n`） |
| 添加工资项类型 | `app/model.py:PayItem` + `app/model.py:PAYITEM_TYPES` + 各行 _refresh_chip |
| 改加密后端 / 令牌格式 | `app/crypto.py`（+ `app/gm.py` 算法层）；自证清单在 `gm.selftest()` |
| 改数据目录位置 / 权限 | `app/storage.py` 的 `default_data_dir()` / `secure_path()` |
| 改导出默认目录 | `app/ui.py:default_export_path()`（默认系统「文档」，回退 `~`） |
| 改打包入口 / 格式分派 | `scripts/pack_all.py`（唯一入口）；薄壳：`一键打包.bat`（ASCII）/ `一键打包.sh`（LF，默认 deb） |
| 改 Windows 打包 | `scripts/pack_windows.py`（PyInstaller + Inno Setup） |
| 改 Linux 打包 / 验证 | `scripts/pack_deb.py`、`scripts/pack_rpm.py`（构建，后者复用前者）、`scripts/verify_deb.sh` / `verify_rpm.sh`（免 root 验证）、`scripts/setup_linux.sh`（环境） |
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
| rpm 构建**复用** `pack_deb.py` 的函数 | 抽 `_pack_common.py` 三方共用 | deb 链路已实测跑通，抽公共模块要改动它、引入回归风险；`import` 复用则零改动 |
| rpm 关掉自动依赖探测（`AutoReqProv: no`） | 让 rpm 自动生成依赖 | 产物自带数十个 `.so`，自动生成的 Requires 目标机必然不满足 → 安装即报「依赖不满足」 |

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

### 全量代码审计（2026-10-07）

8. **`calc.company_hourly_cost` 除零**：分母是「提供正常劳动天数 × 每日工时」，却只判了天数 > 0 ——
   参数页把「24 小时内工时」填成 0 就直接 `ZeroDivisionError`，整个核算崩掉。改为对整个乘积判 > 0；
   同时参数页所有数字框统一 `minimum=0`（工时 / 基数 / 比例填负数没有意义）
9. **后台任务被取消后按钮永远卡住**：`worker.AsyncCall._dispatch_done/_failed` 只在「未取消」分支里
   调 `_finish()` → `cancel()` 之后 `on_finished` 永不执行（各页面「查询中…」按钮停在禁用态），
   `_ACTIVE` 还泄漏。改为 `try/finally` 保证 `_finish()` 必跑。**新契约**：`cancel()` 只拦
   结果类回调（`on_done` / `on_failed`），`on_finished` 照常执行
10. **「关于」对话框谎报国密**：`crypto.describe()` 只要后端不是 `plain` 就返回
    「SM2(C1C3C2) + SM4-CBC + HMAC-SM3」，而 Windows 实际走 DPAPI（无密钥文件、不涉及国密）。
    改为按后端给出真实描述；`key_ready` 在非 `gm` 后端恒为 True（不存在的密钥文件不再被当成“未就绪”）
11. **最低工资静默换成别的城市**：`wages.get(省, 市)` 在「指定了市但内置表里没有」时会返回该省**第一个**
    城市的数字 → 相当于把另一个地方的标准写进账本（还联动加班基数 / 公积金基数），用户看不出来。
    改为返回 `None`（调用方本来就判 `is not None`；顺带去掉这类误报的“与内置表不一致”提醒）
12. **节假日日型判定有两套优先级**：内置表走 `day_kind()`（法定→补班→放假），API 铺设写的是
    （补班→法定→放假）→ 同一天在两处会得到不同结论。抽出 `holidays.classify_day()`（关键字传参，
    防把 rest / makeup 写反）作为全项目唯一判定；`_year_sets` 提升为公开 `year_sets()`
    （`wages` 与 `pages_calendar` 都在用，顺手去掉两个 `# type: ignore`）
13. **添加工资项菜单每次弹出都泄漏一组子菜单**：子菜单的 parent 是本菜单，
    `clear()` 只删“直接属于本菜单”的 action，管不到它们。改为记在 `_subs` 里、rebuild 时
    `deleteLater()`；顺手删掉永远走不到的 `else: self.exec_()`（`exec_` 是弃用别名，走到就 AttributeError）
14. **工资项列宽三处打架**：数据行 `setFixedWidth(150)` 紧接着被 `setMinimumWidth(110)` /
    `setMaximumWidth(180)` 覆盖 → 与表头的固定值对不齐。改为只认 `PAYITEM_COL_WIDTHS["std"]`
15. **「滚到新行」静默失效**：`ensure_visible_row` 写死 `parent().parent()`，而真实层级是
    `pay_items → ResponsiveColumns → salary_root(滚动区)` → 永远找不到滚动区、什么都不做。
    改为沿父链往上找第一个 `ensureWidgetVisible`
16. **`config.py` 里 13 个“改了没效果”的死常量**（chip 字号 / 删除按钮配色 / 输入框边框 /
    列头颜色 / 空提示底色 …）＋ 几处与实现不符的过期注释。
    死常量已删，注释改成真话：QSS 用的是 `style.py` 里的独立字面量，加班倍率写死在 `calc.py`
17. **文档字符串描述不存在的成员**：加班卡片里那个并未保存成属性的“每档总额”、
    个人扣除卡片并未公开的“total”、刷新月小计的签名写多了一个参数、
    卡片框架 `add_layout` 那句“锁定要调用方自己管”（其实会递归）已全部改正
