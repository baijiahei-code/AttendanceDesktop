"""内置最低工资表更新/核对工具。

用途：把「人社部《全国各省、自治区、直辖市最低工资标准情况》」的最新一期
拉下来，与 `app/wages.py` 内置表逐省比对，直接告出：
  * 哪些省的数字变了（并列出官方新值）
  * 哪些城市用的值**不在**官方档位里（映射写错 / 过期）
  * 官方有、内置没用的档位（如只列到第 3 档、第 4 档仅适用部分县）

用法：
    python scripts/update_minwage.py              # 自动抓最新一期（走人社部 IP 镜像）
    python scripts/update_minwage.py --file x.html  # 用本地保存的页面（离线/可复现）
    python scripts/update_minwage.py --list        # 只列出镜像上各期文章

退出码：0 = 内置表与官方一致；1 = 有差异（或抓取失败）。

数据来源说明（2026-10-07 实测）：
  www.mohrss.gov.cn 有 WAF，urllib 抓到的是 JS 壳；同一台服务器的
  **IP 镜像** http://114.255.111.180/ 可直接抓，栏目「劳动关系 > 服务园地」
  （/SYrlzyhshbzb/laodongguanxi_/fwyd/）按季度发布该表。
"""
from __future__ import annotations

import re
import sys
import urllib.request
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import wages  # noqa: E402

MIRROR_INDEX = ("http://114.255.111.180/SYrlzyhshbzb/laodongguanxi_/fwyd/")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
# 官方表里省名可能写成 "北 京"，也可能出现 "其中：深圳" 这类子行
_PROV_ALIAS = {"内蒙": "内蒙古"}


def fetch(url: str, timeout: int = 30) -> str:
    """抓页面并解码（utf-8 → gb18030 兜底）。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = r.headers.get_content_charset()
    if enc:
        return raw.decode(enc, "replace")
    for e in ("utf-8", "gb18030"):
        try:
            return raw.decode(e)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def latest_issue_url(index_html: str, base: str = MIRROR_INDEX) -> tuple[str, str]:
    """从栏目页里挑出最新一期「最低工资标准情况」文章，返回 (标题, 绝对URL)。"""
    best: tuple[str, str] | None = None
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', index_html, re.S | re.I):
        href = m.group(1)
        title = unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if "最低工资" not in title:
            continue
        stamp = re.search(r"t(\d{8})_", href)
        key = stamp.group(1) if stamp else "0"
        if best is None or key > best[0]:
            best = (key, f"{base.rstrip('/')}/{href.lstrip('./')}", title)  # type: ignore[assignment]
    if best is None:
        raise SystemExit("栏目页里没找到「最低工资标准情况」文章，请手工确认镜像地址")
    return best[2], best[1]  # type: ignore[return-value]


def parse_table(html: str) -> dict[str, list[tuple[float, float]]]:
    """解析官方表 → {省: [(月, 时), ...] 按档位从高到低}；「其中：深圳」并入广东。"""
    table = None
    for tb in re.findall(r"<table[^>]*>(.*?)</table>", html, re.S | re.I):
        if "最低工资标准" in tb:
            table = tb
            break
    if table is None:
        raise SystemExit("页面里没找到最低工资表（是不是抓到 JS 壳了？试试 --file）")

    out: dict[str, list[tuple[float, float]]] = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S | re.I):
        cells = [re.sub(r"[\s\xa0]+", "", unescape(re.sub(r"<[^>]+>", "", c)))
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if len(cells) < 9:
            continue
        name = cells[0]
        if name in ("地区", "第一档") or not name:
            continue
        months = [c for c in cells[1:5] if c]
        hours = [c for c in cells[5:9] if c]
        if not months or not hours:
            continue
        pairs: list[tuple[float, float]] = []
        for m, h in zip(months, hours):
            try:
                pairs.append((float(m), float(h)))
            except ValueError:
                pairs = []
                break
        if not pairs:
            continue
        if name.startswith("其中"):
            target = "广东" if "深圳" in name else None
            if target and target in out:
                out[target] = pairs + out[target]      # 深圳单列，放最前
            continue
        out[_PROV_ALIAS.get(name, name)] = pairs
    return out


def compare(official: dict[str, list[tuple[float, float]]]) -> list[str]:
    """与内置表比对，返回人类可读的问题清单（空 = 一致）。"""
    issues: list[str] = []
    for prov in wages.PROVINCES:
        off = official.get(prov)
        if not off:
            issues.append(f"[缺] {prov}：官方表里没解析到（省名写法变了？）")
            continue
        off_set = {p for p in off}
        used: dict[tuple[float, float], list[str]] = {}
        for city, val in wages._REGION_DATA.get(prov, {}).items():  # type: ignore[attr-defined]
            used.setdefault((float(val[0]), float(val[1])), []).append(city)
        bad = {v: cs for v, cs in used.items() if v not in off_set}
        unused = [p for p in off if p not in used]
        if bad:
            for v, cs in sorted(bad.items(), reverse=True):
                issues.append(
                    f"[错] {prov}：{'、'.join(cs[:6])}{'…' if len(cs) > 6 else ''} "
                    f"用的是 月 {v[0]:g} / 时 {v[1]:g}，不在官方档位 "
                    f"{'、'.join(f'{m:g}/{h:g}' for m, h in off)} 里")
        if unused:
            issues.append(f"[注] {prov}：官方还有未使用的档位 "
                          f"{'、'.join(f'{m:g}/{h:g}' for m, h in unused)}"
                          f"（通常只适用部分县，内置表按地级市取高档）")
    return issues


def diff_summary(official: dict[str, list[tuple[float, float]]]) -> list[str]:
    """列出官方各档数值，便于人工核对/抄写。"""
    lines = []
    for prov in wages.PROVINCES:
        off = official.get(prov)
        if off:
            lines.append(f"{prov:<4} " + "  ".join(f"{m:g}/{h:g}" for m, h in off))
    return lines


def main(argv: list[str]) -> int:
    if "--file" in argv:
        path = Path(argv[argv.index("--file") + 1])
        html = path.read_text(encoding="utf-8")
        src = str(path)
    else:
        index = fetch(MIRROR_INDEX)
        if "--list" in argv:
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                                 index, re.S | re.I):
                title = unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
                if "最低工资" in title:
                    print(f"  {title}\n    {MIRROR_INDEX.rstrip('/')}/"
                          f"{m.group(1).lstrip('./')}")
            return 0
        title, url = latest_issue_url(index)
        print(f"最新一期：{title}\n  {url}")
        html = fetch(url)
        src = url

    official = parse_table(html)
    print(f"解析到 {len(official)} 个省级单位：{src}\n")
    print("官方各档（月/时）：")
    for line in diff_summary(official):
        print("  " + line)
    print("\n与内置表比对：")
    issues = compare(official)
    if not issues:
        print("  ✅ 一致：每个城市用的数值都等于官方档位之一")
        return 0
    hard = [s for s in issues if s.startswith(("[错]", "[缺]"))]
    for s in issues:
        print("  " + s)
    print(f"\n共 {len(hard)} 处需要修正（另有 {len(issues) - len(hard)} 条提示）")
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
