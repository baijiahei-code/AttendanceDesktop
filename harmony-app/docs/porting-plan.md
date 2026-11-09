# 鸿蒙版移植方案与实施记录

> 本文回答三个问题：**为什么这样移植、现在做到哪、踩过哪些坑**。
> 日常构建 / 安装 / 签名见 [`../README.md`](../README.md)；桌面版结构见仓库根 `ARCHITECTURE.md`。
>
> **状态（2026-11-09）**：v1 功能已完成 —— 逻辑层与桌面版逐例数值对拍通过，7 个页面全部可用，
> 账本明文存应用沙箱（仅 API Key 用 HUKS 加密），可一键出 HAP（release 实测可运行）。

## 目录

1. [现状速览](#一现状速览)
2. [移植范围](#二移植范围)
3. [模块映射（Python → TS）](#三模块映射python--ts)
4. [一致性保障：数值对拍](#四一致性保障数值对拍)
5. [已知风险与对策](#五已知风险与对策)
6. [实施里程碑](#六实施里程碑)
7. [踩坑规则（照抄即可）](#七踩坑规则照抄即可)
8. [关键技术与决策](#八关键技术与决策)
9. [待办](#九待办)
10. [附录：常用命令](#附录常用命令)

## 一、现状速览

| 维度 | 现状 | 验证方式 |
|---|---|---|
| 逻辑层 `core/` | 11 个文件、约 2.6k 行（calc / model / num / holidays / minwage / paycatalog / units / api / csv / config / index） | `npm test` |
| 与桌面版一致性 | 54 个对拍用例（6 份真实存档 × 9 种变体），金额 / 布尔 / 文案逐字段全等 | `tests/parity.test.ts` |
| 测试规模 | **141 例全绿**（87 单元 + 54 对拍；缺 `fixtures/baseline.json` 时对拍整组 skip） | `npm test` |
| 界面 | 7 个页面：工作台 / 相关单位 / 考勤 / 薪酬构成 / 参数 / 报表 / 年度汇总 | `pages/*Page.ets` |
| 存档 | Preferences 一月一键**明文 JSON**（应用沙箱）；仅 API Key 用 HUKS AES-256-GCM | 状态栏显示「已保存 YYYY-MM」 |
| 导出 | 报表 / 年度汇总导出 CSV（系统「另存为」选择器，落盘后校验字节数） | 模拟器实测 |
| 联网（可选） | OpenAI 兼容 API：最低工资 / 节假日；内置 10 个服务商模板；不配置就只用本地表 | `core/api.ts` + `model/ApiClient.ets` |
| 构建 | `一键打包 harmony` → `release/AttendanceHarmony-v1.0.0-*.hap`（自动识别签名版 / `-unsigned`） | release 实测可运行 |
| 未做 | 上架 / 发布签名（需自备华为证书）；报表 xlsx 导出（目前只出 CSV） | 见「九、待办」 |

> 规模口径（2026-11-09 实测）：桌面版 32 个 `.py` / 8,825 行；鸿蒙工程 18 个 `.ets`（不含 `ets/core/` 自动副本）/ 6,959 行。

## 二、移植范围

原则：**只搬「算钱」和「记账」，界面按 2in1 大屏重新设计**，不复刻桌面版控件。

### 已实现

- 全部核算口径：两个取整函数、合计恒等式、合规布尔判定、报表分组文案；
- 存档模型（与 `MonthBook.to_dict()` 同构，字段名 / 默认值 / 容错规则一致）；**账本明文、仅 API Key 加密**（与桌面版口径一致）；
- 最低工资表、节假日表、工资项目录、相关单位类型 —— 全部由脚本从桌面版**自动导出，不手抄**；
- 7 个页面及主要交互：月份切换 / 历史月份 / 整月锁定 / 参数模板 / 复制工资项 / 单位搜索复制；
- 报表与年度汇总导出 CSV；若 `rawfile/seed_months.json` 存在（脚本生成、不入库），首次启动导入一次示例月份，缺失时自动跳过；
- 可选联网查询（最低工资 / 节假日）：失败时明确显示原因，绝不静默替换数字。

### 不做（第一版）

- **结果报表导出 xlsx**：鸿蒙无 `openpyxl` 等价物 → 先出 CSV（Excel 可直接打开），xlsx 待评估；
- **联网作为默认路径**：必须用户手动配置并点按钮才联网，核算永远优先本地官方表。

## 三、模块映射（Python → TS）

行数取自源仓库实测（2026-11-09：桌面版 32 个 `.py`、8,825 行）。
鸿蒙侧的括号内行数**刻意不写死** —— 那边还在重构，写死必然过期；要看当前规模用
`Get-Content <file> | Measure-Object -Line` 或编辑器的行数。

| 源文件 | 行数 | 目标 | 处理方式 |
|---|---|---|---|
| `app/calc.py` | 419 | `core/calc.ts` | **逐函数翻译**，含 `_count_attendance` / `_build_groups` / `compliance_standard_text` / `overtime_rate_text` |
| `app/model.py` | 345 | `core/model.ts` + `core/units.ts` + `core/paycatalog.ts` | class + `fromDict`/`toDict`；单位类型与工资项目录拆成独立文件，由脚本导出 |
| `app/holidays.py` | 87 | `core/holidays.ts` | 2025/2026 官方数据 + `classifyDay`（法定 → 补班 → 放假）单一判定入口 |
| `app/wages.py` 数据段 | 1065（表约 477） | `core/minwage.data.ts` | 31 省 394 地区月/时最低工资；`scripts/export_minwage.py` 自动导出（含 O(1) 查询的 `Map` 索引） |
| `app/wages.py` 网络层 | ↑ 同上 | `core/api.ts` + `model/ApiClient.ets` | 纯逻辑（端点 / JSON 提取 / 合理性校验）与 HTTP 分离，前者可在 Node 测试 |
| `app/config.py` | 61 | `core/config.ts` + `core/calc.ts` 顶部常量 | `OT_RATE_*`、界面色板 / 列宽；`PAYABLE_DAYS=21.75` 与合规阈值 220/36/26/3 定义在 `core/calc.ts` |
| `app/storage.py` | 308 | `model/Storage.ets`（+ `model/BookCache.ets`） | 鸿蒙侧重写：Preferences 一月一键**明文 JSON** + 回读校验；API 配置单键 `api_config`，仅其中的 Key 走 HUKS（见 8.1） |
| `app/crypto.py` + `app/gm.py` | 521 | `model/Crypto.ets` | 换 HUKS（系统密钥库，密钥不可导出），**不移植 Python / 国密实现** |
| `app/excel_style.py` + 报表 xlsx | 39 + 部分 | `core/csv.ts` + `model/Exporter.ets` | 鸿蒙无 `openpyxl` → CSV（带 UTF-8 BOM），写后 `stat` 校验字节数 |
| `app/pages_*.py` `widgets/` `main_window.py` `style.py` `ui.py` | ≈5.7k | `pages/Index.ets`（外壳）+ 7 个 `pages/*Page.ets` + `pages/components.ets` + `pages/theme.ets` + `model/Snap.ets` | ArkUI 全部重写，不复用；每个页面一个组件，通用小控件拆到 `components.ets`、配色常量拆到 `theme.ets` |

> `app/single_instance.py` / `app/i18n.py` / `app/worker.py` 在鸿蒙侧**没有对应物**：
> 单实例由系统默认 `singleton` 启动类型保证；中文由系统语言提供；HTTP 用系统 `http` 模块的 Promise 接口。

## 四、一致性保障：数值对拍

思路：**同一份输入 JSON，两个实现各算一遍，逐字段 diff**。这一步能抓住 90% 的移植错误
（取整位置、恒等式、默认值、单位口径）。

1. 输入只读真实存档：`%LOCALAPPDATA%\工作考勤表\data\YYYY-MM.json`，可用 `ATT_DATA_DIR` 覆盖，脚本不写死个人路径。
2. Python 侧导出基准（**在仓库根目录**用桌面版 venv 跑）：
   ```powershell
   .venv\Scripts\python.exe harmony-app\scripts\dump_baseline.py --data-dir <dir> --out harmony-app\fixtures\baseline.json
   ```
   输出 `{ "2026-10": { ...Result 全字段... }, ... }`。
3. TS 侧：`npm test` 里的 `tests/parity.test.ts` 读同一批 JSON，跑 `core/calc.ts` 与 `baseline.json` 比对。
4. 判定：**逐字段严格相等** —— 金额由 `compute()` 用 `pyRound2` 取整后按数值全等比较（**不做容差**），布尔 / 文案字符串全等；不一致打印
   `字段 → py 值 vs ts 值` 并让用例失败。

变体矩阵：每个月份跑 9 种输入 —— `base / agreed0 / hours0 / tax_auto / marks / overtime_leave /
no_pay_items / min_wage_high / ot_manual`，共 **54 例**，含 `groups` 报表文案逐字对比。

**已验证「有牙齿」**：把 `OT_RATE_WORKDAY` 从 1.5 改成 1.6 → 6 个用例立即失败并报
`overtime_wage_workday: py=187.05 ts=199.52`；改回后全绿。
⇒ 对拍的价值不在「跑通」，而在**故意改坏时必须挂**。

> `fixtures/baseline.json` 含真实工资，**不入库**；本地没有该文件时对拍整组自动 skip。

## 五、已知风险与对策

| 风险 | 说明 | 对策 / 现状 |
|---|---|---|
| 金额取整口径 | 桌面版有「先算分项再反推合计」的恒等式（`非加班工资合计 = 应发 − 加班工资合计`），若自作主张相加会差 1 分 | 照抄，不做「优化」；对拍锁死 |
| **两个取整函数不能混用** | `calc.py::_round2` = `Decimal(str(v))` + **HALF_UP**（443.835→443.84、2.675→2.68）；`calc.py::_f` = Python `round(v,6)` 对**二进制精确值**做 half-to-even（0.1234565→0.123456）。JS 的 `toFixed` / `Math.round` 两者都不等价 | `core/num.ts` 的 `pyRound2` / `pyRound6`，23 条基准断言 |
| 合规判定 | 桌面版以 `min_wage_ok` / `work_time_legal` 两个布尔为唯一真相，文案只是显示 | 只移植布尔，不做字符串匹配 |
| ArkTS 语法限制 | 禁 `any`、禁索引签名、禁结构化类型 | `core/` 一开始就按 ArkTS 规则写，`tsc` + ArkTS 双通过 |
| UI 手势 / 密度 | 桌面双栏 + 密集表格 | 目标设备定为 **2in1**，保留双栏；窄屏靠**调用处**的 `layoutWeight` + 表格横向滚动兜底（见 7.3） |
| 导出 Excel | 鸿蒙无 `openpyxl` 等价物 | 已改导出 CSV（Excel 可直开）；xlsx 仍待评估 |
| `fileIo.writeSync` | 早期实测曾写入 0 字节 | 导出改为「写后 `stat` 校验字节数」，不一致直接报错（`Exporter.ets`） |
| 签名 / 上架 | 需华为开发者账号、证书、Profile | 自用可侧载 / 调试签名；上架需发布证书（README 有分档说明） |

## 六、实施里程碑

> 按时间顺序记录每个阶段做了什么、怎么验证；必须遵守的写法约定在「七」，技术决策在「八」。

### 6.1 阶段 0：工具链与取整函数（2026-11-08）✅

- 目录骨架 + `package.json` / `tsconfig.json` / `.gitignore`
- 工具链实测：`npm install`（45 包，走 npmmirror）→ `npm test` **23 passed**（当时；现为 141 例）、`tsc --noEmit` **0 error**
- 已落地第一块地基 `core/num.ts`：
  - `pyRound2(v)` —— 复刻 `Decimal(str(v))` + ROUND_HALF_UP（含 `-0.004 → -0.0` 的负零语义）
  - `pyRound6(v)` —— 复刻 Python `round(v, 6)`（按 IEEE 754 精确值做 half-even，用 BigInt 展开二进制）
  - 断言的期望值全部来自桌面版 Python **实测输出**，不是推测

### 6.2 阶段 1+2：逻辑层与数值对拍（2026-11-08）✅

目标设备确定为**鸿蒙 PC（2in1）** ⇒ 保留双栏布局，不做单列重排。

已落地（全部 `tsc` 0 error）：

| 文件 | 对应 | 说明 |
|---|---|---|
| `core/model.ts` | `app/model.py` | MonthBook / DayEntry / PayItem + `fromDict`/`toDict`、`safeFloat/safeInt/safeBool` 容错 |
| `core/calc.ts` | `app/calc.py` | `compute()` + `countAttendance()` + `buildGroups()` + 三个文案函数 |
| `core/holidays.ts` | `app/holidays.py` | 2025/2026 数据 + `classifyDay`（法定→补班→放假 的唯一优先级） |
| `core/config.ts` | `app/config.py` | 只搬参与计算的常量（OT 倍率）；UI 配色在做界面时补上（现已含色板 / 列宽） |

对拍结果：**54 个用例全部一致**（6 份真实存档 × 9 种变体：base / agreed0 / hours0 /
tax_auto / marks / overtime_leave / no_pay_items / min_wage_high / ot_manual），
含 `groups` 报表文案逐字对比。

**已验证「有牙齿」**：把 `OT_RATE_WORKDAY` 从 1.5 改成 1.6 → 6 个用例立刻失败并报
`overtime_wage_workday: py=187.05 ts=199.52`；改回后 77 例全绿（当时；现 141 例）。

### 6.3 阶段 1 补齐：最低工资表与 CSV（2026-11-08）✅

- `core/minwage.data.ts`：31 省 **394** 地区最低工资表 —— 由 `scripts/export_minwage.py`
  从 `app/wages.py` **自动导出，不手抄**；`tests/minwage.test.ts` 11 条断言锁规模、已知值
  （上海 2740/25、北京 2540/27.7、深圳 2520/23.7、广州 2500/23.7），并锁住
  「查不到的地区返回 null，不静默换成别的城市」。
- `core/csv.ts`：报表 CSV 生成（纯字符串，无 IO）；`tests/csv.test.ts` 12 条断言。

### 6.4 阶段 3/4：鸿蒙工程与界面（2026-11-08）✅

工具链（本机实测可用，不需要开 IDE）：

| 项 | 路径 / 版本 |
|---|---|
| DevEco Studio | `D:\DevEco Studio`（26.0.0.865） |
| HarmonyOS SDK | `D:\DevEco Studio\sdk\default`（26.0.0，API 26） |
| hvigor | `tools\hvigor\bin\hvigorw.js`（6.26.9） |
| 编译命令 | `powershell -File scripts\build_hap.ps1` → 产出 `entry-default-unsigned.hap` |

工程：`harmony/`（DevEco 生成，`deviceTypes: ["2in1"]`、targetSdk 26.0.0、compatibleSdk 6.1.1(24)）。

已验证：

- `core/*.ts` 原样拷进 `entry/src/main/ets/core/` 后 **ArkTS 编译通过**（含 `bigint`、
  `Map`、`Set`、getter、optional 属性 —— 这个 SDK 都接受）；
- **编译有牙齿**：往拷贝的 `num.ts` 末尾加一句 `const __teeth: number = 'x'` →
  `CompileArkTS` 立即失败并报 `BUILD FAILED`；恢复后 `BUILD SUCCESSFUL`；
- UI 外壳（侧栏 7 项 + 顶栏月份切换 + 应发/计入/不计入/到手 数值条 + 工作台 KPI 卡）编译通过。

### 6.5 报表导出与最低工资地区选择（2026-11-08）✅

- **报表导出 CSV**（`model/Exporter.ets`）：先调 `DocumentViewPicker.save()` 让用户选位置；
  不可用或被取消 → 回退到应用沙箱 `filesDir` 并把路径显示出来。
  - 写前加 **UTF-8 BOM**（否则 Excel 打开中文乱码）；
  - 写完 **`statSync` 校验字节数**，不一致直接报错 —— 专防「写 0 字节却显示成功」；
  - 模拟器（MateBook Pro / HarmonyOS 7.0.0）实测导出成功。
- **最低工资地区选择**：参数页「省 / 地区」两级菜单（`bindMenu`，不用 `@Builder` 传参），
  选中后自动填入月 / 小时最低工资并立即落盘。

#### 界面约定（避免「改了数没刷新」）

- 模型（纯 TS 非 `@Observed`）不直接放状态变量；统一「改模型 → `Snap.from(book)` 重算快照
  → 整体赋值给 `@Local snap`（V1 时代是 `@State`）」触发刷新（`model/Snap.ets`）。
- `core/` 是唯一真相，改完跑 `scripts/build_hap.ps1`（或 `sync_core.ps1`）同步到工程，**不要直接改 `ets/core/` 副本**。

### 6.6 功能补齐（2026-11-08）✅

- **联网查询**：`core/api.ts`（端点归一化 / 错误码中文 / JSON 括号配对提取 / 合理性校验）
  + `model/ApiClient.ets`（`@kit.NetworkKit` 的 HTTP）。内置 10 个服务商模板；超时 25s（节假日 45s）；
  校验区间：月薪 500~20000、时薪 5~200、时薪 ÷ 月薪 0.005~0.02 —— **模型幻觉不进账本**。
- **相关单位页**：`core/units.ts` 11 类单位（可重复角色、保存顺序），支持「🔍 去搜索」
  （复制关键词 + 打开站点）与银行「📋 复制」；整月锁定时只读动作仍可用。
  关键词**优先用统一社会信用代码**（唯一、精确），没填则用单位名称；两者都空时**只提示**
  「请先填写「统一社会信用代码」或「单位名称」，再去搜索」，不弹站点菜单（与桌面版一致）。
- **工资项目录**：`core/paycatalog.ts` 由 `scripts/export_paycatalog.py` 从桌面版 `model.py` 生成。
- **导出**：`core/csv.ts` 生成报表 / 年度 CSV（CRLF + UTF-8 BOM），`model/Exporter.ets` 负责保存。
- **桌面便利功能**：参数模板、复制工资项、整月锁定 / 解锁、历史月份列表、字段级「跟随最低工资」锁。
- **演示种子**：`rawfile/seed_months.json`（由 `scripts/export_seed.py` 生成，**不入库**）存在时首次启动导入一次；
  缺失不影响启动（`getRawFileContentSync` 异常被捕获并跳过）。

### 6.7 存储口径改为与桌面版一致（2026-11-09）✅

- 起因：HUKS 对称密钥不可导出，SDK 也没有 `backupKeyItem / restoreKeyItem`（`exportKeyItem` 只导公钥），
  而 `backup_config.json` 是 `allowToBackupRestore: true` → 换机 / 云恢复后「密文在、密钥没了」，账本会静默丢失。
- 改为：**账本 / 模板 / 单位 / 工作地明文**（应用沙箱隔离），**只有 API Key 用 HUKS 加密**
  ——`HUKS AES-256-GCM（由系统密钥库托管密钥，不可导出，无密钥文件）`。
- 保护：读取失败的月份（JSON 损坏 / 年月不符）进 `corruptMonths`，`persist()` 直接跳过写盘，**不覆盖原数据**（状态栏提示）。

### 6.8 代码优化（2026-11-09）✅

- **存储层**：`listMonths()` 改一次 `getAllSync()` 取全部键（原来是 `getAllSync` 后逐键再读）；
  `loadMonth()` 只读一次（不再「先探键再取值」）；API 配置三键合为一个 `api_config`（一次原子写入 + 回读校验）；
  锁定集合单独存 `locked_months` —— 历史列表不再为了拿 `locked` 去解析每个月正文。
- **内存缓存**：`model/BookCache.ets`（LRU，上限 12 个月；命中移到队尾），接口与 `Map` 一致，调用方无需改。
- **参数页**：`applyParam / paramNum / setParamNum` 三段 11 分支的 `if/else` 链改成 `switch`，
  且 `applyParam` 直接复用 `setParamNum`（原来同一份赋值逻辑抄了两遍）。
- **年度汇总**：去掉 `hasMonth()` 前置探测，直接看 `loadMonth()` 的 `null`（每月省一次读数）。
- **最低工资表**：`minWageRegions / minWageOf / minWageFirst` 由线性扫描改为模块级 `Map` 索引（O(1)）；
  同步改了生成器 `scripts/export_minwage.py`，重跑输出一致。
- **编码器复用**：`Crypto.ets` / `Exporter.ets` 的 `TextEncoder / TextDecoder / Base64Helper` 提为模块级单例。
- **配色与字号**：页面颜色改从 `pages/theme.ets` 取（不再到处写 `'#E6E8F0'`）；
  9/10fp 的小字统一上调到 11fp（模拟器上过小字号发虚）。

### 6.9 界面与交互对齐桌面版（2026-11-09）✅

- **考勤页版面按桌面版的层次重排**：操作条（4 颗按钮）与考勤统计小条都是**页面级独立一行/一组**
  （桌面版是 `bar` + `cg` 两个 layout），不再塞进月历卡 —— 卡只有左栏宽，四颗中文按钮会溢出到卡片外
  （用户反馈「一键铺超出格子」「统计没独立」）。
- **「清空考勤」补齐确认流程**：锁定时提示「月份已锁定，无法清空考勤」；未锁定弹确认框
  「确定清空 X 年 Y 月所有出勤状态与加班/请假记录吗？」→ 清空后顶栏提示（桌面版 `_clear_days`）。
- **相关单位「🔍 去搜索」补守卫**：关键词为空时**不弹站点菜单**，只提示
  「请先填写「统一社会信用代码」或「单位名称」，再去搜索」（与 `_open_unit_search_menu` 一致）；
  菜单里带「去搜索：<关键词>」标题，改用 `Menu + MenuItem` 以便点完自动收起。
- **参数模板**：没有模板时点「删除 / 重命名」只给提示、不弹对话框（桌面版同口径）。
- **关于对话框**：数据位置只显示 `preferencesDir` 真实路径，不再复述「用户首选项「xxx」（明文…）」。

### 6.10 按桌面版的文件分层拆分（2026-11-09）✅

桌面版是「一页一个 `pages_*.py`」，鸿蒙原来把 7 个页面全塞在 `pages/Index.ets`（4.4k 行）。
现在按同样粒度拆成独立组件（`Index.ets` 只留外壳 + 状态 + 写操作，相当于 `main_window.py`，**拆完 3.2k 行**）：

| 鸿蒙文件 | 对应桌面版 | 形态 |
|---|---|---|
| `pages/Index.ets` | `main_window.py` | 外壳（侧栏 / 顶栏 / 月份条）+ 全部状态与落盘 |
| `pages/OverviewPage.ets` | `pages_overview.py` | `@ComponentV2` + `@Param snap`（纯展示） |
| `pages/CalendarPage.ets` | `pages_calendar.py` | `@Param snap/locked/selOt/selLeave`；格子/面板动作全部回调 |
| `pages/ParamsPage.ets` | `pages_params.py` | `@Param` 表单值 + `@Event onParam(key,v)`；模板弹窗仍在外壳浮层 |
| `pages/SalaryPage.ets` | `pages_salary.py` | `@Param snap/locked/otBaseLocked`；工资项菜单 / 数值条都在组件内，写操作回调给外壳 |
| `pages/AnnualPage.ets` | `pages_annual.py` | `@Param year/rows/…` + `@Event onShift/onExport` |
| `pages/ReportPage.ets` | `pages_report.py` | `@Param snap`；分组折叠状态留在组件内 |
| `pages/UnitsPage.ets` | `pages_units.py` | `@Param rows/locked/stateText` + 7 个 `@Event` |

约定（照抄即可）：

- **数据往下走 `@Param`，动作往上走 `@Event`**；页面组件里不碰 `MonthStorage` / `SettingsStorage`；
- 只属于该页的 UI 状态（如报表分组展开、合规卡实测高度）**放组件内部**，不挂回 `Index`；
- 快照仍是「整体替换」：父级 `this.snap = Snap.from(...)` → 子组件 `@Param snap` 自动更新；
- 七个页面已全部拆完（`Index.ets` 只剩外壳 + 状态 + 写操作）。拆分时必须同步改
  `docs/porting-plan.md` 的这张表。

## 七、踩坑规则（照抄即可）

> 这一节是**必须遵守的写法约定**，不是历史故事；四条规则都验证过「改坏必须失败」。

### 7.1 局部刷新只跟踪状态变量（V2：`@Local`）：界面一律读快照

第一版日历是「界面直接读 `this.book.day(d).status`」，结果**七件事一起失效**：
点状态不更新、点格子右侧不变、铺官方表没反应、换月不刷新、格子与数据对不上……

根因两条：

1. **局部刷新只跟踪状态变量**（V2 的 `@Local` / V1 的 `@State`）。元素如果只读普通字段
   （`this.book`），改模型后它**不会变脏**，永远不会重绘；只有**真的读了 `this.snap`** 的元素才会更新。
2. **`ForEach` 按 key 缓存子组件**。key 不变 → 子组件被复用 → 里面即使读的是旧闭包值也不重建。
   所以 key 必须把「会影响显示的内容」都带上：
   `cellKey = day-status-mark-是否选中`、`rowKey = selDay + 整行状态`。

现在的规则（照抄即可）：

| 场景 | 做法 |
|---|---|
| 显示数据 | 一律从 `@Local snap` 读，**不碰 `book`** |
| 任何修改 | 改 `book` → `this.refresh()` → `this.snap = Snap.from(book, selDay)` |
| `ForEach` key | 包含所有影响显示的字段（含选中态） |
| `TextInput` | `onChange` 里**先把文本写回 `@Local`**，再改模型；否则重绘会拿旧值把用户输入顶掉 |
| 嵌套 `ForEach` | 外层 key 也要包含内层会变的东西，否则内层不会被重新 diff |

> 本项目已全部使用 V2；老代码里的 `@State` / `@Prop` 分别对应 `@Local` / `@Param`（见 8.3）。

### 7.2 `@Builder` 按值传参**不会**随状态刷新

第一版把这些写成 `@Builder chip(label, active)` / `dayCell(c)` / `stripItem(value)` /
`statCard(value)`，结果 `snap` 更新了、页面也重建了，但这些 builder **拿到的是创建那一刻的旧值**，
永远不刷新 —— 症状和「完全没反应」一模一样：

- 点 3 号 → 右侧状态 chip 不变
- 点「病假」→ 格子和顶部数值不变
- 点「清空考勤」→ 只有部分元素变

**规则：会变的值不要通过 `@Builder` 参数传。**

| 用错的写法 | 正确写法（V2） |
|---|---|
| `@Builder chip(label, active)` | `@ComponentV2 struct Chip { @Param active: boolean }`，父组件里 `Chip({ active: this.snap.x === y })` |
| `@Builder statCard(value)` | 同上，用 `@Param value` |
| `@Builder dayCell(c: CalCell)` | 同上，用 `@Param num / midText / hoursText / selected` |
| `@Builder fieldRow(value)` | 同上，`@Param value` + `@Event onEdit` 回调 |

`@Builder` 只用来**分组不带会变参数的静态结构**。
本项目的可复用件都在 **`pages/components.ets`**：`Chip / StripItem / MetaItem / StatCard / DayCell /
OtRow / RoRow / AnnualRowView / UnitRowView / FieldRow` 等（全部是 `@ComponentV2` + `@Param`）。

### 7.3 组件内部的 `layoutWeight` **不参与**父容器分配

现象：考勤日历 7 列宽窄不一，内容多的格子把旁边日期压住（“覆盖到隔壁天数上”）。

原因：`layoutWeight` 只对「父容器的**直接**子组件」生效。写在 `DayCell` / `StatCard` / `StripItem`
**内部根节点**上，父 `Row` 根本看不到，组件退化为「按内容自适应宽度」。

| 错误写法 | 正确写法 |
|---|---|
| 组件内部 `Column() {...}.layoutWeight(1)` | 组件内部 `.width('100%')`，**调用处** `DayCell({...}).layoutWeight(1)` |

配套：`DayCell` 加 `.clip(true)` + 文字 `maxLines(1)` + `textOverflow(Ellipsis)`，内容再长也不外溢。

### 7.4 `ForEach` key 重复会让节点直接消失

现象：`2025-08` 的日历里 `1/2/3` 号跑到周一~周三（8 月 1 日是**周五**），月初空白格整体没了。

原因：内层 key 用 `day-status-mark-sel`，而月初有多个占位格 `day=0` → key 全是 `0--0-n`，**重复**。
ArkUI 遇到重复 key 会丢弃/错误复用节点。

修法：key 里必须带**索引**：

```ts
ForEach(week, (c: CalCell, ci: number) => { ... },
        (c: CalCell, ci: number) => `${ci}-${this.cellKey(c)}`)
```

外层周数组同理带上 `wi`。教训：凡是有「占位/默认值元素」的列表，key 一定要加索引。

## 八、关键技术与决策

### 8.1 存储与加密：账本明文 + 仅 API Key 用 HUKS

**选型（2026-11-09 定，与桌面版一致）**：

| 数据 | 存储 | 加密 |
|---|---|---|
| 月份账本 / 参数模板 / 相关单位 / 工作地 / 锁定月份集合 | Preferences（`attendance_months` / `attendance_settings`） | **明文**（靠应用沙箱隔离，其它应用读不到） |
| API 配置（`api_config` 单键，内 `{u,m,k}`） | Preferences 的 `api_config` 键 | **只有 `k`（Key）走 HUKS**，URL / 模型名明文 |

加密描述统一为「算法（密钥托管位置，无密钥文件）」——「关于」对话框三端一致：

| 平台 | 描述 |
| --- | --- |
| Windows | `Windows DPAPI（由当前用户账户托管密钥，无密钥文件）` |
| 信创 / Linux | `SM2(C1C3C2) + SM4-CBC + HMAC-SM3（私钥存 <数据目录>/keys/，权限 0600）` |
| 鸿蒙 | `HUKS AES-256-GCM（由系统密钥库托管密钥，不可导出，无密钥文件）` |

⚠ 鸿蒙**不能把 Windows 那句照搬过来**：DPAPI 是同账户同机器可解；
HUKS 的密钥在系统密钥库内且**不可导出**（因此多写「不可导出」），
代价是换机后 Key 解不开、需重填（账本明文，不受影响）。

**为什么不整份加密**：

- HUKS 的对称密钥**不可导出**，本 SDK 也没有 `backupKeyItem / restoreKeyItem`（`exportKeyItem` 只导公钥）；
- `backup_config.json` 是 `allowToBackupRestore: true` → 系统备份会带回密文，却**不会带回密钥**；
- 换机 / 云恢复后「密文在、密钥没了」，账本必然解不开。而 API Key 丢了可以重填，账本丢了无法重建
  —— 所以两者用不同的保护策略（桌面版一直如此：只加密 `api_key`）。

实现要点（`model/Crypto.ets`，只用于 API Key）：

- 别名 `attendance_store_key`（发布后不要改，否则旧数据解不开）；AES-256-GCM，`HUKS_PADDING_NONE`，AAD = `"ATT1"`。
- **本 SDK（API 26）没有 `encryptItem`/`decryptItem`**，只有会话式接口：
  `initSession → finishSession`（一次给完整 input，数据量小不需要 `updateSession`）。
- 每次加密随机 12 字节 nonce（`cryptoFramework.createRandom()`），落盘为 `nonce || 密文本体 || AEAD(16B)`。
- API Key 的落盘格式带版本前缀：`h1:<base64>` 密文 / `h0:<base64>` 明文降级；读取时**不认识前缀按明文**。
- 降级策略：HUKS 不可用时写 `h0:` 并在界面显示「未加密」，`lastError` 记原因 —— **绝不静默**。
- 三个键合成一个（`api_config` = `{"u":url,"m":model,"k":token}`）：一次 `putSync` + 一次回读校验，
  不会出现「URL 写进去了、Key 没写进去」的半成品；旧的分键词写法已删除，不做兼容。
- 读取失败（JSON 坏 / 解密失败）→ `key` 返回空字符串，原因留在 `SettingsStorage.lastError`，
  界面在 API 提示行用 `⚠` 展示；`confirmApiDialog` 保存失败会**留在弹窗**显示原因。

#### 8.1.1 坑：`isKeyItemExist` 在 key 不存在时**抛错**而非返回 false

首次跑模拟器，状态一直显示「已保存 2026-11（未加密）」。加上「阶段 + 错误码」显示后拿到：

```
未加密：HUKS 密钥初始化：code=12000011 The entity does not exist.
```

`12000011` = `HUKS_ERROR_NOT_EXIST`。**这个异常是从 `huks.isKeyItemExist()` 抛出来的** ——
它表示「key 不存在」，属于**正常情况**，但被我们的 `try` 当成失败，于是永远走不到
`generateKeyItem()`，每次保存都降级明文。

修正：

```ts
try {
  return await huks.isKeyItemExist(KEY_ALIAS, probe);
} catch (e) {
  if ((e as BusinessError).code === ERR_NOT_EXIST) {   // 常量 = 12000011
    return false;          // 不存在 → 正常去生成
  }
  this.fail('HUKS 查询密钥', e as Error);
  throw e as Error;        // 其它错误才真失败
}
```

**教训**：加密/存储这类「静默降级」的功能，失败原因必须一路显示到界面上
（阶段名 + `BusinessError.code`），否则「未加密」三个字完全无法定位。
修正后状态变为「已保存 2026-11（加密）」。

代价与相应改动：

| 影响 | 处理 |
|---|---|
| HUKS 只有 Promise 接口 | `SettingsStorage.loadApiKey / saveApiKey` 是 `async`；月份读写走 Preferences 同步 API |
| 启动加载 | `aboutToAppear` → `initData()`（预热密钥 + 迁移旧数据） |
| 切月 | `changeMonth()` 保持 `async`，未命中缓存时 `await loadMonth` |
| 自动保存 | `persist()` 保持同步返回，落盘 Promise 完成后回填 `saveState`（`保存中…` → `已保存 YYYY-MM`） |
| 读取失败 | 归档解析失败（JSON 损坏 / 年月不符）时返回 `null` + `lastError`，该月进 `corruptMonths`；`persist()` **跳过写盘**，绝不覆盖原数据 |

已验证：`BUILD SUCCESSFUL`（HAP 同尺寸）、`npm test` 141 项全绿（`core/` 未受改动）。

### 8.2 官方文档核对（developer.huawei.com）

| 文档原文（要点） | 对我们的影响 |
|---|---|
| @Builder「参数传递规则」：**按值传递时状态变量改变不会引起 @Builder 内 UI 刷新** | 即规则 7.2，官方确认 |
| 按引用传递**仅在「只传一个参数、且该参数是对象字面量」时**生效 | 多参数一律别指望刷新 |
| **两个及以上参数**即使对象字面量也不刷新 | `chip(label, active)` 必然失效 |
| 私有 @Builder 的建议写法：**状态变量通过 `this` 访问，不要通过参数传** | `placeholder()` 已改成读 `this.pageTitle()` |
| API 20+ 提供 `UIUtils.makeBinding()` 做「按回调传递」 | compatibleSdk 24 可用，但 `@ComponentV2` + `@Param` 更通用 |
| ForEach「组件创建规则」：**键值已存在 → 复用组件，不创建新组件** | key 必须含会影响显示的数据（不含 index —— 文档明确不建议，但占位元素必须带索引去重，见 7.4） |
| ForEach「数据源数组项子属性变化」：需 `@Observed`/`@ObjectLink` | 用「整体重建 snap + key 带状态」代替，等价且不污染 core |
| 状态管理概述：**新应用建议直接用 V2**（@ObservedV2/@Trace/@ComponentV2） | 已按此迁移，见 8.3 |

**关于 core 为什么不加 V2 装饰器**：`core/` 必须保持**纯 TS**（要在 Node 里跑 141 个测试，
含与桌面版 Python 的 54 例对拍），`@ObservedV2/@Trace` 是 ArkTS 专有装饰器，加进去 `tsc` / `vitest` 就跑不了。
UI 层用 `@Local` / `@Param` 做观测，业务模型依旧靠「重算快照」，代价是每次改动多一次 `compute()`（实测 <1ms）。

### 8.3 状态管理 V2 迁移（已全部落地）

官方文档「状态管理概述」：**对于新开发的应用，建议直接使用 V2 版本范式**。
UI 层已全部迁到 V2，实测**一次编译通过**：

| V1（旧） | V2（现） |
|---|---|
| `@Entry @Component` | `@Entry @ComponentV2` |
| `@State` | `@Local` |
| `@Prop` | `@Param`（**按引用同步，不做深拷贝**） |
| 回调属性 `onTap: () => void` | `@Event onTap: () => void` |

`core/` **仍是纯 TS**，原因不变：它要在 Node 里跑 141 个测试（含与桌面版 Python 的 54 例数值对拍），
`@ObservedV2/@Trace` 是 ArkTS 专有装饰器，加进去 `tsc`/`vitest` 就跑不了。

⚠ 实测记录：把 `@ObservedV2/@Trace` 写在 `.ts` 文件里，ArkTS 编译器**接受**（能编译通过），
但「能否真正产生观测能力」需真机验证；而且 V2 观测只在 `@ComponentV2` 组件里生效，
所以并没有「只改 core 就能去掉快照」这条捷径。

**V2 下的两条纪律仍然有效**（与 7.2 / 7.4 相同，只是换成 V2 装饰器）：
1. 会变的值走 `@Param` 组件，不要通过 `@Builder` 参数传；
2. `ForEach` 的 key 必须包含会影响显示的数据。

### 8.4 存储选型：为什么用 Preferences

| 官方文档 | 原文要点 | 我们的结论 |
|---|---|---|
| 应用文件访问(ArkTS) | 示例 `openSync(READ_WRITE\|CREATE)` + `writeSync(fd, ...)`，返回写入字节数 | **用于导出 CSV**；早期曾出现 `writeSync` 恒返回 0，因此写完一律 `stat` 校验字节数（`Exporter.ets`） |
| 通过用户首选项实现数据持久化 (ArkTS) | 专为「轻量键值型数据」；`getPreferencesSync / putSync / getSync / flushSync` 全同步；key ≤ 1024B、string value ≤ 16MB、总量建议 ≤ 50MB | **采用**：一个月一个 key、**明文 JSON**（约 5KB）；API 配置合成单键 `api_config`，其中 Key 用 HUKS 加密 |
| 同上 · 约束 | XML 模式不支持多进程并发；数据非 UTF-8 时要用 Uint8Array | 单进程单窗口，符合前提 |

存档结构：

```
Preferences 文件 attendance_months（应用沙箱内）
  "2026-11" → {"year":2026,"month":11,"days":[...],"pay_items":[...], ...}
  "2026-12" → ...

Preferences 文件 attendance_settings（应用沙箱内）
  "api_config"    → {"u":"https://...","m":"gpt-4o-mini","k":"h1:..."}   ← 只有 k 是密文
  "locked_months" → "2026-09,2026-10"                                    ← 锁定集合（历史列表不用读正文）
  "units" / "units_locked" / "templates" / "work_region" / seed 标记      ← 均为明文
```

保存流程：`putSync` → `flushSync` → `getSync` 回读比对（写读不一致就报错，绝不静默成功）。
值是 `MonthBook.to_dict()` 的**明文 JSON**（与桌面版同构，字段名 / 默认值一致）。

**读历史别再逐月解析**：只有 `listMonths()` 一次 `getAllSync` 拿全部键，
锁定状态查内存里的 `lockedMonths`；某月正文只在真正切到该月 / 做年度汇总时读，
并放进 `model/BookCache.ets`（LRU，上限 12 个月，命中即移到队尾）。

## 九、待办

| 项 | 说明 | 前置条件 |
|---|---|---|
| `xlsx` 导出 | 目前只出 CSV | 评估三方库，或自行拼最小 xlsx |
| 上架 / 发布签名 | 现在只能调试签名或侧载 | 华为开发者账号 + 发布证书 / Profile |
| 对拍覆盖扩充 | 现在 6 份真实存档 × 9 变体 | 补充极端值（0 工时 / 超长连班 / 空工资项）存档 |

## 附录：常用命令

> `npm` / `build_hap.ps1` 在 **`harmony-app/`** 下执行；`一键打包.bat` 与 `dump_baseline.py` 在**仓库根目录**执行。

```powershell
# （harmony-app/）逻辑层测试，不需要鸿蒙工具链
npm install
npm test

# （harmony-app/）同步 core → ets/core 并编译 HAP
powershell -ExecutionPolicy Bypass -File scripts/build_hap.ps1

# （仓库根）一键打包（自动收集签名版）
一键打包.bat harmony
一键打包.bat harmony -Install

# （仓库根）生成对拍基准（含真实工资，勿入库）
.venv\Scripts\python.exe harmony-app\scripts\dump_baseline.py --data-dir <存档目录> --out harmony-app\fixtures\baseline.json
```
