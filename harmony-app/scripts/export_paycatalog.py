"""从桌面版 app/model.py 导出「添加工资项」预设目录 → core/paycatalog.ts

原则：**不手抄**。改目录请改桌面版再重跑本脚本。

用法（在仓库根的 venv 里跑，不需要传参）：
    python harmony-app/scripts/export_paycatalog.py
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent            # harmony-app/
DESKTOP = ROOT.parent         # 仓库根：桌面版 Python 代码在 DESKTOP/app/
if not (DESKTOP / "app" / "config.py").exists():
    raise SystemExit(
        "[ERROR] 找不到桌面版代码：%s\n"
        "        本脚本必须在完整仓库里运行（app/ 与 harmony-app/ 同级）。"
        % (DESKTOP / "app")
    )
OUT = ROOT / "core" / "paycatalog.ts"

sys.path.insert(0, str(DESKTOP))

from app import model  # noqa: E402

GROUPS = [
    ("wage", "PAYITEM_CATALOG_WAGE", "计入最低工资标准的工资"),
    ("subsidy", "PAYITEM_CATALOG_SUBSIDY", "公司补贴"),
    ("fixed_allow", "PAYITEM_CATALOG_FIXED", "固定津贴"),
    ("perday_allow", "PAYITEM_CATALOG_PERDAY", "按出勤津贴"),
]


def ts_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> int:
    catalog = model.PAYITEM_CATALOG
    lines: list[str] = []
    lines.append("/**")
    lines.append(" * 「添加工资项」预设目录（按工资项类型分组）。")
    lines.append(" *")
    lines.append(" * ⚠ 由 scripts/export_paycatalog.py 从桌面版 app/model.py 自动生成，**不要手改**。")
    lines.append(" */")
    lines.append("")

    total = 0
    for key, const, _title in GROUPS:
        items = list(catalog.get(key, []))
        total += len(items)
        lines.append(f"/** {_title}（{len(items)} 项） */")
        lines.append(f"export const {const}: string[] = [")
        for n in items:
            lines.append(f"  {ts_str(n)},")
        lines.append("];")
        lines.append("")

    # 分类标题 + 类型 key，供 UI 直接遍历
    lines.append("export class PayCatalogGroup {")
    lines.append("  type: string;")
    lines.append("  title: string;")
    lines.append("  items: string[];")
    lines.append("")
    lines.append("  constructor(type: string, title: string, items: string[]) {")
    lines.append("    this.type = type;")
    lines.append("    this.title = title;")
    lines.append("    this.items = items;")
    lines.append("  }")
    lines.append("}")
    lines.append("")
    lines.append("/** 菜单分组（顺序与桌面版一致）。 */")
    lines.append("export const PAYITEM_GROUPS: PayCatalogGroup[] = [")
    for key, const, title in GROUPS:
        lines.append(f"  new PayCatalogGroup('{key}', '{title}', {const}),")
    lines.append("];")
    lines.append("")
    lines.append("/** 新增项时各类的默认名称（桌面版同源）。 */")
    lines.append("export const PAYITEM_DEFAULT_NAME: Map<string, string> = new Map<string, string>([")
    for key in ["wage", "subsidy", "fixed_allow", "perday_allow"]:
        lines.append(f"  ['{key}', {ts_str(model.PAYITEM_DEFAULT_NAME[key])}],")
    lines.append("]);")
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] 4 组 / {total} 项 → {OUT}")
    for key, _c, title in GROUPS:
        print(f"  {title}: {len(catalog.get(key, []))} 项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
