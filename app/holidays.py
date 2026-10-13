"""中国法定节假日 / 调休数据表（用于一键铺考勤与加班小时自动分桶）。

数据来源：国务院办公厅历年"部分节假日安排的通知"。
  2026：国办发明电〔2025〕7号（2025-11-04 发布）
  2025：国办发明电〔2024〕7号
kind 取值：
  statutory  法定节假日当天（加班 ×3，计入"提供正常劳动"）
  rest       放假调休区间（含法定日与拼假休息日）
  makeup     调休补班日（周末但需上班）
2027 年及以后的安排官方通常在上一年的 11 月左右发布，发布后在此补充即可。
"""
from __future__ import annotations

from datetime import date, timedelta

# 每年：法定日 / 放假区间（含法定日）/ 补班日（MM-DD）
_YEAR_DATA: dict[int, dict[str, list]] = {
    2026: {
        "statutory": ["01-01",
                      "02-16", "02-17", "02-18", "02-19",
                      "04-05",
                      "05-01", "05-02",
                      "06-19",
                      "09-25",
                      "10-01", "10-02", "10-03"],
        "ranges": [("01-01", "01-03"),
                   ("02-15", "02-23"),
                   ("04-04", "04-06"),
                   ("05-01", "05-05"),
                   ("06-19", "06-21"),
                   ("09-25", "09-27"),
                   ("10-01", "10-07")],
        "makeup": ["01-04", "02-14", "02-28", "05-09", "09-20", "10-10"],
    },
    2025: {
        "statutory": ["01-01",
                      "01-28", "01-29", "01-30", "01-31",
                      "04-04",
                      "05-01", "05-02",
                      "05-31",
                      "10-01", "10-02", "10-03", "10-06"],
        "ranges": [("01-01", "01-01"),
                   ("01-28", "02-04"),
                   ("04-04", "04-06"),
                   ("05-01", "05-05"),
                   ("05-31", "06-02"),
                   ("10-01", "10-08")],
        "makeup": ["01-26", "02-08", "04-27", "09-28", "10-11"],
    },
}

_cache: dict[int, dict[str, set[str]]] = {}


def year_sets(year: int) -> dict[str, set[str]] | None:
    """展开某年的 {statutory/rest/makeup: "MM-DD" 集合}，未收录返回 None。

    公开 API：``wages._holidays_from_local`` 与 ``pages_calendar._apply_holidays``
    都要拿这份原始集合（前者要与 API 返回同构，后者要做差异核对）。
    """
    if year in _cache:
        return _cache[year]
    data = _YEAR_DATA.get(year)
    if data is None:
        _cache[year] = None  # type: ignore[assignment]
        return None
    statutory = set(data["statutory"])
    makeup = set(data["makeup"])
    rest: set[str] = set(statutory)
    for start, end in data["ranges"]:
        d = date.fromisoformat(f"{year}-{start}")
        stop = date.fromisoformat(f"{year}-{end}")
        while d <= stop:
            rest.add(d.strftime("%m-%d"))
            d += timedelta(days=1)
    out = {"statutory": statutory, "rest": rest, "makeup": makeup}
    _cache[year] = out
    return out


def has_year(year: int) -> bool:
    """该年节假日安排是否已收录。"""
    return year in _YEAR_DATA


def classify_day(key: str, *, statutory: set[str], rest: set[str],
                 makeup: set[str]) -> str | None:
    """把某个 "MM-DD" 归类为 ``statutory`` / ``rest`` / ``makeup``；普通日返回 None。

    ⚠ **优先级全项目只有这一处**（法定 → 补班 → 放假），参数限定关键字传参，
    避免调用方把 rest / makeup 写反。

    为什么必须只有一份：正常数据里三者互斥，但联网查回来的数据是模型生成的，
    真会把同一天既列进放假区间又列进补班日 —— 两条链路（内置官方表 / API）
    必须给出同一个答案，否则同一天在不同入口会铺成两种结果。
    """
    if key in statutory:
        return "statutory"
    if key in makeup:
        return "makeup"
    if key in rest:
        return "rest"
    return None


def day_kind(year: int, month: int, day: int) -> str | None:
    """返回某天类型：statutory / rest / makeup；未收录或普通日返回 None。"""
    sets = year_sets(year)
    if sets is None:
        return None
    return classify_day(f"{month:02d}-{day:02d}", statutory=sets["statutory"],
                        rest=sets["rest"], makeup=sets["makeup"])
