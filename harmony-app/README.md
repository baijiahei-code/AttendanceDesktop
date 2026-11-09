# 工作考勤表 · 鸿蒙版（HarmonyOS / ArkTS）

本目录是「工作考勤表」仓库的**鸿蒙端实现**，与仓库根目录下的桌面版（Python / PySide6）是
同一款软件的两个平台版本，共用同一套核算口径（`core/` 已与桌面版 `app/calc.py` 做数值对拍）。

## 目录结构

```
harmony-app/
├─ core/       纯 TS 逻辑层（模型 / 核算 / 节假日 / 最低工资表 / 导出）
├─ tests/      Vitest 单测 + 与桌面版 Python 的数值对拍（共 141 例，对拍需本地生成基准）
├─ fixtures/   对拍基准目录（`baseline.json` 含真实工资，**本地生成、不入库**）
├─ scripts/    对拍导出、数据表导出、HAP 构建等工具
├─ docs/       移植方案与进度
└─ harmony/    鸿蒙工程（DevEco Studio 工程，2in1 / API 26）
```

`core/` 的硬约束：**必须同时满足 Node（vitest）与 ArkTS 语法** —— 禁 `any`/`unknown`、
禁索引签名、禁 `Function` 类型，全部用 class + 显式类型。因此它可以在 Node 里跑测试。

> `harmony/entry/src/main/ets/core/` 是 `core/` 的**自动副本**（由 `scripts/build_hap.ps1` 同步）。
> 改逻辑只改根目录的 `core/*.ts`，不要手改 `ets/core/`。

## 跑逻辑层测试（不需要鸿蒙工具链）

```powershell
npm install
npm test          # 单元用例（纯逻辑）+ 对拍用例（需本地生成 fixtures/baseline.json）
```

> 仓库里**不带** `fixtures/baseline.json`（含真实工资）：没有该文件时对拍分支自动 skip，
> 只跑 87 个单元用例；自己生成后变 141 个（生成方法见「数据与隐私」）。

## 构建 HAP

前置：**DevEco Studio 26.x**（含 HarmonyOS SDK）、Node.js。

### 一键打包（推荐）

整个仓库只有**两个入口**（每个平台一个），鸿蒙版是其中一个子命令：

**Windows**：仓库根目录双击 **`一键打包.bat`**，或命令行：

```powershell
一键打包.bat                    # 桌面版（Windows exe + 安装程序）
一键打包.bat harmony            # 鸿蒙版 HAP
一键打包.bat harmony -Install   # 鸿蒙版 HAP + 安装到已连接设备并启动
一键打包.bat harmony -Clean     # 先清构建缓存
一键打包.bat --help             # 帮助
```

**macOS / Linux / Git Bash / WSL**：仓库根目录执行 **`./一键打包.sh`**：

```bash
./一键打包.sh                   # 桌面版 deb（默认）
./一键打包.sh rpm               # 桌面版 rpm
./一键打包.sh all               # 桌面版 deb + rpm
./一键打包.sh harmony           # 鸿蒙版 HAP
./一键打包.sh harmony --install # 打包 + 安装并启动
./一键打包.sh harmony --check   # 只自检工具链（不构建）
```

脚本会自动：找 DevEco Studio → 同步 `core/` → 编译（release，失败自动退回 debug）
→ 产物复制到 `release/AttendanceHarmony-v<版本>-<模式>[-unsigned].hap`。

- DevEco 查找顺序：`-DevEco` / `DEVECO_STUDIO_HOME` → `D:\DevEco Studio` → `C:\Program Files\Huawei\DevEco Studio`；
  macOS 自动找 `/Applications/DevEco-Studio.app/Contents`
- `hdc` 查找顺序：`%HDC%` / `$HDC` → PATH → DevEco 的 `sdk/default/openharmony/toolchains/hdc`
- 未配签名时产物带 `-unsigned`（只能装到开了调试授权的设备）；在 DevEco 里配好
  `Signing Configs` 后，脚本会自动收集签名版

> ⚠ **HAP 无法在鸿蒙 PC 上编译**：鸿蒙设备不带 DevEco Studio（HarmonyOS SDK / hvigor / node），
> 构建必须在 Windows 或 macOS 开发机上完成。设备上只需要安装产物：
> `hdc install -r AttendanceHarmony-v<版本>-<模式>.hap`（在脚本里加 `--install` 可自动完成）。
> 在鸿蒙终端里执行 `pack_hap.sh --check` 会直接告诉你缺什么。

### 手动构建

