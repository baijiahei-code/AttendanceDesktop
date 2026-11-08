# 移植方案（草案 v1）

> **现状（2026-11-08）**：本方案已全部落地 —— `core/` 逻辑层与桌面版数值对拍（包含 54 个对拍用例）通过，
> 七个页面（工作台 / 相关单位 / 考勤 / 薪酬构成 / 参数 / 报表 / 年度汇总）均已实现，
> 存储层改用 **Preferences + HUKS（AES-256-GCM）**，可出一键打包的 HAP（release 实测可运行）。
> 本文保留为**设计与决策记录**；日常使用/构建请看 [`../README.md`](../README.md)。
> 仍未做：与桌面版存档的**文件导入/导出**（需真机验证 `fileIo` 后再补）。

## 一、模块映射（Python → TS）

行数取自源仓库实测（2026-11-08：32 个 py 文件、10,264 行）。

| 源文件 | 行数 | 目标 | 处理方式 |
|---|---|---|---|
| `app/calc.py` | 482 | `core/calc.ts` | **逐函数翻译**，含 `_count_attendance` / `_build_groups` / `compliance_standard_text` / `overtime_rate_text` |
| `app/model.py` | 464 | `core/model.ts` | class + `from_dict`/`to_dict`，保留「未知键忽略」「重复 role 保序」等既有语义 |
| `app/holidays.py` | 150+ | `core/holidays.ts` | 2026 年官方数据 + `day_kind` / `classify_day` 单一判定入口 |
| `app/wages.py` 数据段 | ~900 | `core/minwage.data.ts` | 31 省 394 地区的月/时最低工资表；**网络层不做**（鸿蒙端不联 AI 接口） |
| `app/config.py` | 100+ | `core/config.ts` | 常量：`PAYABLE_DAYS=21.75`、`OT_RATE_*`、合规阈值 220/36/26/3 |
| `app/storage.py` | 355 | `platform/storage.ets` | 鸿蒙侧重写（应用沙箱 + 原子写 + `.bak`），格式与桌面版一致 |
| `app/crypto.py` `app/gm.py` | 660 | `platform/crypto.ets` | 换鸿蒙 Crypto Architecture Kit（原生 SM2/SM3/SM4），**不移植 Python 实现** |
| `app/pages_*.py` `widgets/` `main_window.py` `style.py` `ui.py` | ~6000 | `harmony/entry/src/main/ets/pages/*` | ArkUI 全部重写，不复用 |

## 二、数值对拍设计（阶段 2 的核心交付）

思路：**同一份输入 JSON，两个实现各自算，逐字段 diff。**

1. 输入取自真实存档目录（只读）：`%LOCALAPPDATA%\工作考勤表\data\YYYY-MM.json`，
   路径通过环境变量 `ATT_DATA_DIR` 覆盖，脚本里不写死个人路径。
2. Python 侧导出基准：
   ```
   .venv\Scripts\python.exe scripts\dump_baseline.py --data-dir <dir> --out fixtures\baseline.json
   ```
   输出 `{ "2026-10": { ...Result 全字段... }, ... }`。
3. TS 侧：`npm run parity` 读同一批 JSON，跑 `core/calc.ts`，与 `baseline.json` 比对。
4. 判定：金额字段按 `round(x, 2)` 后**全等**；布尔/文案字段**字符串全等**；
   任何不一致打印 `文件 → 字段 → py 值 vs ts 值` 并退出码非 0。

这一步能抓住 90% 的移植错误（取整位置、恒等式、默认值、单位口径），值得先做。

## 三、已知风险

