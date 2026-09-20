# 工作考勤表（Attendance Desktop）

一款完全离线的 **月度考勤 + 工资核算** 桌面工具（Python / PySide6，支持
**Windows** 与 **Linux**）。
按月记录出勤与工资项，自动核算加班费、社保 / 公积金、请假扣款、应发 / 实发、
**最低工资与工时合规判定**，把每月「填表 + 算工资」从 Excel 公式里解放出来。

## 特性

- 📅 **彩色月历**：逐日 9 种出勤状态，右键格子快捷改状态 / 标记
- 🌐 **节假日 API**：一键铺法定节假日 + 调休补班日（已填日期自动覆盖；无网络时可用内置年表）
- 💰 **完整核算引擎**：加班（工作日 ×1.5 / 休息日 ×2 / 法定 ×3）、社保 / 公积金（基数 × 比例）、请假扣款、应发 / 实发自动串联
- 📊 **工资项管理**：类型 / 名称 / 金额可增删；按出勤津贴自动 × 上班天数；模板二级菜单快速添加
- 🧮 **个税自动**：月度预扣率表（应发 − 5000 − 个人社保 − 公积金 计税）
- ✅ **合规判定**：月最低工资、月工时 ≤ 220h、单日加班 ≤ 3h、月加班 ≤ 36h、每小时雇佣成本
- 🔒 **月份锁定**：整月只读（UI 禁用 + 写入拦截双保险）；参数页另有「跟随月最低工资」的字段级锁（最低工资 / 加班费基数 / 公积金缴费基数）
- 📤 **Excel 导出**：报表页、年度汇总页一键导出 `.xlsx`（多 Sheet：明细 / 汇总 / 公司成本）
- 🎨 **统一 UI 框架**：5 种卡片变体（default / hero / stat / quick / row），QSS 一处切主题

## 环境要求

- **Python 3.10+**（开发 / 打包机，实测 3.14）
- **操作系统**：Windows 10+；Linux **x86_64 且 glibc ≥ 2.38**（预编译 deb，实测基线）
- 打 Windows 安装程序需额外安装 **Inno Setup 6**；打 deb 需 Debian 系（`dpkg-deb`）

> ⚠️ **Linux 版系统要求（重要）**：预编译的 deb 适用于 **x86_64、glibc ≥ 2.38** 的系统
> （已验证 Deepin 25、openEuler 24.03+）。**麒麟 V10（glibc 2.23）、麒麟 V10 SP1（2.31）、
> 统信 UOS 20（约 2.28）等既有信创版本无法直接安装**，原因与解法见下文「deb 打包」的
> glibc 基线说明。安装前请自查：`getconf GNU_LIBC_VERSION && uname -m`

> 敏感设置（API 凭据）的加密方式随平台而异：Windows 用 DPAPI，其它平台用国密
> SM2 + SM4 + HMAC-SM3（见 `app/crypto.py`、`app/gm.py`，细节见下文「敏感字段加密」）。

## 从源码运行

