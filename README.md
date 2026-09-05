# 工资考勤表（Attendance Desktop）

一款完全离线的 **月度考勤 + 工资核算** 桌面工具（Python / PySide6，Windows）。
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

- **Windows**（设置里的 API 凭据用 Windows DPAPI 加密；其它平台代码可运行但需自行替换 `storage._dpapi_call`）
- **Python 3.10+**（开发 / 打包机，实测 3.14）
- 打包安装程序需额外安装 **Inno Setup 6**（可选，仅发布安装版时用）

## 从源码运行

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py          # 启动桌面应用
.\.venv\Scripts\python.exe _smoke_test.py   # 离屏冒烟测试（QT_QPA_PLATFORM=offscreen）
```

数据默认保存在 `%LOCALAPPDATA%\工作考勤表\data\`（每月一个 JSON 文件）；
可用环境变量 `ATT_DATA_DIR` 覆盖数据目录。

## 打包发行（免安装版 + 安装程序）

双击根目录 **`一键打包.bat`**，或运行 `python _pack_driver.py`，
会依次完成：清理旧产物 → PyInstaller（按 `AttendanceDesktop.spec`）→ Inno Setup →
把免安装版复制到 `release\AttendanceDesktop`，安装程序输出到 `release\`。

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

依赖（`requirements.txt`）：

```
PySide6==6.11.2
openpyxl==3.1.5
pyinstaller==6.22.2
```

## 项目结构

```
工作考勤表/
├── main.py                  应用入口（QApplication / 窗口图标 / MonthStore）
├── app/                     业务源码包
│   ├── model.py             数据类：MonthBook / PayItem / DayEntry ...
│   ├── calc.py              工资核算引擎（compute(book) -> Result）
│   ├── storage.py           月份存档 + Settings（含 Windows DPAPI 加密）
│   ├── holidays.py          法定节假日 / 调休表（按年查）+ API 调用
│   ├── wages.py             全国最低工资标准（省 / 地二级，查 + API 回填）
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
├── 一键打包.bat              一键打包（免安装版 + 安装程序）
├── _pack_driver.py          Python 版打包驱动（等价 一键打包.bat）
├── _smoke_test.py           离屏冒烟测试
├── ARCHITECTURE.md          架构说明（开发者视角）
└── LICENSE                  GNU GPL v3
```

## 核算口径（内置）

- **提供正常劳动天数** = 上班 + 婚假 + 丧假 + 产假 + 年假 + 法定节假日 + 其他
- **应发（总工资）** = 计入最低工资标准的工资 + 津贴（按上班天数 × 标准）+ 固定津贴 / 奖励 + 加班工资 + 公司补贴
- **加班小时工资** = 加班费基数 ÷ 174（月计薪天数 21.75 × 8）；工作日 ×1.5 / 休息日 ×2 / 法定 ×3
- **个人扣除** = 社保基数 × 个人比例 + 公积金基数 × 个人比例 + 大病医疗 + 个税
- **请假扣款**：按「（应发 − 个人扣除）÷ 约定工作天数」折算每日 / 每小时；另有「约定工作天数 − 提供正常劳动天数」的天数扣款
- **合规判定**：计入最低工资标准的工资与月最低工资比较；月工时 > 220h / 单日加班 > 3h / 月加班 > 36h / 上班 > 26 天 等违法项提示

> 提示：若「约定工作天数」大于实际「提供正常劳动天数」（例如约定 26 天但每周双休只上了 22 天），
> 会按天扣款——请按实际用工口径设置「约定工作天数」或标记出勤。

## 数据 / 隐私

- 完全本地离线：月份数据、参数模板、设置均只保存在本机；
- 内置**全国省级官方最低工资表**（省 / 地区二级）；
- 可选：配置自有「节假日 / 最低工资」API 地址后，点击按钮时才联网拉取（凭据经 Windows DPAPI 加密落盘）；
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
