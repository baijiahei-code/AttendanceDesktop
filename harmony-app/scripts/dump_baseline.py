"""生成数值对拍基准（桌面版 Python 侧）。

用法（**在仓库根目录、用桌面版的 venv 跑**）：
  .venv\\Scripts\\python.exe harmony-app\\scripts\\dump_baseline.py

产出 `fixtures/baseline.json`：
  { "cases": [ { "name": ..., "input": <MonthBook.to_dict()>, "expected": <calc.compute 结果> } ] }

其中 `input` 是**桌面版自己序列化出来的**账本，TS 侧只要 `MonthBook.fromDict(input)`
再 `compute()`，两边结果必须逐字段一致。

⚠ 产出的基准含真实工资数据，**不入库**（`.gitignore` 已排除）；换成自己的数据请重新生成。

本脚本**只读**桌面版存档（导入 app.model / app.calc），不写任何东西回去。
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent            # harmony-app/
DESKTOP = ROOT.parent         # 仓库根：桌面版 Python 代码在 DESKTOP/app/
if not (DESKTOP / "app" / "calc.py").exists():
    raise SystemExit(
        "[ERROR] 找不到桌面版代码：%s\n"
        "        本脚本必须在完整仓库里运行（app/ 与 harmony-app/ 同级）。"
        % (DESKTOP / "app")
    )

sys.path.insert(0, str(DESKTOP))

from app import calc, model  # noqa: E402  （必须先插路径再导入）


def book_cases(book: model.MonthBook, name: str) -> list[dict]:
    """以一本书为基底，派生若干「刁钻组合」变体。"""
    out: list[dict] = []

    def emit(tag: str, b: model.MonthBook) -> None:
        out.append({
            "name": f"{name}/{tag}",
            "input": b.to_dict(),
            "expected": dataclasses.asdict(calc.compute(b)),
        })

    emit("base", book)

    b = copy.deepcopy(book)
    b.agreed_work_days = 0          # 日薪/时薪不折算（历史上的除零坑）
    emit("agreed0", b)

    b = copy.deepcopy(book)
    b.hours_per_day = 0             # 公司每小时成本分母为 0
    emit("hours0", b)

    b = copy.deepcopy(book)
    b.income_tax_auto = True        # 个税走预扣率表
    emit("tax_auto", b)

    b = copy.deepcopy(book)
    for d in b.days[:3]:
        d.mark = 1                  # 法定节假日
    for d in b.days[3:6]:
        d.mark = 2                  # 其他视为提供正常劳动
    emit("marks", b)

    b = copy.deepcopy(book)
    for d in b.days[:8]:
        d.overtime_hours = 5.0      # 单日加班 > 3h → 违法明细
    for d in b.days[8:11]:
        d.leave_hours = 2.0
    emit("overtime_leave", b)

    b = copy.deepcopy(book)
    b.pay_items = []                # 没有工资项
    emit("no_pay_items", b)

    b = copy.deepcopy(book)
    b.min_wage = 999999             # 必然低于最低工资
    b.parttime_min = 999999
    emit("min_wage_high", b)

    b = copy.deepcopy(book)
    b.locked = True
    b.fixed_overtime_wage = 540.0
    b.workday_ot_hours = 10.0
    b.restday_ot_hours = 8.0
    b.holiday_ot_hours = 3.5
    emit("ot_manual", b)

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="生成数值对拍基准（只读桌面版仓库）")
    ap.add_argument("--data-dir", default=os.path.join(
        os.environ.get("LOCALAPPDATA", str(Path.home())), "工作考勤表", "data"),
        help="桌面版存档目录（默认 %%LOCALAPPDATA%%\\工作考勤表\\data）")
    ap.add_argument("--out", default=str(ROOT / "fixtures" / "baseline.json"))
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    files = sorted(p for p in data_dir.glob("*.json")
                   if p.name[:4].isdigit() and p.name[4:5] == "-")
    if not files:
        print(f"[错] 存档目录里没有 YYYY-MM.json：{data_dir}")
        return 1

    cases: list[dict] = []
    for p in files:
        raw = json.loads(p.read_text(encoding="utf-8"))
        book = model.MonthBook.from_dict(raw)
        cases.extend(book_cases(book, p.stem))
        print(f"  {p.name}: {book.year}-{book.month:02d}  {len(book.days)} 天  "
              f"{len(book.pay_items)} 个工资项")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {len(cases)} 个用例 → {out} ({out.stat().st_size:,} 字节)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