| 风险 | 说明 | 应对 |
|---|---|---|
| 金额取整口径 | 桌面版有「先算分项再反推合计」的恒等式（`非加班工资合计 = 应发 − 加班工资合计`），TS 若自作主张相加会差 1 分 | 照抄，不做「优化」 |
| **两个取整函数不能混用** | `calc.py::_round2` = `Decimal(str(v))` + **HALF_UP**（443.835→443.84、2.675→2.68）；`calc.py::_f` = Python `round(v,6)` = 对**二进制精确值**做 half-to-even（0.1234565→0.123456）。JS 的 `toFixed`/`Math.round` 两者都不等价 | 已在 `core/num.ts` 实现 `pyRound2` / `pyRound6` 并有 23 条基准断言 |
| 合规判定 | 桌面版是 `min_wage_ok` / `work_time_legal` 两个布尔为唯一真相，文案只是显示 | 只移植布尔，不移植字符串匹配 |
| ArkTS 语法限制 | 禁 `any`、禁索引签名、禁结构化类型 | `core/` 一开始就按 ArkTS 规则写 |
| UI 手势/密度 | 桌面双栏 + 密集表格，手机必须单列重排 | 阶段 4 先做最小集，逐屏确认 |
| 导出 Excel | 鸿蒙无 `openpyxl` 等价物 | 先导出 CSV；xlsx 待评估三方库 |
| 签名/上架 | 需华为开发者账号、证书、Profile | 阶段 5 前确认是否需要上架（自用可侧载） |

## 四、明确不做（第一版）

- 联网查询最低工资 / 节假日（AI 接口）：鸿蒙端不联，用内置官方表。
- 参数模板、相关单位的搜索跳转等桌面便利功能：按需再加。
- 与桌面版的实时同步：靠「导入/导出 JSON」即可。

## 五、进度

### 阶段 0（2026-11-08）✅

- 目录骨架 + `package.json` / `tsconfig.json` / `.gitignore`
- 工具链实测：`npm install`（45 包，走 npmmirror）→ `npm test` **23 passed**、`tsc --noEmit` **0 error**
- 已落地第一块地基 `core/num.ts`：
  - `pyRound2(v)` —— 复刻 `Decimal(str(v))` + ROUND_HALF_UP（含 `-0.004 → -0.0` 的负零语义）
  - `pyRound6(v)` —— 复刻 Python `round(v, 6)`（按 IEEE 754 精确值做 half-even，用 BigInt 展开二进制）
  - 断言的期望值全部来自桌面版 Python **实测输出**，不是推测

### 阶段 1 + 2（2026-11-08）✅

目标设备确定为**鸿蒙 PC（2in1）** ⇒ 保留双栏布局，不做单列重排。

已落地（全部 `tsc` 0 error）：

| 文件 | 对应 | 说明 |
|---|---|---|
| `core/model.ts` | `app/model.py` | MonthBook / DayEntry / PayItem + `fromDict`/`toDict`、`safeFloat/safeInt/safeBool` 容错 |
| `core/calc.ts` | `app/calc.py` | `compute()` + `countAttendance()` + `buildGroups()` + 三个文案函数 |
| `core/holidays.ts` | `app/holidays.py` | 2025/2026 数据 + `classifyDay`（法定→补班→放假 的唯一优先级） |
| `core/config.ts` | `app/config.py` | 只搬参与计算的常量（OT 倍率）；UI 配色等做界面时再补 |

对拍结果：**54 个用例全部一致**（6 份真实存档 × 9 种变体：base / agreed0 / hours0 /
tax_auto / marks / overtime_leave / no_pay_items / min_wage_high / ot_manual），
含 `groups` 报表文案逐字对比。

**已验证「有牙齿」**：把 `OT_RATE_WORKDAY` 从 1.5 改成 1.6 → 6 个用例立刻失败并报
`overtime_wage_workday: py=187.05 ts=199.52`；改回后 77 测试全绿。

### 阶段 1 剩余（小）✅ 2026-11-08 完成

- `core/minwage.data.ts`：31 省 **394** 地区最低工资表 —— 由 `scripts/export_minwage.py`
  从 `app/wages.py` **自动导出，不手抄**；`tests/minwage.test.ts` 11 条断言锁规模、已知值
  （上海 2740/25、北京 2540/27.7、深圳 2520/23.7、广州 2500/23.7），并锁住
  「查不到的地区返回 null，不静默换成别的城市」。
- `core/csv.ts`：报表 CSV 生成（纯字符串，无 IO）；`tests/csv.test.ts` 12 条断言。

### 阶段 3/4 开工（2026-11-08）🔄

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

### 数据导入 / 导出（2026-11-08）✅

- **报表导出 CSV**（`model/Exporter.ets`）：先调 `DocumentViewPicker.save()` 让用户选位置；
  不可用或被取消 → 回退到应用沙箱 `filesDir` 并把路径显示出来。
  - 写前加 **UTF-8 BOM**（否则 Excel 打开中文乱码）；
  - 写完 **`statSync` 校验字节数**，不一致直接报错 —— 专防「写 0 字节却显示成功」；
  - 模拟器（MateBook Pro / HarmonyOS 7.0.0）实测导出成功。