> ⚠ **hvigor 不支持含中文的绝对路径**（会报 `Invalid project path`）。
> 所以整个仓库请 clone 到 ASCII 路径（如 `C:\dev\AttendanceDesktop`）；
> 若仓库路径含中文，可只把 `harmony-app/` 复制到 ASCII 路径后再构建。
>
> 平时开发可用环境变量指定 DevEco 位置（默认 `D:\DevEco Studio`）：
> `$env:DEVECO_STUDIO_HOME = 'C:\Program Files\DevEco Studio'`

```powershell
# 1) 同步 core → ets/core 并编译 HAP
powershell -ExecutionPolicy Bypass -File scripts/build_hap.ps1

# 产物
harmony/entry/build/default/outputs/default/entry-default-unsigned.hap
```

首次构建前无需安装 ohpm 依赖（`harmony/oh_modules` 不入库）；只有要在设备上跑
`ohosTest` 时才需要先 `cd harmony; ohpm install`。

安装到模拟器/真机（需要 `hdc`）：

```powershell
hdc install -r harmony/entry/build/default/outputs/default/entry-default-unsigned.hap
hdc shell aa start -a EntryAbility -b com.example.attendanceharmony
```

⚠ 正式分发需要华为开发者证书（`.p12` / `.p7b` / profile）做签名，仓库里不含任何证书。

## 签名与分发（自己签名）

仓库里**不含任何证书**，任何人都可以用自己的华为账号签名，不用找作者要文件。
按「要装到哪儿」选一档：

### 档 1 ｜只在模拟器 / 自己开了调试的设备上跑 —— 不用签名

```powershell
一键打包.bat harmony -Install        # 未签名 HAP 也能装到模拟器
```

### 档 2 ｜装到自己或同事的真机 —— DevEco 自动签名（约 1 分钟）

1. 用 DevEco Studio 打开 `harmony-app/harmony`
2. `File → Project Structure… → Project → Signing Configs`
   → 勾选 **Automatically generate signature** → `Sign In` 登录华为账号 → `OK`
3. 回仓库根重新打包：

   ```powershell
   一键打包.bat harmony -Install      # 脚本会自动收集签名版 HAP（文件名不带 -unsigned）
   ```

自动签名会把**你连接过的设备 UDID 写进 Profile**，所以：

- 只有这些设备能装；换设备 → 重新点一次自动签名（或在 AGC「设备管理」里加 UDID，单账号上限 **100 台**）
- 别人拿这个 HAP 是**装不上**的 —— 那是调试签名，不是分发签名

### 档 3 ｜给别人装 / 公开发布 —— 发布签名