**Windows**：

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py          # 启动桌面应用
.\\.venv\\Scripts\\python.exe scripts\\smoke_test.py   # 离屏冒烟测试（QT_QPA_PLATFORM=offscreen）
```

**Linux（需 glibc ≥ 2.34 —— PySide6 6.11 的 wheel 标签，比预编译 deb 的要求低）**：

```bash
bash scripts/setup_linux.sh       # 建 venv + 装依赖 + 跑国密自证
.venv/bin/python main.py
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/smoke_test.py
```

> Debian 系需先 `sudo apt install -y python3.12-venv`（venv 是独立包，缺了报
> `ensurepip is not available`）。另：`gmssl` 在国内镜像常缺，安装时请走默认
> PyPI 源（`scripts/setup_linux.sh` 已自动处理）。

数据默认保存在用户数据目录下（每月一个 JSON 文件）：Windows 为
`%LOCALAPPDATA%\工作考勤表\data\`，其它平台为 `$XDG_DATA_HOME/工作考勤表/data`；
可用环境变量 `ATT_DATA_DIR` 覆盖数据目录。导出的 Excel 默认落在系统「文档」目录。

### 敏感字段加密与密钥拷贝风险

- **Windows**：API 凭据由 **DPAPI** 加密（密钥由 Windows 账户托管、不落盘），
  数据目录下**没有** `keys/`，不存在下述拷贝问题。
- **信创 / Linux**：API 凭据用国密 **SM2 + SM4 + HMAC-SM3** 加密，SM2 私钥存于
  `<数据目录>/keys/sm2_private.hex`（POSIX 权限 `0600`）。拷贝数据时**两个方向都要注意**：

  1. **只拷 `data/` 不拷 `keys/`** → 换台机器后 `settings.json` 里的凭据解不开
     （文件与密文都在，但显示为不可用的原样字符串）；
  2. **`data/` 与 `keys/` 一起拷走** → 加密就**失去保护意义**了（拿到密钥即可解密）。

  也就是说，这里的国密加密防的是「**同机其他用户偷看**」—— 靠数据目录 `700`、
  私钥文件 `600` 的权限隔离；**不防「整个数据目录被拷走」**。若需要后者，
  必须把 `keys/` 移出数据目录（或改用系统密钥环托管）。

### 文件权限（POSIX / 信创）

信创 / Linux 下数据目录与数据文件会**自动收紧到 `700` / `600`**：桌面发行版默认
`umask 002` 会写出 `775`/`664`，那意味着**同机其他用户能直接读到考勤与工资数据**
（多用户机器或公用电脑上是真实泄露面）。启动时还会把已有文件补做一次收紧，
所以从旧版本升级也会自动修正。

Windows 无需处理：`%LOCALAPPDATA%` 的 ACL 本身按用户隔离。

排障时可用环境变量 `ATT_PERMS=off` 临时关闭这套收紧逻辑。

## 打包发行

### Windows（免安装版 + Inno 安装程序）

双击根目录 **`一键打包.bat`**，或运行 `python scripts/pack_all.py`（等价：`python scripts/pack_windows.py`），
会依次完成：清理旧产物 → PyInstaller（按 `AttendanceDesktop.spec`）→ Inno Setup →
把免安装版复制到 `release\AttendanceDesktop`，安装程序输出到 `release\`，最后启动 3 秒冒烟。

等价手动命令：

```powershell
.\\.venv\Scripts\pyinstaller.exe --noconfirm --clean AttendanceDesktop.spec
# Inno Setup 6（按 installer.iss，输出到 release\）
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
# 复制免安装版
xcopy /E /I /H /Y dist\AttendanceDesktop release\AttendanceDesktop
```

> `release/`、`build/`、`dist/`、`.venv/` 均被 `.gitignore` 忽略，不入库；
> 发行二进制建议以 **GitHub Releases 附件** 形式发布。

### Linux / 信创（deb）

```bash
bash scripts/setup_linux.sh       # 首次：建 venv + 装依赖 + 跑国密自证
./一键打包.sh                     # 一键打包（= .venv/bin/python scripts/pack_all.py deb）
```

同样可以直接调底层实现：`.venv/bin/python scripts/pack_deb.py`
（PyInstaller → 组装 deb 树 → `dpkg-deb` → SM3 摘要）。

产物：`release/attendance-desktop_<版本>_<架构>.deb`（同目录附 `.sm3` 摘要文件）。
版本号取自 `installer.iss` 的 `AppVersion`，架构由 `dpkg --print-architecture` 自动探测。

> **两个版本只需记一个入口**：`scripts/pack_all.py` 按平台自动分派 ——
> Windows 走 `pack_windows.py`（exe + 免安装目录），Linux 走 `pack_deb.py`（deb）。
> PyInstaller 不能交叉编译、deb 也必须在 Debian 系上用 `dpkg-deb` 生成，
> 所以是「**同一入口、两个平台各跑一次**」，而不是「一条命令同时出两个包」。
> 在 Windows 上误传 `deb` 会被直接拒绝并说明原因（退出码 2，不会静默失败）。

安装与卸载：

```bash
sudo dpkg -i release/attendance-desktop_*.deb
sudo apt -f install                  # 若有未满足依赖
dpkg -L attendance-desktop           # 查看安装内容
sudo dpkg -r attendance-desktop      # 卸载（保留用户数据）
```

安装内容：`/usr/lib/attendance-desktop/`（程序本体）、`/usr/bin/attendance-desktop`
（启动器，默认设 `QT_QPA_PLATFORM=xcb`）、`.desktop` 入口与 hicolor 图标。

> ⚠️ **glibc 基线（实测）**：deb 能装到哪些系统，由**构建机的 glibc** 决定 —— PyInstaller 会把
> 构建机的 `libpython`、`libstdc++`、GTK/GLib 等库一并收进包内，这些库的符号版本就是下限。
> 在 **Deepin 25（glibc 2.38）** 上构建的包实测要求 **GLIBC_2.38**、`Architecture: amd64`，
> 因此**装不进**麒麟 V10(2.23) / 麒麟 V10 SP1(2.31) / UOS 20(约 2.28)；可用的是
> **openEuler 24.03+、Deepin 23+** 等较新基线系统。
>
> 要覆盖旧基线必须**同时改两件事**：
> 1. 在低 glibc 容器内构建（`python:3.11-slim-bullseye` = 2.31、`python:3.11-slim-buster` = 2.28）；
> 2. **把 PySide6 降到 ≤ 6.7** —— PySide6 6.11 的 wheel 标签是 `manylinux_2_34`，
>    在 2.31 / 2.28 的容器里**根本装不上**，只换构建环境是无效的。
>
> 而麒麟 V10 的 glibc 2.23 低于 Qt6 全家（≥ 2.28）的下限，需换 Qt5 技术栈才可能支持。
> 目标机自查：`getconf GNU_LIBC_VERSION` 或 `ldd --version | head -1`。
>
> 包内文件属主由 `dpkg-deb --root-owner-group` 固定为 root，**不需要 fakeroot**。

依赖（`requirements.txt`）：

```
PySide6==6.11.2
openpyxl==3.1.5
gmssl==3.2.2       # 国密算法（本体纯 Python；会带 pycryptodomex 这个 C 扩展）
pyinstaller==6.22.2
```

## 项目结构

```
工作考勤表/
├── main.py                  应用入口（QApplication / 窗口图标 / MonthStore）
├── app/                     业务源码包
│   ├── model.py             数据类：MonthBook / PayItem / DayEntry ...
│   ├── calc.py              工资核算引擎（compute(book) -> Result）
│   ├── storage.py           月份存档 + Settings（敏感字段透明加解密）
│   ├── crypto.py            敏感字段加解密：DPAPI / 国密双后端 + 令牌格式
│   ├── gm.py                国密算法封装（SM2 / SM3 / SM4 + 自证清单）
│   ├── holidays.py          法定节假日 / 调休表（按年查）+ API 调用
│   ├── wages.py             全国最低工资标准（省 / 地二级，查 + API 回填）
│   ├── worker.py            后台任务（网络请求不阻塞界面）
│   ├── excel_style.py       Excel 导出统一样式（openpyxl）
│   ├── style.py             Qt 样式表（QSS）
│   ├── config.py            应用级常量（文案 / tooltip / 参数名）
│   ├── ui.py                通用 widget 工具（NumberSpin、PAGES 表等）
│   ├── main_window.py       主窗口（多继承各页面 mixin）
│   ├── pages_overview.py    「工作台」mixin
│   ├── pages_calendar.py    「考勤」mixin
│   ├── pages_salary.py      「薪酬构成」mixin
│   ├── pages_params.py      「参数」mixin
│   ├── pages_report.py      「报表」mixin
│   ├── pages_annual.py      「年度汇总」mixin
│   └── widgets/             卡片 / 金额条 / 加班卡 / 扣除卡 / 工资项列表
├── AttendanceDesktop.spec   PyInstaller 打包描述
├── installer.iss            Inno Setup 安装脚本
├── requirements.txt         Python 依赖
├── 一键打包.bat              一键打包（Windows 壳：双击即构建 exe + 免安装版）
├── 一键打包.sh               一键打包（Linux 壳：执行即构建 deb）
├── scripts/                 构建与测试脚本（不参与运行时打包）
│   ├── pack_all.py          统一打包入口（按平台分派到下面两个实现）
│   ├── pack_windows.py      Windows 构建实现（PyInstaller + Inno Setup）
│   ├── pack_deb.py          Linux / 信创 deb 构建实现
│   ├── setup_linux.sh       Linux 环境准备（venv + 依赖 + 国密自证）
│   ├── verify_deb.sh        deb 免 root 验证（内容 / 权限 / 解包试运行）
│   └── smoke_test.py        离屏冒烟测试（30+ 组回归断言）
├── ARCHITECTURE.md          架构说明（开发者视角）
└── LICENSE                  GNU GPL v3
```

## 核算口径（内置）

- **提供正常劳动天数** = 上班 + 婚假 + 丧假 + 产假 + 年假 + 法定节假日 + 其他
- **应发（总工资）** = 计入最低工资标准的工资 + 津贴（按上班天数 × 标准）+ 固定津贴 / 奖励 + 加班工资 + 公司补贴
- **加班小时工资** = 加班费基数 ÷ 174（月计薪天数 21.75 × 8）；工作日 ×1.5 / 休息日 ×2 / 法定 ×3
  （三档加班小时在薪酬页手工填写，不按考勤自动推算）
- **个人扣除** = 社保基数 × 个人比例 + 公积金基数 × 个人比例 + 大病医疗 + 个税
- **请假扣款**：日薪 = （应发 − 个人扣除）÷ 约定工作天数，时薪 = 日薪 ÷ 8
  （8 为法定标准工作日，与加班时薪基数 174 = 21.75 × 8 同口径）；
  另有「约定工作天数 − 提供正常劳动天数」的天数扣款。约定工作天数为 0 时不计请假扣款
- **合规判定**：计入最低工资标准的工资与月最低工资比较；月工时 > 220h / 单日加班 > 3h / 月加班 > 36h / 上班 > 26 天 等违法项提示

> 提示：若「约定工作天数」大于实际「提供正常劳动天数」（例如约定 26 天但每周双休只上了 22 天），
> 会按天扣款——请按实际用工口径设置「约定工作天数」或标记出勤。

## 数据 / 隐私

- 完全本地离线：月份数据、参数模板、设置均只保存在本机（信创 / Linux 下数据目录与文件会自动收紧到 `700` / `600`，见上文）；
- 内置**全国省级官方最低工资表**（省 / 地区二级）；
- 可选：配置自有「节假日 / 最低工资」API 地址后，点击按钮时才联网拉取（凭据加密落盘，见上文平台与加密说明）；
- 软件不会主动上报任何数据。

## 免责声明

本软件为**免费开源工具**，仅用于工资核算的学习与参考，**不构成任何法律、税务或财务建议**。

- 内置的法定节假日 / 调休、最低工资标准等数据会随国家与地方政策变化，使用前请以官方最新发布为准；
- 社保比例、公积金比例、个税税率、加班 / 请假规则等由使用者自行配置，本软件不代替任何政策判断；
- 自动计算出的金额（应发、扣除、实发、合规判定等）可能因口径、规则或数据更新存在误差；
- **若用于正式发薪或对外出具数据，请务必由财务 / 人事人员按现行法规人工复核后再使用。**

因使用、误用或依赖本软件及其输出而造成的任何直接或间接损失，作者与贡献者概不承担责任；使用即视为同意以上条款。

## 许可证

[GNU General Public License v3.0](LICENSE)

Copyright (C) 2026 工作考勤表 项目作者。本项目为自由软件：你可以再分发和 / 或修改它，
但必须遵守 GPL v3 条款（详见 `LICENSE`）。引用 / 衍生产品请保留版权与许可声明。