- **最低工资地区选择**：参数页「省 / 地区」两级菜单（`bindMenu`，不用 `@Builder` 传参），
  选中后自动填入月 / 小时最低工资并立即落盘。

界面约定（避免“改了数没刷新”）：

- 模型（纯 TS 非 `@Observed`）不直接放 `@State`；统一「改模型 → `Snap.from(book)` 重算快照
  → 整体赋值给 `@State snap`」触发刷新（`ets/model/Snap.ets`）。
- `core/` 是唯一真相，改完跑 `scripts/sync_core.ps1` 同步到工程（不要直接改工程里的副本）。

### ⚠ ArkUI 刷新机制（2026-11-08 踩过的坑，务必遵守）

第一版日历是「界面直接读 `this.book.day(d).status`」，结果**七件事一起失效**：
点状态不更新、点格子右侧不变、铺官方表没反应、换月不刷新、格子与数据对不上……

根因两条：

1. **局部刷新只跟踪 `@State`**。元素如果只读普通字段（`this.book`），改模型后它**不会变脏**，
   永远不会重绘。`@State snap` 的赋值只能救那些**真的读了 `this.snap`** 的元素。
2. **`ForEach` 按 key 缓存子组件**。key 不变 → 子组件被复用 → 里面即使读的是旧闭包值也不重建。
   所以 key 必须把「会影响显示的内容」都带上：
   `cellKey = day-status-mark-是否选中`、`rowKey = selDay + 整行状态`。

现在的规则（照抄即可）：

| 场景 | 做法 |
|---|---|
| 显示数据 | 一律从 `@State snap` 读，**不碰 `book`** |
| 任何修改 | 改 `book` → `this.refresh()` → `this.snap = Snap.from(book, selDay)` |
| `ForEach` key | 包含所有影响显示的字段（含选中态） |
| `TextInput` | `onChange` 里**先把文本写回 `@State`**，再改模型；否则重绘会拿旧值把用户输入顶掉 |
| 嵌套 `ForEach` | 外层 key 也要包含内层会变的东西，否则内层不会被重新 diff |

### ⚠⚠ `@Builder` 按值传参**不会**随状态刷新（第二课，同一天踩到）

第一版把这些写成 `@Builder chip(label, active)` / `dayCell(c)` / `stripItem(value)` /
`statCard(value)`，结果 `snap` 更新了、页面也重建了，但这些 builder **拿到的是创建那一刻的旧值**，
永远不刷新 —— 症状和「完全没反应」一模一样：

- 点 3 号 → 右侧状态 chip 不变
- 点「病假」→ 格子和顶部数值不变
- 点「清空考勤」→ 只有部分元素变

**规则：会变的值不要通过 `@Builder` 参数传。**

| 用错的写法 | 正确写法 |
|---|---|
| `@Builder chip(label, active)` | `@Component struct Chip { @Prop active: boolean }`，父组件里 `Chip({ active: this.snap.x === y })` |
| `@Builder statCard(value)` | 同上，用 `@Prop value` |
| `@Builder dayCell(c: CalCell)` | 同上，用 `@Prop num/status/mark/selected` |
| `@Builder fieldRow(value)` | 同上，`@Prop value` + `onEdit` 回调 |

`@Builder` 只用来**分组不带会变参数的静态结构**。
本项目的可复用件都在 `pages/Index.ets` 顶部：`Chip / StripItem / StatCard / DayCell / FieldRow`。

### ⚠⚠ 第三课：自定义组件内部的 `layoutWeight` **不参与**父容器分配

现象：考勤日历 7 列宽窄不一，内容多的格子把旁边日期压住（“覆盖到隔壁天数上”）。

原因：`layoutWeight` 只对「父容器的**直接**子组件」生效。写在 `DayCell` / `StatCard` / `StripItem`
**内部根节点**上，父 `Row` 根本看不到，组件退化为「按内容自适应宽度」。

| 错误写法 | 正确写法 |
|---|---|
| 组件内部 `Column() {...}.layoutWeight(1)` | 组件内部 `.width('100%')`，**调用处** `DayCell({...}).layoutWeight(1)` |