1. 在 [AGC](https://developer.huawei.com/consumer/cn/) 创建应用（**bundleName 必须改成你自己的**，见下）
2. 申请 **发布证书**（`.cer`，有效期 3 年）和 **发布 Profile**（`.p7b`，约 1 年）
3. DevEco `Signing Configs` 里取消自动签名，手工填 `.p12` / `.cer` / `.p7b`
4. 打包后通过下面任一渠道分发：
   - AGC **邀请测试 / 公开测试**（门槛最低，有用户数上限）
   - 上架 **AppGallery**（需实名 + 应用资质，部分类目要软著）
   - 企业内部分发（需企业开发者账号）

> 证书 / Profile 到期只影响「再签新包」，**已装在设备上的应用照常运行**。

### 建议先改 bundleName

`harmony-app/harmony/AppScope/app.json5`：

```json5
"bundleName": "com.example.attendanceharmony"
```

改成你自己的反向域名（例如 `com.yourname.attendance`）。

- 只是本地调试签名：**不用改**
- 要在 AGC 创建应用 / 上架：**必须改**，`com.example.*` 会和别人冲突
- 改完不用动脚本：`build_hap` / `pack_hap` 都从 `app.json5` 读 bundleName 来安装和启动
- ⚠ 换 bundleName 等于换了应用身份，**已装的旧版本数据不会迁移**

### 签名文件绝对不要入库

`.p12`（私钥）/ `.cer` / `.p7b` / `.csr` 已写进 `.gitignore` —— 私钥泄露等于别人能用你的身份发布应用。
DevEco 自动签名默认把文件放在 `%USERPROFILE%\.ohos\config\`，本来也不在仓库里。

> ⚠ 但 DevEco 会把签名信息写进 **`harmony/build-profile.json5` 的 `signingConfigs`**（含证书的绝对路径）。
> 这个文件是要入库的，所以**提交前请把它还原成**：
>
> ```json5
> "signingConfigs": [],
> ```
>
> 否则会把你的本机路径（甚至加密后的口令串）一起提上去。

### 查证书 / Profile 什么时候过期

```powershell
"D:\DevEco Studio\jbr\bin\keytool.exe" -printcert -file <你的证书>.cer
# 输出里的 Valid from ... until ... 就是有效期

# 验一个已签名的 HAP（签名链、bundleName、证书有效期都能看到）
java -jar "D:\DevEco Studio\sdk\default\openharmony\toolchains\lib\app_check_tool.jar" <签名后的>.hap
```

### 常见现象

| 现象 | 原因 / 处理 |
| --- | --- |
| `signature verify failed` | 用的是**调试签名**，当前设备 UDID 不在 Profile 里 → 重新自动签名或改用发布签名 |
| 装完桌面名字显示 `label` | 覆盖安装没刷新启动器缓存：`hdc uninstall <bundle>` 再装一次 |
| 改了 bundleName 后脚本还装旧包 | 脚本读的是 `app.json5`，确认改的是 `AppScope/app.json5` 并重新构建 |

## 数据与隐私

- 应用数据只存应用沙箱内的 **Preferences**（不写入任何外部目录）：
  - 月份账本 / 参数模板 / 相关单位 / 工作地 / 锁定月份：**明文 JSON**（其它应用读不到）；
  - API 配置（地址 / 模型 / Key）合成单键 `api_config`，其中 **Key 由 HUKS 加密** ——
    `HUKS AES-256-GCM（由系统密钥库托管密钥，不可导出，无密钥文件）`
    （与桌面版同一句式：Windows 是 `Windows DPAPI（由当前用户账户托管密钥，无密钥文件）`；
    HUKS 不可用时降级明文并在界面提示）。
- 这样做的好处：**账本不依赖设备密钥** —— 换机 / 备份恢复后仍能正常打开；
  代价是账本在系统备份里是明文（若需要更强保护，可后续加「备份口令」方案）。
- 导出报表 / 年度 CSV 时由你在系统「另存为」对话框里选择位置。
- 凡是从桌面版真实存档导出的东西**一律不入库**（含真实工资）：
  - `harmony/entry/src/main/resources/rawfile/seed_months.json`（示例月份，`scripts/export_seed.py`）
  - `harmony/entry/src/main/ets/model/demo.data.ts`（`scripts/dump_demo_book.py` 生成的界面核对样例；
    当前代码未引用，按需生成即可，不要提交）
  - `fixtures/baseline.json`（数值对拍基准，`scripts/dump_baseline.py`）

  需要时在自己的机器上生成（脚本只读桌面版存档，不写回）：

  ```powershell
  .venv\Scripts\python.exe harmony-app\scripts\dump_baseline.py   # 生成对拍基准
  npm test                                                        # 现在会跑满 141 例
  ```

  基准缺失时 `tests/parity.test.ts` 会自动 skip 对拍分支（其余用例照常跑）。

## 与桌面版的差异

| 项 | 桌面版 | 鸿蒙版 | 说明 |
|---|---|---|---|
| 界面 | PySide6 / Qt | ArkUI（状态管理 V2） | 布局与文案逐页对齐，宽度自适应规则不同 |
| 存储 | 每月一个**明文** JSON（靠文件权限 0600 保护），仅 API Key 用 `Windows DPAPI（由当前用户账户托管密钥，无密钥文件）` / 信创用 `SM2 + SM4 + HMAC-SM3` | Preferences 一月一键**明文** JSON（应用沙箱），仅 API Key 用 `HUKS AES-256-GCM（由系统密钥库托管密钥，不可导出，无密钥文件）`（`api_config` 单键） | 口径一致：只加密可重建的凭据；账本明文靠系统沙箱隔离，换机 / 备份恢复不会因密钥丢失而解不开 |
| 导出格式 | `.xlsx`（openpyxl） | `.csv`（UTF-8 带 BOM） | **内容结构一致**：标题 / 备注 / 汇总 6 项 / 各核算分组（含合规判定）；CSV 双击即可用 Excel / WPS 打开 |
| 月份跳转 | 点月份按钮弹月历，可直接选任意年月 | `‹ 上月` / `下月 ›`，或用左侧「历史月份」列表跳转 | ArkUI 没有内置月历控件；历史月份列表同样可以直接点进去 |
| 平台 | Windows / Linux | HarmonyOS PC（2in1） | — |

核算公式、最低工资数据表、节假日表、工资项目录、报表分组**与桌面版完全一致**
（`tests/parity.test.ts` 用桌面版真实账本做了 54 例逐字段对拍）；另外 `tests/` 里还有 87 个纯逻辑用例。

> ⚠ 两端**不能直接互换存档**：字段结构同构（`MonthBook.to_dict()`），但桌面版是每月独立 JSON 文件，
> 鸿蒙版是 Preferences 键值库 —— 装载方式不同，只能在各自的设备上录入。

## 许可证

与仓库根目录一致：GNU GPL v3。
