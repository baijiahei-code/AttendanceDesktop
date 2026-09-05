"""小组件目录：统一卡片 / 工资项 / 加班 / 扣除 / strip。

* :class:`Card`                    —— 统一卡片框架（5 种 variant + 锁定机制）
* :class:`PayItemRow`              —— 工资项单行
* :class:`PayItemCatalogMenu`      —— 添加菜单（包含二级菜单）
* :class:`PayItemListWidget`       —— 工资项列表容器（标题/列头/空提示）
* :class:`SalaryStripWidget`       —— 顶部 4 列金额 strip
* :class:`OvertimeCardWidget`      —— 加班工资卡片
* :class:`DeductionCardWidget`     —— 个人扣除卡片
"""
from .card import Card
from .pay_item_row import PayItemRow
from .pay_item_menu import PayItemCatalogMenu
from .pay_item_list import PayItemListWidget
from .salary_strip import SalaryStripWidget
from .overtime_card import OvertimeCardWidget
from .deduction_card import DeductionCardWidget

__all__ = [
    "Card",
    "PayItemRow",
    "PayItemCatalogMenu",
    "PayItemListWidget",
    "SalaryStripWidget",
    "OvertimeCardWidget",
    "DeductionCardWidget",
]