配套：`DayCell` 加 `.clip(true)` + 文字 `maxLines(1)` + `textOverflow(Ellipsis)`，内容再长也不外溢。

### ⚠⚠ 第四课：`ForEach` key 重复会让节点直接消失

现象：`2025-08` 的日历里 `1/2/3` 号跑到周一~周三（8 月 1 日是**周五**），月初空白格整体没了。

原因：内层 key 用 `day-status-mark-sel`，而月初有多个占位格 `day=0` → key 全是 `0--0-n`，**重复**。
ArkUI 遇到重复 key 会丢弃/错误复用节点。

修法：key 里必须带**索引**：

```ts
ForEach(week, (c: CalCell, ci: number) => { ... },
        (c: CalCell, ci: number) => `${ci}-${this.cellKey(c)}`)
```

外层周数组同理带上 `wi`。教训：凡是有「占位/默认值元素」的列表，key 一定要加索引。

### 存档加密（HUKS，2026-11-08 落地）

选型：**HUKS（`@kit.UniversalKeystoreKit`）+ Preferences**，而非自己管密钥。

| 方案 | 结论 |
|---|---|
| 自己生成密钥存 Preferences | ❌ 密钥和数据放同一个文件里，等于没加密 |
| 密钥硬编码在代码里 | ❌ 反编译即可解 |
| **HUKS** | ✅ 密钥由系统密钥库生成、**不可导出**，应用数据被拷走也解不开 |

实现要点（`model/Crypto.ets`）：

- 别名 `attendance_master_v1`；AES-256-GCM，`HUKS_PADDING_NONE`，AAD = `"ATT1"`。
- **本 SDK（API 26）没有 `encryptItem`/`decryptItem`**，只有会话式接口：
  `initSession → finishSession`（一次给完整 input，数据量小不需要 `updateSession`）。
- 每次加密随机 12 字节 nonce（`cryptoFramework.createRandom()`），存 `nonce || ciphertext`。
- 落盘格式带版本前缀：`h1:<base64>` 密文 / `h0:<base64>` 明文降级；读取时**不认识前缀按明文**（兼容早期数据）。
- 降级策略：HUKS 不可用时写 `h0:` 并在界面显示「未加密」，`lastError` 记原因 —— **绝不静默**。

