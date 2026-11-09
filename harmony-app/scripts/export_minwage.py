"""从桌面版 app/wages.py 导出最低工资表 → core/minwage.data.ts

原则：**不手抄**。数据只有一个源头（桌面版 Python），改数据只改那边再重跑本脚本。

用法（在仓库根的 venv 里跑，不需要传参）：
    python harmony-app/scripts/export_minwage.py

只读导入 app.wages，不写任何桌面项目文件。
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent            # harmony-app/
DESKTOP = ROOT.parent         # 仓库根：桌面版 Python 代码在 DESKTOP/app/
if not (DESKTOP / "app" / "wages.py").exists():
    raise SystemExit(
        "[ERROR] 找不到桌面版代码：%s\n"
        "        本脚本必须在完整仓库里运行（app/ 与 harmony-app/ 同级）。"
        % (DESKTOP / "app")
    )
OUT = ROOT / "core" / "minwage.data.ts"

sys.path.insert(0, str(DESKTOP))

from app import wages  # noqa: E402


def ts_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> int:
    provinces = list(wages.PROVINCES)
    rows: list[tuple[str, str, float, float]] = []
    for p in provinces:
        for city in wages.get_regions(p):
            got = wages.get(p, city)
            if got is None:
                continue
            month, hour = got
            rows.append((p, city, float(month), float(hour)))

    lines: list[str] = []
    lines.append("/**")
    lines.append(" * 最低工资标准表（月最低工资 / 非全日制小时最低工资）。")
    lines.append(" *")
    lines.append(" * ⚠ 本文件由 scripts/export_minwage.py 从桌面版 app/wages.py 自动生成，")
    lines.append(" *   **不要手改**：改数据请改桌面版再重跑脚本，否则两边会不一致。")
    lines.append(" */")
    lines.append("")
    lines.append("export class MinWageRow {")
    lines.append("  province: string;")
    lines.append("  region: string;")
    lines.append("  month: number;")
    lines.append("  hour: number;")
    lines.append("")
    lines.append("  constructor(province: string, region: string, month: number, hour: number) {")
    lines.append("    this.province = province;")
    lines.append("    this.region = region;")
    lines.append("    this.month = month;")
    lines.append("    this.hour = hour;")
    lines.append("  }")
    lines.append("}")
    lines.append("")
    lines.append("/** 省份显示顺序（常用省在前，与桌面版一致）。 */")
    lines.append("export const MIN_WAGE_PROVINCES: string[] = [")
    for p in provinces:
        lines.append(f"  {ts_str(p)},")
    lines.append("];")
    lines.append("")
    lines.append("/** 全部地区（顺序：省份顺序 + 省内原顺序）。 */")
    lines.append("export const MIN_WAGE_ROWS: MinWageRow[] = [")
    for p, city, month, hour in rows:
        lines.append(f"  new MinWageRow({ts_str(p)}, {ts_str(city)}, {month!r}, {hour!r}),")
    lines.append("];")
    lines.append("")
    lines.append("/** 省份 → 该省地区（保序）；模块级建一次，查询 O(1)。 */")
    lines.append("const BY_PROVINCE: Map<string, string[]> = (() => {")
    lines.append("  const m: Map<string, string[]> = new Map<string, string[]>();")
    lines.append("  for (const r of MIN_WAGE_ROWS) {")
    lines.append("    const arr: string[] | undefined = m.get(r.province);")
    lines.append("    if (arr === undefined) {")
    lines.append("      m.set(r.province, [r.region]);")
    lines.append("    } else {")
    lines.append("      arr.push(r.region);")
    lines.append("    }")
    lines.append("  }")
    lines.append("  return m;")
    lines.append("})();")
    lines.append("")
    lines.append("/** `${省}/${地区}` → 标准行；模块级建一次，查询 O(1)。 */")
    lines.append("const BY_REGION: Map<string, MinWageRow> = (() => {")
    lines.append("  const m: Map<string, MinWageRow> = new Map<string, MinWageRow>();")
    lines.append("  for (const r of MIN_WAGE_ROWS) {")
    lines.append("    m.set(`${r.province}/${r.region}`, r);")
    lines.append("  }")
    lines.append("  return m;")
    lines.append("})();")
    lines.append("")
    lines.append("/** 某省下的地区名（保序；返回的是只读共享数组，调用方不要原地改）。 */")
    lines.append("export function minWageRegions(province: string): string[] {")
    lines.append("  return BY_PROVINCE.get(province) ?? [];")
    lines.append("}")
    lines.append("")
    lines.append("/** 查某省某地区的标准；查不到返回 null（**不静默替换成别的城市**）。 */")
    lines.append("export function minWageOf(province: string, region: string): MinWageRow | null {")
    lines.append("  return BY_REGION.get(`${province}/${region}`) ?? null;")
    lines.append("}")
    lines.append("")
    lines.append("/** 全省第一个地区（“全省未细分”场景，与桌面版 get(p) 行为一致）。 */")
    lines.append("export function minWageFirst(province: string): MinWageRow | null {")
    lines.append("  const regions: string[] | undefined = BY_PROVINCE.get(province);")
    lines.append("  if (regions === undefined || regions.length === 0) {")
    lines.append("    return null;")
    lines.append("  }")
    lines.append("  return BY_REGION.get(`${province}/${regions[0]}`) ?? null;")
    lines.append("}")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"省份 {len(provinces)} 个，地区 {len(rows)} 条 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