#### ⚠ 踩过的坑：`isKeyItemExist` 在 key 不存在时**抛错**而非返回 false

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
  return await huks.isKeyItemExist(ALIAS, probe);
} catch (e) {
  if ((e as BusinessError).code === 12000011) {
    return false;          // 不存在 → 正常去生成
  }
  throw e as Error;        // 其它错误才真失败
}
```

**教训**：加密/存储这类「静默降级」的功能，失败原因必须一路显示到界面上
（阶段名 + `BusinessError.code`），否则「未加密」三个字完全无法定位。
修正后状态变为「已保存 2026-11（加密）」。

代价与相应改动：

| 影响 | 处理 |
|---|---|
| HUKS 只有 Promise 接口 | `MonthStorage.loadMonth/saveMonth`、`SettingsStorage.loadUnitsText/saveUnitsText`、`rebuildAnnual()` 全部改 `async` |
| 启动加载 | `aboutToAppear` → `initData()`（内部 `await`） |
| 切月 | `changeMonth()` 改 `async`，未命中缓存时 `await` 读盘 |
| 自动保存 | `persist()` 保持同步返回，落盘 Promise 完成后回填 `saveState`（`保存中…` → `已保存（加密）`） |
| 解密失败 | 返回 `null` + `lastError`，**不覆盖已有密文**，界面显示「仅内存（原因）」 |

已验证：`BUILD SUCCESSFUL`（HAP 同尺寸）、`npm test` 91 项全绿（`core/` 未受改动）。

### 官方文档核对（2026-11-08，developer.huawei.com）

| 文档原文（要点） | 对我们的影响 |
|---|---|
| @Builder「参数传递规则」：**按值传递时状态变量改变不会引起 @Builder 内 UI 刷新** | 上面的第 2 课，官方确认 |
| 按引用传递**仅在「只传一个参数、且该参数是对象字面量」时**生效 | 多参数一律别指望刷新 |
| **两个及以上参数**即使对象字面量也不刷新 | `chip(label, active)` 必然失效 |
| 私有 @Builder 的建议写法：**状态变量通过 `this` 访问，不要通过参数传** | 我们的 `placeholder()` 已改成读 `this.pageTitle()` |
| API 20+ 提供 `UIUtils.makeBinding()` 做「按回调传递」 | 我们 compatibleSdk 24 可用，但 @Component+@Prop 更通用 |
| ForEach「组件创建规则」：**键值已存在 → 复用组件，不创建新组件** | 所以 key 必须含会影响显示的数据（不含 index —— 文档明确不建议） |
| ForEach「数据源数组项子属性变化」：需 `@Observed`/`@ObjectLink` | 我们用「整体重建 snap + key 带状态」代替，等价且不污染 core |
| 状态管理概述：**新应用建议直接用 V2**（@ObservedV2/@Trace/@ComponentV2） | 见下方取舍 |

**关于 V2**：文档推荐新应用用 V2（深度观测、属性级更新）。我们没有直接迁，原因是
`core/` 必须保持**纯 TS**（要能在 Node 里跑对拍测试，不能加 `@ObservedV2/@Trace` 装饰器）。
用「快照重算 + @Prop」达到同样效果，代价是每次改动多一次 `compute()`（实测 <1ms）。

### ✅ 状态管理 V2 迁移（2026-11-08，按官方建议执行）

官方文档「状态管理概述」：**对于新开发的应用，建议直接使用 V2 版本范式**。
UI 层已全部迁到 V2，实测**一次编译通过**：

| V1（旧） | V2（现） |
|---|---|
| `@Entry @Component` | `@Entry @ComponentV2` |
| `@State` | `@Local` |
| `@Prop` | `@Param`（**按引用同步，不做深拷贝**） |
| 回调属性 `onTap: () => void` | `@Event onTap: () => void` |

`core/` **仍是纯 TS**，原因不变：它要在 Node 里跑 91 个测试（含与桌面版 Python 的 54 例数值对拍），
`@ObservedV2/@Trace` 是 ArkTS 专有装饰器，加进去 `tsc`/`vitest` 就跑不了。

⚠ 实测记录：把 `@ObservedV2/@Trace` 写在 `.ts` 文件里，ArkTS 编译器**接受**（能编译通过），
但「能否真正产生观测能力」需真机验证；而且 V2 观测只在 `@ComponentV2` 组件里生效，
所以并没有「只改 core 就能去掉快照」这条捷径。

**V2 下的两条纪律仍然有效**（已踩两次）：
1. 会变的值走 `@Param` 组件，不要通过 `@Builder` 参数传；
2. `ForEach` 的 key 必须包含会影响显示的数据。

### 存储选型（2026-11-08，按官方文档定）

| 官方文档 | 原文要点 | 我们的结论 |
|---|---|---|
| 应用文件访问(ArkTS) | 示例就是 `openSync(READ_WRITE\|CREATE)` + `writeSync(fd, 'Hello world')`，返回写入字节数 | 用法没错，但本机实测 **`writeSync` 恒返回 0、文件 0 字节**（string / ArrayBuffer 都试过）→ 当前环境不可用 |
| 通过用户首选项实现数据持久化 (ArkTS) | 专为「轻量键值型数据」；`getPreferencesSync / putSync / getSync / flushSync` 全同步；key ≤ 1024B、string value ≤ 16MB、总量建议 ≤ 50MB | **采用**：一个月一个 key（`2026-11` → `MonthBook.to_dict()` 的 JSON，约 5KB） |
| 同上 · 约束 | XML 模式不支持多进程并发；数据非 UTF-8 时要用 Uint8Array | 单进程单窗口，符合前提 |

存档结构：

```
Preferences 文件 attendance_months（应用沙箱内）
  "2026-11" → {"year":2026,"month":11,"days":[...],"pay_items":[...], ...}
  "2026-12" → ...
```

保存流程：`putSync` → `flushSync` → `getSync` 回读比对（写读不一致就报错，绝不静默成功）。
数据格式与桌面版 `MonthBook.to_dict()` 同构，将来做「导出/导入」时直接落成 `YYYY-MM.json`。

⚠ 待办：**文件导入/导出**（读桌面版存档）要等真机验证 `fileIo.writeSync` 是否正常，
届时按官方「应用文件访问」示例实现。





