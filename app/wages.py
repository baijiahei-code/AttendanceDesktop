"""全国最低工资标准（省 → 地级市 二级结构）。
数据来源：人力资源社会保障部《全国各省、自治区、直辖市最低工资标准情况
（截至 2026 年 1 月 1 日）》，并逐条对照各省人民政府/人社厅的调整通知。
同档城市共用同一标准，但每个地级市作为独立选项出现在下拉中，方便精确选择。
未收录返回 None；如需更新请查当地人社厅最新通知。

== 修改某省数值的方法 ======================================================
每个省在下方都有独立的数据块，结构完全一致：
    _XX_GRADE1 = (月最低工资, 非全日制小时最低工资)   # 一行一个档位
    _CITY_XX_1 = ("城市A", "城市B", ...)            # 该档覆盖的地区
    ...
    _XX_DATA: dict[str, tuple[float, float]] = {}
    for _city in _CITY_XX_1:
        _XX_DATA[_city] = _XX_GRADE1

想改标准数值 → 直接改该省 _XX_GRADEn 的元组
想改城市属哪一档 → 把市名在 _CITY_XX_n 元组之间移动
===========================================================================
"""
from __future__ import annotations

import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.request


# =======================================================================
# 数据来源：人力资源社会保障部《全国各省、自治区、直辖市最低工资标准情况
#           （截至 2026 年 1 月 1 日）》+ 各省人民政府/人社厅调整通知。
# 更新方式：改某省 _XX_GRADEn 的元组即可；城市属哪一档改 for 循环。
# =======================================================================

# =======================================================================
# 北京：1 档
# 依据：北京市人社局通知（2025-09-01 起执行）
# =======================================================================
_BJ_GRADE1 = (2540.0, 27.7)
_CITY_BJ_1 = ('全市统一',)
#   ↑ 第 1 档（月 2540 / 时 27.7）：全市统一
_BJ_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_BJ_1:
    _BJ_DATA[_city] = _BJ_GRADE1


# =======================================================================
# 上海：1 档
# 依据：沪人社规〔2025〕…（2025-07-01 起执行，单档）
# =======================================================================
_SH_GRADE1 = (2740.0, 25.0)
_CITY_SH_1 = ('全市统一',)
#   ↑ 第 1 档（月 2740 / 时 25.0）：全市统一
_SH_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_SH_1:
    _SH_DATA[_city] = _SH_GRADE1


# =======================================================================
# 广东：5 档
# 依据：粤府函（深圳单列 2520/23.7；其余 4 档）
# =======================================================================
_GD_GRADE1 = (2520.0, 23.7)
_CITY_GD_1 = ('深圳',)
#   ↑ 第 1 档（月 2520 / 时 23.7）：深圳
_GD_GRADE2 = (2500.0, 23.7)
_CITY_GD_2 = ('广州', '珠海', '佛山', '东莞', '中山',)
#   ↑ 第 2 档（月 2500 / 时 23.7）：广州、珠海、佛山、东莞、中山
_GD_GRADE2 = (2500.0, 23.7)
_CITY_GD_2 = ('广州',)
#   ↑ 一类（月 2500 / 时 23.7）：广州（深圳单列 2520）
_GD_GRADE3 = (2080.0, 19.8)
_CITY_GD_3 = ('珠海', '佛山', '东莞', '中山',)
#   ↑ 二类（月 2080 / 时 19.8）：珠海、佛山、东莞、中山
_GD_GRADE4 = (1850.0, 18.3)
_CITY_GD_4 = ('汕头', '惠州', '江门', '湛江', '肇庆',)
#   ↑ 三类（月 1850 / 时 18.3）：汕头、惠州、江门、湛江、肇庆
_GD_GRADE5 = (1750.0, 17.4)
_CITY_GD_5 = ('韶关', '茂名', '清远', '梅州', '汕尾', '河源', '阳江', '潮州', '揭阳', '云浮',)
#   ↑ 四类（月 1750 / 时 17.4）：韶关、茂名、清远、梅州、汕尾、河源、阳江、潮州、揭阳、云浮
_GD_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_GD_1:
    _GD_DATA[_city] = _GD_GRADE1
for _city in _CITY_GD_2:
    _GD_DATA[_city] = _GD_GRADE2
for _city in _CITY_GD_3:
    _GD_DATA[_city] = _GD_GRADE3
for _city in _CITY_GD_4:
    _GD_DATA[_city] = _GD_GRADE4
for _city in _CITY_GD_5:
    _GD_DATA[_city] = _GD_GRADE5


# =======================================================================
# 江苏：3 档
# 依据：苏人社发（2026-01-01 起执行，3 档）
# =======================================================================
_JS_GRADE1 = (2660.0, 25.0)
_CITY_JS_1 = ('南京', '苏州', '无锡', '常州', '镇江',)
#   ↑ 第 1 档（月 2660 / 时 25.0）：南京、苏州、无锡、常州、镇江
_JS_GRADE2 = (2430.0, 23.0)
_CITY_JS_2 = ('徐州', '南通', '连云港', '淮安', '盐城', '扬州', '泰州',)
#   ↑ 第 2 档（月 2430 / 时 23.0）：徐州、南通、连云港、淮安、盐城、扬州、泰州
_JS_GRADE3 = (2180.0, 21.0)
_CITY_JS_3 = ('宿迁',)
#   ↑ 第 3 档（月 2180 / 时 21.0）：宿迁
_JS_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_JS_1:
    _JS_DATA[_city] = _JS_GRADE1
for _city in _CITY_JS_2:
    _JS_DATA[_city] = _JS_GRADE2
for _city in _CITY_JS_3:
    _JS_DATA[_city] = _JS_GRADE3


# =======================================================================
# 浙江：3 档（省定三档 2660/2430/2180，由各设区市选择确定后公布）
# 依据：浙政发〔2025〕23号（2026-01-01 起）；各市 2026 年通知：
#   杭州/宁波/温州=2660，嘉兴/湖州/绍兴/金华/舟山/台州=2430，衢州/丽水=2180
# =======================================================================
_ZJ_GRADE1 = (2660.0, 25.0)
_CITY_ZJ_1 = ('杭州', '宁波', '温州',)
#   ↑ 第 1 档（月 2660 / 时 25.0）：杭州（市区）、宁波（海曙/江北/镇海/北仑/鄢州/奉化）、温州（市区）
_ZJ_GRADE2 = (2430.0, 23.0)
_CITY_ZJ_2 = ('嘉兴', '湖州', '绍兴', '金华', '舟山', '台州',)
#   ↑ 第 2 档（月 2430 / 时 23.0）：嘉兴、湖州、绍兴、金华（市区/义乌等）、舟山、台州
_ZJ_GRADE3 = (2180.0, 21.0)
_CITY_ZJ_3 = ('衢州', '丽水',)
#   ↑ 第 3 档（月 2180 / 时 21.0）：衢州、丽水（均为全市统一）
_ZJ_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_ZJ_1:
    _ZJ_DATA[_city] = _ZJ_GRADE1
for _city in _CITY_ZJ_2:
    _ZJ_DATA[_city] = _ZJ_GRADE2
for _city in _CITY_ZJ_3:
    _ZJ_DATA[_city] = _ZJ_GRADE3


# =======================================================================
# 天津：1 档
# 依据：天津市人社局通知（单档）
# =======================================================================
_TJ_GRADE1 = (2510.0, 26.6)
_CITY_TJ_1 = ('和平区', '河东区', '河西区', '南开区', '河北区', '红桥区', '东丽区', '西青区', '津南区', '北辰区', '武清区', '宝坻区', '滨海新区', '宁河区', '静海区', '蓟州区',)
#   ↑ 第 1 档（月 2510 / 时 26.6）：和平区、河东区、河西区、南开区、河北区、红桥区、东丽区、西青区、津南区、北辰区、武清区、宝坻区、滨海新区、宁河区、静海区、蓟州区
_TJ_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_TJ_1:
    _TJ_DATA[_city] = _TJ_GRADE1


# =======================================================================
# 重庆：2 档
# 依据：渝人社发〔2024〕22号（2025-01-01 起执行）：
#   一类行政区域 2330/23 = 万州、黔江、涪陵、渝中、大渡口、江北、沙坪坝、九龙坡、南岸、北碚、渝北、
#     巴南、长寿、江津、合川、永川、南川、綦江、大足、璧山、铜梁、潼南、荣昌、开州、梁平、武隆
#     （以及两江新区、西部科学城重庆高新区、万盛经开区）；
#   二类行政区域 2200/22 = 城口、丰都、垫江、忠县、云阳、奉节、巫山、巫溪、石柱、秀山、酉阳、彭水
# =======================================================================
_CQ_GRADE1 = (2330.0, 23.0)
_CITY_CQ_1 = ('渝中区', '大渡口区', '江北区', '沙坪坝区', '九龙坡区', '南岸区', '北碚区', '渝北区',
              '巴南区', '万州区', '涪陵区', '长寿区', '江津区', '合川区', '永川区', '璧山区',
              '黔江区', '南川区', '开州区', '梁平区', '武隆区',)
#   ↑ 一档（月 2330 / 时 23.0）：中心城区 + 主城新区（万州、黔江、涪陵、长寿、江津、合川、永川、
#     璧山、南川、开州、梁平、武隆 等）
_CQ_GRADE2 = (2200.0, 22.0)
_CITY_CQ_2 = ('城口县', '丰都县', '垫江县', '忠县', '云阳县', '奉节县', '巫山县', '巫溪县',
              '石柱县', '秀山县', '酉阳县', '彭水县',)
#   ↑ 二档（月 2200 / 时 22.0）：城口、丰都、垫江、忠县、云阳、奉节、巫山、巫溪、石柱、秀山、酉阳、彭水
_CQ_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_CQ_1:
    _CQ_DATA[_city] = _CQ_GRADE1
for _city in _CITY_CQ_2:
    _CQ_DATA[_city] = _CQ_GRADE2


# =======================================================================
# 四川：2 档
# 依据：川府规〔2024〕4号（2025-01-01 起执行，2 档；各市州自行选择档次后公布）：
#   一档 2330/23 = 成都（市区）、攀枝花（攀府规〔2025〕3号）；
#   二档 2200/22 = 其余市州（已逐个核实：自贡、泸州、德阳、绵阳、广元、遂宁、南充、宜宾、
#     达州、内江、眉山、巴中、资阳、乐山、雅安、阿坝、凉山、甘孜（州府康定）；
#     注：甘孜的色达/石渠/理塘/稻城四县执一档 2330；成都的简阳/都江堰等县市执 2200）
# =======================================================================
_SC_GRADE1 = (2330.0, 23.0)
_CITY_SC_1 = ('成都', '攀枝花',)
#   ↑ 一档（月 2330 / 时 23.0）：成都、攀枝花
_SC_GRADE2 = (2200.0, 22.0)
_CITY_SC_2 = ('自贡', '泸州', '德阳', '绵阳', '广元', '乐山', '南充', '宜宾', '达州',
              '内江', '雅安', '巴中', '资阳', '眉山', '遂宁', '甘孜', '阿坝', '凉山',)
#   ↑ 二档（月 2200 / 时 22.0）：自贡、泸州、德阳、绵阳、广元、乐山、南充、宜宾、达州、
#     内江、雅安、巴中、资阳、眉山、遂宁、甘孜、阿坝、凉山
_SC_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_SC_1:
    _SC_DATA[_city] = _SC_GRADE1
for _city in _CITY_SC_2:
    _SC_DATA[_city] = _SC_GRADE2


# =======================================================================
# 山东：3 档
# 依据：鲁政字（3 档）
# =======================================================================
_SD_GRADE1 = (2400.0, 24.0)
_CITY_SD_1 = ('济南', '青岛', '淄博', '东营', '烟台', '潍坊', '威海',)
#   ↑ 第 1 档（月 2400 / 时 24.0）：济南、青岛、淄博、东营、烟台、潍坊、威海
_SD_GRADE2 = (2210.0, 22.0)
_CITY_SD_2 = ('枣庄', '济宁', '泰安', '日照', '临沂', '德州', '聊城', '滨州',)
#   ↑ 第 2 档（月 2210 / 时 22.0）：枣庄、济宁、泰安、日照、临沂、德州、聊城、滨州
_SD_GRADE3 = (2020.0, 20.0)
_CITY_SD_3 = ('菏泽',)
#   ↑ 第 3 档（月 2020 / 时 20.0）：菏泽
_SD_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_SD_1:
    _SD_DATA[_city] = _SD_GRADE1
for _city in _CITY_SD_2:
    _SD_DATA[_city] = _SD_GRADE2
for _city in _CITY_SD_3:
    _SD_DATA[_city] = _SD_GRADE3


# =======================================================================
# 福建：3 档（省定四档 2265/2195/2045/1895）
# 依据：闽人社文〔2025〕《公布我省最低工资标准的通知》适用范围表（2025-04-01 起）：
#   第 1 档仅厦门 6 区；第 2 档含福州（鼓楼/台江/仓山/晋安/马尾/长乐等）、泉州（鲤城/丰泽/洛江/
#   泉港等）、漳州（芗城/龙文）、龙岩（新罗）；第 3 档含莆田、三明（三元）、南平（延平/建阳）、
#   宁德（蕉城）；第 4 档 1895/20 仅适用各县，未单列
# =======================================================================
_FJ_GRADE1 = (2265.0, 23.5)
_CITY_FJ_1 = ('厦门',)
#   ↑ 第 1 档（月 2265 / 时 23.5）：厦门（思明/湖里/集美/海沧/同安/翔安）
_FJ_GRADE2 = (2195.0, 23.0)
_CITY_FJ_2 = ('福州', '泉州', '漳州', '龙岩',)
#   ↑ 第 2 档（月 2195 / 时 23.0）：福州、泉州、漳州、龙岩
_FJ_GRADE3 = (2045.0, 21.5)
_CITY_FJ_3 = ('莆田', '三明', '南平', '宁德',)
#   ↑ 第 3 档（月 2045 / 时 21.5）：莆田、三明、南平、宁德
_FJ_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_FJ_1:
    _FJ_DATA[_city] = _FJ_GRADE1
for _city in _CITY_FJ_2:
    _FJ_DATA[_city] = _FJ_GRADE2
for _city in _CITY_FJ_3:
    _FJ_DATA[_city] = _FJ_GRADE3


# =======================================================================
# 安徽：3 档
# 依据：皖政办秘〔2025〕32号（2025-09-01 起执行，共 4 档，第 4 档 2000/20 适用于部分县，未单列）
# =======================================================================
_AH_GRADE1 = (2320.0, 23.0)
_CITY_AH_1 = ('合肥', '铜陵',)
#   ↑ 第 1 档（月 2320 / 时 23.0）：合肥、铜陵
_AH_GRADE2 = (2170.0, 22.0)
_CITY_AH_2 = ('淮北', '宿州', '蚌埠', '淮南', '滁州', '六安', '马鞍山', '芜湖', '宣城', '池州', '安庆',)
#   ↑ 第 2 档（月 2170 / 时 22.0）：淮北、宿州、蚌埠、淮南、滁州、六安、马鞍山、芜湖、宣城、池州、安庆
_AH_GRADE3 = (2100.0, 21.0)
_CITY_AH_3 = ('亳州', '阜阳', '黄山',)
#   ↑ 第 3 档（月 2100 / 时 21.0）：亳州、阜阳、黄山
_AH_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_AH_1:
    _AH_DATA[_city] = _AH_GRADE1
for _city in _CITY_AH_2:
    _AH_DATA[_city] = _AH_GRADE2
for _city in _CITY_AH_3:
    _AH_DATA[_city] = _AH_GRADE3


# =======================================================================
# 湖北：3 档
# 依据：鄂政办发（2025-12-01 起执行）附件《各档标准及适用区域》：
#   一档=武汉市区、襄阳（襄城/樊城）、宜昌（西陵/伍家岗/点军/猞亭）；
#   二档=黄石（黄石港/西塞山/下陆/铁山/大冶）、十堰（茅箭/张湾）、荆州（荆州/沙市）、荆门（东宝/掴刀）；
#   三档=鄂州、孝感、黄冈、咸宁、随州、恩施、神农架（主要为其市区/各县）
# =======================================================================
_HB_GRADE1 = (2400.0, 24.0)
_CITY_HB_1 = ('武汉', '襄阳', '宜昌',)
#   ↑ 一档（月 2400 / 时 24.0）：武汉、襄阳、宜昌（市区）
_HB_GRADE2 = (2130.0, 21.5)
_CITY_HB_2 = ('黄石', '十堰', '荆州', '荆门',)
#   ↑ 二档（月 2130 / 时 21.5）：黄石、十堰、荆州、荆门（市区）
_HB_GRADE3 = (1970.0, 20.0)
_CITY_HB_3 = ('鄂州', '孝感', '黄冈', '咸宁', '随州', '恩施', '神农架',)
#   ↑ 三档（月 1970 / 时 20.0）：鄂州、孝感、黄冈、咸宁、随州、恩施、神农架
_HB_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_HB_1:
    _HB_DATA[_city] = _HB_GRADE1
for _city in _CITY_HB_2:
    _HB_DATA[_city] = _HB_GRADE2
for _city in _CITY_HB_3:
    _HB_DATA[_city] = _HB_GRADE3


# =======================================================================
# 湖南：3 档
# 依据：湘人社规〔2025〕…（2025-09-01 起执行，3 档）
# =======================================================================
_HN_GRADE1 = (2200.0, 22.0)
_CITY_HN_1 = ('长沙', '株洲', '湘潭',)
#   ↑ 一档（月 2200 / 时 22.0）：长沙（芙蓉/天心/岳麓/开福/雨花/望城）、株洲（天元/荷塘/芦淞/石峰）、湘潭（城区）
_HN_GRADE2 = (2000.0, 20.0)
_CITY_HN_2 = ('衡阳', '岳阳', '常德', '张家界',)
#   ↑ 二档（月 2000 / 时 20.0）：衡阳（市区+南岳）、岳阳（楼区/君山/云溪等）、
#     常德（武陵/鼎城城区）、张家界（市政府 2025 公告：全市 2000）
_HN_GRADE3 = (1800.0, 18.0)
_CITY_HN_3 = ('邵阳', '益阳', '郴州', '永州', '怀化', '娄底', '湘西',)
#   ↑ 三档（月 1800 / 时 18.0）：邵阳、益阳、郴州、永州、怀化、娄底、湘西（均已核实）
_HN_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_HN_1:
    _HN_DATA[_city] = _HN_GRADE1
for _city in _CITY_HN_2:
    _HN_DATA[_city] = _HN_GRADE2
for _city in _CITY_HN_3:
    _HN_DATA[_city] = _HN_GRADE3


# =======================================================================
# 河南：3 档
# 依据：豫政（3 档）
# =======================================================================
_HEN_GRADE1 = (2350.0, 23.0)
_CITY_HEN_1 = ('郑州', '洛阳', '开封', '平顶山',)
#   ↑ 第 1 档（月 2350 / 时 23.0）：郑州、洛阳、开封、平顶山
_HEN_GRADE2 = (2150.0, 21.1)
_CITY_HEN_2 = ('南阳', '信阳', '周口', '安阳', '鹤壁', '新乡', '焦作', '濮阳', '许昌', '漯河', '三门峡',)
#   ↑ 第 2 档（月 2150 / 时 21.1）：南阳、信阳、周口、安阳、鹤壁、新乡、焦作、濮阳、许昌、漯河、三门峡
_HEN_GRADE3 = (2000.0, 19.6)
_CITY_HEN_3 = ('驻马店', '商丘',)
#   ↑ 第 3 档（月 2000 / 时 19.6）：驻马店、商丘
_HEN_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_HEN_1:
    _HEN_DATA[_city] = _HEN_GRADE1
for _city in _CITY_HEN_2:
    _HEN_DATA[_city] = _HEN_GRADE2
for _city in _CITY_HEN_3:
    _HEN_DATA[_city] = _HEN_GRADE3


# =======================================================================
# 河北：3 档
# 依据：冀人社字（3 档）
# =======================================================================
_HE_GRADE1 = (2380.0, 24.0)
_CITY_HE_1 = ('石家庄', '唐山', '秦皇岛',)
#   ↑ 第 1 档（月 2380 / 时 24.0）：石家庄、唐山、秦皇岛
_HE_GRADE2 = (2230.0, 22.0)
_CITY_HE_2 = ('邯郸', '邢台', '保定', '张家口', '承德',)
#   ↑ 第 2 档（月 2230 / 时 22.0）：邯郸、邢台、保定、张家口、承德
_HE_GRADE3 = (2080.0, 20.0)
_CITY_HE_3 = ('沧州', '廊坊', '衡水',)
#   ↑ 第 3 档（月 2080 / 时 20.0）：沧州、廊坊、衡水
_HE_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_HE_1:
    _HE_DATA[_city] = _HE_GRADE1
for _city in _CITY_HE_2:
    _HE_DATA[_city] = _HE_GRADE2
for _city in _CITY_HE_3:
    _HE_DATA[_city] = _HE_GRADE3


# =======================================================================
# 辽宁：3 档
# 依据：辽人社发（3 档）
# =======================================================================
_LN_GRADE1 = (2230.0, 22.0)
_CITY_LN_1 = ('沈阳', '大连',)
#   ↑ 第 1 档（月 2230 / 时 22.0）：沈阳、大连
_LN_GRADE2 = (2080.0, 20.0)
_CITY_LN_2 = ('鞍山', '抚顺', '本溪', '丹东', '锦州', '营口',)
#   ↑ 第 2 档（月 2080 / 时 20.0）：鞍山、抚顺、本溪、丹东、锦州、营口
_LN_GRADE3 = (1930.0, 19.0)
_CITY_LN_3 = ('阜新', '辽阳', '盘锦', '铁岭', '朝阳', '葫芦岛',)
#   ↑ 第 3 档（月 1930 / 时 19.0）：阜新、辽阳、盘锦、铁岭、朝阳、葫芦岛
_LN_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_LN_1:
    _LN_DATA[_city] = _LN_GRADE1
for _city in _CITY_LN_2:
    _LN_DATA[_city] = _LN_GRADE2
for _city in _CITY_LN_3:
    _LN_DATA[_city] = _LN_GRADE3


# =======================================================================
# 陕西：3 档（一类区/二类区/三类区）
# 依据：陕人社发（2026-01-01 起）附件《最低工资标准适用范围》：
#   一类区=西安市区、咸阳（秦都/渭城）、榆林（榆阳/横山）、杨陵；二类区=宝鸡（渭滨/金台/陈仓）、
#   铜川（王益）、渭南（临渭）、延安（宝塔）、汉中（汉台/南郑）、商洛（商州）、韩城；
#   三类区=安康（汉滨）及其余县
# =======================================================================
_SXAN_GRADE1 = (2376.0, 23.0)
_CITY_SXAN_1 = ('西安', '咸阳', '榆林',)
#   ↑ 一类区（月 2376 / 时 23.0）：西安、咸阳、榆林（市区）
_SXAN_GRADE2 = (2250.0, 21.7)
_CITY_SXAN_2 = ('宝鸡', '铜川', '渭南', '延安', '商洛', '汉中',)
#   ↑ 二类区（月 2250 / 时 21.7）：宝鸡、铜川、渭南、延安、商洛、汉中（市区）
_SXAN_GRADE3 = (2140.0, 20.7)
_CITY_SXAN_3 = ('安康',)
#   ↑ 三类区（月 2140 / 时 20.7）：安康
_SXAN_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_SXAN_1:
    _SXAN_DATA[_city] = _SXAN_GRADE1
for _city in _CITY_SXAN_2:
    _SXAN_DATA[_city] = _SXAN_GRADE2
for _city in _CITY_SXAN_3:
    _SXAN_DATA[_city] = _SXAN_GRADE3


# =======================================================================
# 山西：3 档
# 依据：晋政办发（3 档）
# =======================================================================
_SX_GRADE1 = (2150.0, 23.2)
_CITY_SX_1 = ('太原',)
#   ↑ 第 1 档（月 2150 / 时 23.2）：太原
_SX_GRADE2 = (2050.0, 22.1)
_CITY_SX_2 = ('大同', '阳泉', '长治', '晋城',)
#   ↑ 第 2 档（月 2050 / 时 22.1）：大同、阳泉、长治、晋城
_SX_GRADE3 = (1950.0, 20.9)
_CITY_SX_3 = ('朔州', '晋中', '运城', '忻州', '临汾', '吕梁',)
#   ↑ 第 3 档（月 1950 / 时 20.9）：朔州、晋中、运城、忻州、临汾、吕梁
_SX_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_SX_1:
    _SX_DATA[_city] = _SX_GRADE1
for _city in _CITY_SX_2:
    _SX_DATA[_city] = _SX_GRADE2
for _city in _CITY_SX_3:
    _SX_DATA[_city] = _SX_GRADE3


# =======================================================================
# 江西：2 档使用（省定三类区域 2240/2090/1950）
# 依据：赣府厅字〔2025〕42号（2025-12-01 起）：一类区域=南昌市区（东湖/西湖/青云谱/青山湖/红谷滩等）；
#   二类区域=九江（浔阳/濂溪）、景德镇（珠山）、萍乡（安源/湘东）、新余（渝水）、鹰潭（月湖/贵溪）、
#   赣州（章贡/南康）、宜春（袁州）、上饶（信州）、吉安（吉州）、抚州（临川）与南昌（新建/南昌县）；
#   三类区域 1950/19.5 仅适用各县，未单列
# =======================================================================
_JX_GRADE1 = (2240.0, 22.4)
_CITY_JX_1 = ('南昌',)
#   ↑ 一类区域（月 2240 / 时 22.4）：南昌市区
_JX_GRADE2 = (2090.0, 20.9)
_CITY_JX_2 = ('赣州', '九江', '上饶', '景德镇', '萍乡', '新余', '鹰潭', '抚州', '吉安', '宜春',)
#   ↑ 二类区域（月 2090 / 时 20.9）：赣州、九江、上饶、景德镇、萍乡、新余、鹰潭、抚州、吉安、宜春
_JX_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_JX_1:
    _JX_DATA[_city] = _JX_GRADE1
for _city in _CITY_JX_2:
    _JX_DATA[_city] = _JX_GRADE2


# =======================================================================
# 海南：2 档
# 依据：琼人社规〔2025〕7号（2025-12-01 起执行，2 类地区）
# =======================================================================
_HI_GRADE1 = (2250.0, 20.0)
_CITY_HI_1 = ('海口', '三亚', '三沙', '儋州',)
#   ↑ 第 1 档（月 2250 / 时 20.0）：海口、三亚、三沙、儋州
_HI_GRADE2 = (2070.0, 18.4)
_CITY_HI_2 = ('文昌', '琼海', '万宁', '东方', '五指山', '澄迈', '乐东', '临高', '定安', '屯昌', '陵水', '昌江', '保亭', '琼中', '白沙',)
#   ↑ 第 2 档（月 2070 / 时 18.4）：文昌、琼海、万宁、东方、五指山、澄迈、乐东、临高、定安、屯昌、陵水、昌江、保亭、琼中、白沙
_HI_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_HI_1:
    _HI_DATA[_city] = _HI_GRADE1
for _city in _CITY_HI_2:
    _HI_DATA[_city] = _HI_GRADE2


# =======================================================================
# 内蒙古：3 档
# 依据：内政办发（3 档）
# =======================================================================
_NMG_GRADE1 = (2380.0, 23.5)
_CITY_NMG_1 = ('呼和浩特', '包头', '鄂尔多斯',)
#   ↑ 第 1 档（月 2380 / 时 23.5）：呼和浩特、包头、鄂尔多斯
_NMG_GRADE2 = (2310.0, 22.8)
_CITY_NMG_2 = ('乌海', '赤峰', '通辽', '呼伦贝尔',)
#   ↑ 第 2 档（月 2310 / 时 22.8）：乌海、赤峰、通辽、呼伦贝尔
_NMG_GRADE3 = (2250.0, 22.2)
_CITY_NMG_3 = ('乌兰察布', '兴安盟', '锡林郭勒', '阿拉善', '巴彦淖尔',)
#   ↑ 第 3 档（月 2250 / 时 22.2）：乌兰察布、兴安盟、锡林郭勒、阿拉善、巴彦淖尔
_NMG_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_NMG_1:
    _NMG_DATA[_city] = _NMG_GRADE1
for _city in _CITY_NMG_2:
    _NMG_DATA[_city] = _NMG_GRADE2
for _city in _CITY_NMG_3:
    _NMG_DATA[_city] = _NMG_GRADE3


# =======================================================================
# 云南：3 档
# 依据：云人社发（3 档）
# =======================================================================
_YN_GRADE1 = (2170.0, 21.0)
_CITY_YN_1 = ('昆明',)
#   ↑ 第 1 档（月 2170 / 时 21.0）：昆明
_YN_GRADE2 = (2020.0, 20.0)
_CITY_YN_2 = ('曲靖', '玉溪', '大理',)
#   ↑ 第 2 档（月 2020 / 时 20.0）：曲靖、玉溪、大理
_YN_GRADE3 = (1870.0, 19.0)
_CITY_YN_3 = ('昭通', '丽江', '普洱', '保山', '临沧', '西双版纳', '楚雄', '红河', '文山', '怒江', '迪庆',)
#   ↑ 第 3 档（月 1870 / 时 19.0）：昭通、丽江、普洱、保山、临沧、西双版纳、楚雄、红河、文山、怒江、迪庆
_YN_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_YN_1:
    _YN_DATA[_city] = _YN_GRADE1
for _city in _CITY_YN_2:
    _YN_DATA[_city] = _YN_GRADE2
for _city in _CITY_YN_3:
    _YN_DATA[_city] = _YN_GRADE3


# =======================================================================
# 贵州：3 档
# 依据：黔人社发（3 档）
# =======================================================================
_GZ_GRADE1 = (2130.0, 22.4)
_CITY_GZ_1 = ('贵阳',)
#   ↑ 第 1 档（月 2130 / 时 22.4）：贵阳
_GZ_GRADE2 = (1980.0, 20.8)
_CITY_GZ_2 = ('遵义', '六盘水', '安顺',)
#   ↑ 第 2 档（月 1980 / 时 20.8）：遵义、六盘水、安顺
_GZ_GRADE3 = (1890.0, 19.8)
_CITY_GZ_3 = ('毕节', '铜仁', '黔东南', '黔南', '黔西南',)
#   ↑ 第 3 档（月 1890 / 时 19.8）：毕节、铜仁、黔东南、黔南、黔西南
_GZ_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_GZ_1:
    _GZ_DATA[_city] = _GZ_GRADE1
for _city in _CITY_GZ_2:
    _GZ_DATA[_city] = _GZ_GRADE2
for _city in _CITY_GZ_3:
    _GZ_DATA[_city] = _GZ_GRADE3


# =======================================================================
# 广西：3 档
# 依据：桂人社发（3 档）
# =======================================================================
_GX_GRADE1 = (2200.0, 22.4)
_CITY_GX_1 = ('南宁', '柳州', '桂林', '梧州',)
#   ↑ 第 1 档（月 2200 / 时 22.4）：南宁、柳州、桂林、梧州
_GX_GRADE2 = (2040.0, 20.7)
_CITY_GX_2 = ('北海', '防城港', '钦州', '贵港', '玉林',)
#   ↑ 第 2 档（月 2040 / 时 20.7）：北海、防城港、钦州、贵港、玉林
_GX_GRADE3 = (1870.0, 19.0)
_CITY_GX_3 = ('百色', '贺州', '河池', '来宾', '崇左',)
#   ↑ 第 3 档（月 1870 / 时 19.0）：百色、贺州、河池、来宾、崇左
_GX_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_GX_1:
    _GX_DATA[_city] = _GX_GRADE1
for _city in _CITY_GX_2:
    _GX_DATA[_city] = _GX_GRADE2
for _city in _CITY_GX_3:
    _GX_DATA[_city] = _GX_GRADE3


# =======================================================================
# 新疆：3 档
# 依据：新政发（3 档）
# =======================================================================
_XJ_GRADE1 = (2070.0, 20.7)
_CITY_XJ_1 = ('乌鲁木齐', '昌吉', '石河子',)
#   ↑ 第 1 档（月 2070 / 时 20.7）：乌鲁木齐、昌吉、石河子
_XJ_GRADE2 = (1890.0, 18.9)
_CITY_XJ_2 = ('克拉玛依', '吐鲁番', '哈密', '巴音郭楞',)
#   ↑ 第 2 档（月 1890 / 时 18.9）：克拉玛依、吐鲁番、哈密、巴音郭楞
_XJ_GRADE3 = (1750.0, 17.5)
_CITY_XJ_3 = ('阿克苏', '喀什', '和田', '伊犁', '塔城', '阿勒泰', '克州', '博尔塔拉',)
#   ↑ 第 3 档（月 1750 / 时 17.5）：阿克苏、喀什、和田、伊犁、塔城、阿勒泰、克州、博尔塔拉
_XJ_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_XJ_1:
    _XJ_DATA[_city] = _XJ_GRADE1
for _city in _CITY_XJ_2:
    _XJ_DATA[_city] = _XJ_GRADE2
for _city in _CITY_XJ_3:
    _XJ_DATA[_city] = _XJ_GRADE3


# =======================================================================
# 宁夏：2 档
# 依据：宁人社发（2 档）
# =======================================================================
_NX_GRADE1 = (2235.0, 22.0)
_CITY_NX_1 = ('银川',)
#   ↑ 第 1 档（月 2235 / 时 22.0）：银川
_NX_GRADE2 = (2080.0, 20.0)
_CITY_NX_2 = ('石嘴山', '吴忠', '固原', '中卫',)
#   ↑ 第 2 档（月 2080 / 时 20.0）：石嘴山、吴忠、固原、中卫
_NX_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_NX_1:
    _NX_DATA[_city] = _NX_GRADE1
for _city in _CITY_NX_2:
    _NX_DATA[_city] = _NX_GRADE2


# =======================================================================
# 甘肃：3 档
# 依据：甘政办发（3 档）
# =======================================================================
_GS_GRADE1 = (2200.0, 22.0)
_CITY_GS_1 = ('兰州',)
#   ↑ 第 1 档（月 2200 / 时 22.0）：兰州
_GS_GRADE2 = (2130.0, 21.5)
_CITY_GS_2 = ('天水', '白银', '酒泉',)
#   ↑ 第 2 档（月 2130 / 时 21.5）：天水、白银、酒泉
_GS_GRADE3 = (2080.0, 21.0)
_CITY_GS_3 = ('张掖', '武威', '定西', '陇南', '平凉', '庆阳', '临夏', '甘南',)
#   ↑ 第 3 档（月 2080 / 时 21.0）：张掖、武威、定西、陇南、平凉、庆阳、临夏、甘南
_GS_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_GS_1:
    _GS_DATA[_city] = _GS_GRADE1
for _city in _CITY_GS_2:
    _GS_DATA[_city] = _GS_GRADE2
for _city in _CITY_GS_3:
    _GS_DATA[_city] = _GS_GRADE3


# =======================================================================
# 青海：1 档
# 依据：青人社厅发（单档）
# =======================================================================
_QH_GRADE1 = (2080.0, 20.0)
_CITY_QH_1 = ('西宁', '海东', '海北', '黄南', '海南', '果洛', '玉树', '海西',)
#   ↑ 第 1 档（月 2080 / 时 20.0）：西宁、海东、海北、黄南、海南、果洛、玉树、海西
_QH_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_QH_1:
    _QH_DATA[_city] = _QH_GRADE1


# =======================================================================
# 西藏：1 档
# 依据：藏人社发（单档）
# =======================================================================
_XZ_GRADE1 = (2360.0, 23.0)
_CITY_XZ_1 = ('拉萨', '日喀则', '昌都', '林芝', '山南', '那曲', '阿里',)
#   ↑ 第 1 档（月 2360 / 时 23.0）：拉萨、日喀则、昌都、林芝、山南、那曲、阿里
_XZ_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_XZ_1:
    _XZ_DATA[_city] = _XZ_GRADE1


# =======================================================================
# 吉林：3 档
# 依据：吉人社发（3 档）
# =======================================================================
_JL_GRADE1 = (2230.0, 22.0)
_CITY_JL_1 = ('长春',)
#   ↑ 第 1 档（月 2230 / 时 22.0）：长春
_JL_GRADE2 = (2020.0, 20.5)
_CITY_JL_2 = ('吉林', '四平', '通化', '延边',)
#   ↑ 第 2 档（月 2020 / 时 20.5）：吉林、四平、通化、延边
_JL_GRADE3 = (1870.0, 19.0)
_CITY_JL_3 = ('白城', '松原',)
#   ↑ 第 3 档（月 1870 / 时 19.0）：白城、松原
_JL_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_JL_1:
    _JL_DATA[_city] = _JL_GRADE1
for _city in _CITY_JL_2:
    _JL_DATA[_city] = _JL_GRADE2
for _city in _CITY_JL_3:
    _JL_DATA[_city] = _JL_GRADE3


# =======================================================================
# 黑龙江：3 档
# 依据：黑人社发（3 档）
# =======================================================================
_HLJ_GRADE1 = (2270.0, 21.0)
_CITY_HLJ_1 = ('哈尔滨',)
#   ↑ 第 1 档（月 2270 / 时 21.0）：哈尔滨
_HLJ_GRADE2 = (2010.0, 18.8)
_CITY_HLJ_2 = ('齐齐哈尔', '大庆', '牡丹江', '佳木斯',)
#   ↑ 第 2 档（月 2010 / 时 18.8）：齐齐哈尔、大庆、牡丹江、佳木斯
_HLJ_GRADE3 = (1910.0, 18.2)
_CITY_HLJ_3 = ('鸡西', '双鸭山', '伊春', '七台河', '鹤岗', '绥化', '大兴安岭',)
#   ↑ 第 3 档（月 1910 / 时 18.2）：鸡西、双鸭山、伊春、七台河、鹤岗、绥化、大兴安岭
_HLJ_DATA: dict[str, tuple[float, float]] = {}
for _city in _CITY_HLJ_1:
    _HLJ_DATA[_city] = _HLJ_GRADE1
for _city in _CITY_HLJ_2:
    _HLJ_DATA[_city] = _HLJ_GRADE2
for _city in _CITY_HLJ_3:
    _HLJ_DATA[_city] = _HLJ_GRADE3


# =======================================================================
# 省 → 数据字典 的统一映射（新加省份在这里注册 + 上面 PROVINCES）
# =======================================================================
_REGION_DATA: dict[str, dict[str, tuple[float, float]]] = {
    "北京": _BJ_DATA, "上海": _SH_DATA, "天津": _TJ_DATA, "重庆": _CQ_DATA,
    "广东": _GD_DATA, "江苏": _JS_DATA, "浙江": _ZJ_DATA, "山东": _SD_DATA,
    "福建": _FJ_DATA, "安徽": _AH_DATA, "四川": _SC_DATA, "湖北": _HB_DATA,
    "湖南": _HN_DATA, "河南": _HEN_DATA, "河北": _HE_DATA, "江西": _JX_DATA,
    "山西": _SX_DATA, "辽宁": _LN_DATA, "吉林": _JL_DATA, "黑龙江": _HLJ_DATA,
    "陕西": _SXAN_DATA, "云南": _YN_DATA, "贵州": _GZ_DATA, "广西": _GX_DATA,
    "海南": _HI_DATA, "内蒙古": _NMG_DATA, "新疆": _XJ_DATA, "宁夏": _NX_DATA,
    "甘肃": _GS_DATA, "青海": _QH_DATA, "西藏": _XZ_DATA,
}

# 省份显示顺序（常用省排前）
PROVINCES = [
    "北京", "上海", "广东", "江苏", "浙江",
    "天津", "重庆", "四川", "山东", "福建",
    "安徽", "湖北", "湖南", "河南", "河北",
    "辽宁", "陕西", "山西", "江西", "海南",
    "内蒙古", "云南", "贵州", "广西",
    "新疆", "宁夏", "甘肃", "青海", "西藏",
    "吉林", "黑龙江",
]


def get_regions(province: str) -> list[str]:
    """返回某省份下所有地级市名（保序）。"""
    return list(_REGION_DATA.get(province, {}).keys())


def get(province: str, region: str | None = None) -> tuple[float, float] | None:
    """返回 (月最低工资, 非全日制小时最低工资)。
    region 为 None 时取该省第一个城市；未收录返回 None。"""
    regions = _REGION_DATA.get(province)
    if not regions:
        return None
    if region and region in regions:
        return regions[region]
    # 未指定 region → 取第一项
    return next(iter(regions.values()))


# —— Chat API 接入：用 LLM 查询最低工资 ——
# 策略（用户 2026-10-07 定）：内置表与 API 两个数据源**各自独立**，
# 由界面上的按钮决定用哪个：fetch_local / fetch_holidays_local 纯本地不联网，
# fetch_wage_api / fetch_holidays_api 只走 API，两者之间不自动互相替代。
# 省/市数据在上方 _XX_DATA / _XX_GRADEn 分块中定义，可随时编辑修改数值。
# api_model：OpenAI 兼容服务的模型名（DeepSeek / 通义 / Kimi / 智谱 等），
#   **只在「API 设置」里填写，没有内置默认值**（用户 2026-10-07：取消默认 api，选哪个用哪个）。


def _chat_model(api_model: str | None) -> str:
    """返回本次请求用的模型名。

    **没有默认值**：以「API 设置」里填写的为准；没填就直接报错，
    绝不隐式用某个内置模型发请求（用户 2026-10-07 口径）。
    """
    name = (api_model or "").strip()
    if not name:
        raise ChatError("未填写模型名：请在「⚙️ API 设置」里选择服务商或手动填写模型名")
    return name


# ========================= 网络层（三处 API 调用共用） =========================
# 最低工资查询 / 节假日查询 / 测试连接三个功能走的是同一个 OpenAI 兼容
# /chat/completions 端点，请求构造、HTTPS 校验、错误翻译完全一致，故收敛到
# 下面这一层。改超时 / 改错误文案 / 加自定义 Header 都只需改这里。

CHAT_TIMEOUT = 25         # 最低工资等短回答的超时（秒）：推理型模型要先「思考」再输出，
                          # 15 秒偏紧（实测带 reasoning 的模型单次问答 2~10 秒）
HOLIDAY_TIMEOUT = 45      # 节假日要吐 30+ 个日期，慢模型更久
CHAT_PATH = "/chat/completions"
# 有些网关/自建代理不校验 Key，也常见「只填地址不填 Key」→ 仅要求地址
_RETRY_STATUS = (429, 500, 502, 503, 504)   # 限流 / 服务端临时错误 → 退避重试一次
_RETRY_DELAY = 0.8
# 服务端不支持 response_format 时常见的状态码 → 去掉该字段重试
_JSON_MODE_REJECT = (400, 404, 415, 422)
_USER_AGENT = "AttendanceDesktop/1.0 (PySide6; +https://github.com/baijiahei-code/AttendanceDesktop)"


class ChatError(Exception):
    """API 调用失败，message 为可直接展示给用户的中文原因。"""


class _HttpFailure(Exception):
    """HTTP 层失败（带状态码与服务端原始说明），供 _post_chat 决定重试/降级。"""

    def __init__(self, code: int, detail: str = ""):
        super().__init__(f"{code} {detail}")
        self.code = code
        self.detail = detail


def _endpoint(api_url: str | None) -> str | None:
    """拼出 /chat/completions 端点；非 https 或地址为空返回 None。

    安全防线：仅允许 HTTPS + 强制校验证书，防止中间人窃取 Bearer Token。
    当前版本刻意不接 http 本地服务（如 Ollama）。

    容错（用户贴错的常见形态）：
    * 直接粘贴完整端点 ``.../v1/chat/completions`` → 不再重复拼一段（原会变 404）
    * 地址带查询串（``...?key=xxx``，部分网关要求）→ 在 ``?`` 之前插入路径
    """
    url = (api_url or "").strip()
    if not url:
        return None
    query = ""
    for sep in ("?", "#"):
        if sep in url:
            url, rest = url.split(sep, 1)
            query = sep + rest
            break
    url = url.rstrip("/")
    endpoint = url if url.lower().endswith(CHAT_PATH) else url + CHAT_PATH
    endpoint += query
    return endpoint if endpoint.lower().startswith("https://") else None


def _http_reason(code: int, detail: str = "") -> str:
    """HTTP 状态码 → 用户可读原因（三处调用共用同一套文案）。

    ``detail`` 是服务端返回的原始说明（如 model not found / response_format
    不支持），附在后面能大幅提高用户自查效率。
    """
    if code == 400:
        base = "请求被服务端拒绝（400，常见原因：模型名不受支持 / 参数不被接受）"
    elif code == 401:
        base = "API Key 无效（401）"
    elif code == 403:
        base = "API Key 无权访问该模型（403）"
    elif code == 404:
        base = "接口地址或模型名不正确（404），请检查 API 地址与模型名"
    elif code == 429:
        base = "调用频率超限（429），请稍后再试"
    elif code >= 500:
        base = f"服务商服务器错误（{code}）"
    else:
        base = f"HTTP 错误（{code}）"
    detail = " ".join((detail or "").split())[:160]
    return f"{base}｜服务端：{detail}" if detail else base


def _url_reason(err: urllib.error.URLError) -> str:
    """URLError → 用户可读原因（超时 / 证书 / 其它网络故障）。"""
    reason = getattr(err, "reason", err)
    msg = str(reason)
    if isinstance(reason, socket.timeout) or "timed out" in msg.lower():
        return "连接超时，请检查网络或 API 地址"
    if isinstance(reason, ssl.SSLError) or "ssl" in msg.lower() or "certificate" in msg.lower():
        return f"TLS/证书校验失败：{reason}"
    return f"网络请求失败：{reason}"


def _content_text(message: dict) -> str:
    """从 message 里取回复正文（兼容 content 为字符串 / 多段数组 / 老式 text 字段）。"""
    c = message.get("content")
    if isinstance(c, list):      # 部分网关回 [{"type": "text", "text": "..."}]
        c = "".join(str(it.get("text") or it.get("content") or "") if isinstance(it, dict)
                     else str(it) for it in c)
    if not c:
        c = message.get("text") or ""
    return str(c)


def _request_json(endpoint: str, api_key: str | None, payload: dict,
                  timeout: int) -> str:
    """POST 一次 /chat/completions，返回首条回复文本。

    HTTP 失败抛 :class:`_HttpFailure`（带状态码与服务端说明），网络失败抛
    :class:`ChatError`（已是可展示文案）。
    """
    headers = {"Content-Type": "application/json",
               "Accept": "application/json",
               "User-Agent": _USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode("utf-8"),
        headers=headers, method="POST")
    ctx = ssl.create_default_context()  # 默认启用 hostname 检查 + 证书链校验
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - 读不出就算了，别掩盖原始错误
            pass
        raise _HttpFailure(e.code, detail) from e
    except urllib.error.URLError as e:
        raise ChatError(_url_reason(e)) from e
    except socket.timeout as e:
        raise ChatError("连接超时，请检查网络或 API 地址") from e
    except Exception as e:  # noqa: BLE001 - 兜底：任何异常都转成可展示原因
        raise ChatError(f"网络请求失败：{e}") from e
    try:
        body = json.loads(raw)
    except ValueError as e:
        raise ChatError(
            "返回内容不是有效 JSON，可能不是 OpenAI 兼容的 /chat/completions 端点") from e
    if not isinstance(body, dict):
        raise ChatError("接口返回结构异常（顶层不是 JSON 对象）")
    choices = body.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise ChatError("接口返回 200 但无 choices 字段，可能不是兼容的 chat 接口")
    choice = choices[0]
    message = choice.get("message") or {}
    content = _content_text(message).strip()
    if not content:
        # ⚠ 实测坑（2026-10-07）：推理型模型（如 agnes-2.5-flash / deepseek-reasoner / glm-4.5）
        # 会先把 token 花在 reasoning_content 上 —— 若 max_tokens 给小了（原来测试连接写 8），
        # finish_reason=length、content 为空、text_tokens=0，报「内容为空」会让人误以为 Key/模型名错。
        finish = choice.get("finish_reason") or "?"
        reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
        if reasoning or finish == "length":
            raise ChatError(
                f"模型只产出了思考内容就被截断（finish_reason={finish}）："
                "这是推理型模型的表现，请增大 max_tokens 或换用非推理型模型")
        raise ChatError(f"接口返回内容为空（finish_reason={finish}），请检查模型名是否可用")
    return content


def _post_chat(api_url: str | None, api_key: str | None, messages: list,
               api_model: str | None = None, max_tokens: int | None = None,
               timeout: int = CHAT_TIMEOUT, json_mode: bool = False) -> str:
    """调用 OpenAI 兼容 /chat/completions，返回首条回复文本。

    ``json_mode=True`` 时先带 ``response_format={"type":"json_object"}``（支持的服务
    能显著提升结构稳定性）；服务端回「不支持该字段」则自动去掉重试。
    限流 / 5xx 会退避重试一次（401/403/404 这类配置错误不重试）。

    失败一律抛 :class:`ChatError`（带可展示原因），由调用方转成用户可读提示，
    避免各处重复 try/except 与文案。
    """
    endpoint = _endpoint(api_url)
    if endpoint is None:
        raise ChatError("API 地址无效：必须以 https:// 开头（当前版本不支持 http 本地服务）")
    payload: dict = {
        "model": _chat_model(api_model),
        "temperature": 0,
        "messages": messages,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    use_json_mode = bool(json_mode)
    for attempt in (0, 1):          # 首次 + 一次重试（或降级）
        body = dict(payload)
        if use_json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            return _request_json(endpoint, api_key, body, timeout)
        except _HttpFailure as e:
            if attempt == 0 and use_json_mode and e.code in _JSON_MODE_REJECT:
                use_json_mode = False       # 服务端不认 response_format → 去掉重试
                continue
            if attempt == 0 and e.code in _RETRY_STATUS:
                time.sleep(_RETRY_DELAY)    # 限流 / 临时故障 → 等一拍重试
                continue
            raise ChatError(_http_reason(e.code, e.detail)) from e
    raise ChatError("请求失败（已重试一次）")   # 逻辑上不可达


def _extract_json(text: str) -> dict:
    """从模型回复里取出 JSON 对象（容错 markdown 围栏 / 前后解释 / 嵌套对象）。

    原来两处调用各写了一个正则：最低工资用 ``\\{[^}]+\\}``（遇嵌套对象直接截断），
    节假日用 ``\\{[\\s\\S]*\\}``（贪婪，会把后面的内容一起吃进来）。这里统一成
    「从第一个 ``{`` 起做括号配对（跳过字符串内的括号）」——两者都覆盖，且能容忍
    模型在 JSON 后多写一句解释。
    """
    s = (text or "").strip()
    if s.startswith("```"):                       # ```json ... ```
        s = re.sub(r"^```[A-Za-z]*\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    start = s.find("{")
    if start < 0:
        raise ValueError("回复里没有 JSON 对象")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                parsed = json.loads(s[start:i + 1])
                if not isinstance(parsed, dict):
                    raise ValueError("JSON 顶层不是对象")
                return parsed
    raise ValueError("JSON 括号不配对（可能被截断）")


def fetch_local(province: str, region: str | None = None) -> dict | None:
    """【内置官方表】按省+地区取值，**纯本地、不联网**。

    用户 2026-10-07 定的口径：本地表和 API 不再分优先级、不自动回退 ——
    界面上点哪个按钮就用哪个的数据源。表里没有该地区时返回 None，
    由界面提示改用「联网查询」或手动输入。

    返回 {"min_wage": float, "parttime_min": float, "source": "local"}。
    """
    local = get(province, region)
    if local is None:
        return None
    return {"min_wage": local[0], "parttime_min": local[1], "source": "local"}


def fetch_wage_api(api_url: str | None, api_key: str | None,
                   year: int, month: int, province: str, region: str,
                   api_model: str | None = None) -> dict:
    """【联网查询】只走 API，**不回退内置表**（与 :func:`fetch_local` 对称）。

    失败时返回带 ``api_error`` 的 dict（min_wage/parttime_min 为 0），
    由界面直接提示失败原因 —— 不静默换成另一份数据。
    """
    if not api_url:
        return {"min_wage": 0.0, "parttime_min": 0.0, "source": "api",
                "api_error": "未配置 API 地址（请先点「⚙️ API 设置」）"}
    api_result, api_error = _try_chat_api(
        api_url, api_key, year, month, province, region, api_model=api_model)
    if api_result is not None:
        return api_result
    return {"min_wage": 0.0, "parttime_min": 0.0, "source": "api",
            "api_error": api_error or "未知原因"}


# API 返回值的合理性区间：模型幻觉（例如 999999 或 0.5）**不能进账本** ——
# 最低工资会联动加班费基数与公积金基数，写错会直接算错工资。
MIN_WAGE_RANGE = (500.0, 20000.0)      # 月最低工资（元）
PARTTIME_RANGE = (5.0, 200.0)          # 非全日制小时最低工资（元/时）
# 中国各地「非全日制小时标准 ÷ 月标准」普遍在 0.009~0.011（≈1/100）附近，
# 用宽松的 0.005~0.02 做交叉校验，可挡住「月 2170 / 时 150」这类明显不搭的值。
_HOURLY_TO_MONTHY_RANGE = (0.005, 0.02)


def _try_chat_api(api_url: str, api_key: str,
                  year: int, month: int, province: str, region: str,
                  api_model: str | None = None) -> tuple[dict | None, str | None]:
    """单次 Chat API 调用。prompt 包含用户选择的年份/月份。

    返回 (数据, 失败原因)：成功 (dict, None)；失败 (None, "用户可读原因")。
    """
    prompt = (
        f"请查询中国 {province} {region} {year} 年 {month} 月的最低工资标准。"
        f"返回一个 JSON 对象，只包含两个数值字段：min_wage（月最低工资，单位元）和 parttime_min（非全日制小时最低工资，单位元）。"
        f"如果找不到 {year} 年 {month} 月的官方发布标准，就用该地区在 {year} 年 {month} 月实际有效的最新标准。"
        f"直接返回 JSON，不要任何解释、不要 markdown、不要代码块。"
    )
    try:
        content = _post_chat(api_url, api_key,
                             [{"role": "user", "content": prompt}],
                             api_model=api_model, json_mode=True)
    except ChatError as e:
        return None, str(e)
    try:
        parsed = _extract_json(content)
        mw = float(parsed.get("min_wage") or 0)
        ph = float(parsed.get("parttime_min") or 0)
    except (ValueError, TypeError, AttributeError):
        return None, "模型返回的不是要求的 JSON 格式（可换用更擅长结构化输出的模型，或改用本地表）"
    if mw <= 0 or ph <= 0:
        return None, "模型未返回有效数额（需同时给出 min_wage 与 parttime_min）"
    # —— 合理性校验：宁可退回本地表，也不让可疑数值进账本 ——
    if not (MIN_WAGE_RANGE[0] <= mw <= MIN_WAGE_RANGE[1]):
        return None, (f"模型给出的月最低工资 {mw:g} 元明显不合理"
                      f"（合理区间 {MIN_WAGE_RANGE[0]:g}~{MIN_WAGE_RANGE[1]:g} 元），已忽略")
    if not (PARTTIME_RANGE[0] <= ph <= PARTTIME_RANGE[1]):
        return None, (f"模型给出的非全日制小时工资 {ph:g} 元/时明显不合理"
                      f"（合理区间 {PARTTIME_RANGE[0]:g}~{PARTTIME_RANGE[1]:g} 元），已忽略")
    ratio = ph / mw
    if not (_HOURLY_TO_MONTHY_RANGE[0] <= ratio <= _HOURLY_TO_MONTHY_RANGE[1]):
        return None, (f"模型给出的两个数额不匹配（月 {mw:g} 元 / 小时 {ph:g} 元，"
                      f"正常应为月标准的约 1/100），已忽略")
    return {"min_wage": mw, "parttime_min": ph, "source": "api"}, None


# —— 节假日 API：独立于最低工资 API，复用相同连接信息 ——
# 返回结构：{
#   "statutory": ["MM-DD", ...],   # 法定节假日（加班×3，mark=1）
#   "rest": ["MM-DD", ...],        # 放假调休区间（含法定日与拼假休息日，status=休息）
#   "makeup": ["MM-DD", ...],      # 调休补班日（周末上班，status=上班）
#   "source": "api"|"local"
# }
# 两个数据源各自独立：本地表走 fetch_holidays_local，联网走 fetch_holidays_api，
# 谁都不回退给谁（用户 2026-10-07 口径）。


def fetch_holidays_local(year: int) -> dict | None:
    """【内置官方表】读 holidays.py 的某年安排，**纯本地、不联网**。

    未收录该年（通常因为国务院尚未公布，惯例是上年 11 月发布）返回 None。
    """
    return _holidays_from_local(year)


def fetch_holidays_api(api_url: str | None, api_key: str | None,
                       year: int, api_model: str | None = None) -> dict:
    """【联网查询】只走 API，**不回退内置表**（与 :func:`fetch_holidays_local` 对称）。

    失败时返回带 ``api_error`` 的 dict，日期均为空 —— 界面据此提示原因，
    不会把另一份数据偷偷换上。
    """
    if not api_url:
        return {"statutory": [], "rest": [], "makeup": [], "source": "api",
                "api_error": "未配置 API 地址（请先点「⚙️ API 设置」）"}
    r, api_error = _try_holiday_api(api_url, api_key, year, api_model=api_model)
    if r is not None:
        return r
    return {"statutory": [], "rest": [], "makeup": [], "source": "api",
            "api_error": api_error or "未知原因"}


def _holidays_from_local(year: int) -> dict | None:
    """从 holidays.py 本地数据读取节假日安排（结构与 API 返回一致）。"""
    from . import holidays
    sets = holidays._year_sets(year)  # type: ignore[attr-defined]
    if sets is None:
        return None
    return {
        "statutory": sorted(sets["statutory"]),
        "rest": sorted(sets["rest"]),
        "makeup": sorted(sets["makeup"]),
        "source": "local",
    }


def _clean_mmdd(arr) -> list[str]:
    """把模型返回的日期数组规范成去重排序的 MM-DD 列表（无法识别的项直接丢弃）。"""
    clean: list[str] = []
    if not isinstance(arr, list):
        return clean
    for s in arr:
        parts = str(s).strip().replace("/", "-").split("-")
        if len(parts) == 2:
            mm, dd = parts
        elif len(parts) == 3:  # 兼容 YYYY-MM-DD
            mm, dd = parts[1], parts[2]
        else:
            continue
        try:
            mi, di = int(mm), int(dd)
        except ValueError:
            continue
        if not (1 <= mi <= 12 and 1 <= di <= 31):
            continue
        item = f"{mi:02d}-{di:02d}"
        if item not in clean:
            clean.append(item)
    return sorted(clean)


def _try_holiday_api(api_url: str, api_key: str, year: int,
                     api_model: str | None = None) -> tuple[dict | None, str | None]:
    """调用 Chat API 查询某年中国法定节假日安排。

    返回 (数据, 失败原因)：成功 (dict, None)；失败 (None, "用户可读原因")。
    """
    prompt = (
        f"请查询中国国务院办公厅发布的 {year} 年法定节假日放假安排（含每个节假日的"
        f"法定日、放假调休区间、调休补班日）。"
        "返回一个 JSON 对象，只包含三个数组字段："
        "1) statutory：数组，每项为 MM-DD 格式的法定节假日日期（×3加班的那一天）。"
        "2) rest：数组，每项为 MM-DD 格式的放假调休日（包括法定日和拼假休息日）。"
        "3) makeup：数组，每项为 MM-DD 格式的调休补班日（原本是周末但需要上班的日子）。"
        "严格基于官方发布的安排，不要臆造。直接返回 JSON，不要任何解释、不要 markdown、不要代码块。"
    )
    try:
        content = _post_chat(api_url, api_key,
                             [{"role": "user", "content": prompt}],
                             api_model=api_model, json_mode=True,
                             timeout=HOLIDAY_TIMEOUT)
    except ChatError as e:
        return None, str(e)
    try:
        parsed = _extract_json(content)
    except ValueError:
        return None, "模型返回的节假日数据不是有效 JSON（可换用更擅长结构化输出的模型）"
    result: dict = {k: _clean_mmdd(parsed.get(k))
                    for k in ("statutory", "rest", "makeup")}
    if not any(result.values()):
        return None, (f"模型没有给出任何日期（{year} 年的安排可能尚未公布，"
                      f"或该模型未能给出），请改用本地表")
    result["source"] = "api"
    return result, None


def test_connection(api_url: str | None, api_key: str | None,
                    api_model: str | None = None) -> tuple[bool, str]:
    """向配置的 OpenAI 兼容服务发一条最小消息，验证能否连通。

    返回 (True, "连接成功（xxx ms · 模型 xxx）") 或 (False, 具体原因)。
    供「API 设置」里的「测试连接」使用：能直接看出 Key 无效 / 模型名不对 /
    接口地址错 / 超时等问题。仅支持 https（当前版本不接本地 http 服务）。

    ⚠ **不要设 max_tokens**：实测推理型模型（agnes-2.5-flash）会把 8 个 token 全花在
    ``reasoning_content`` 上、正文为空、``finish_reason=length`` → 误报「接口返回内容为空」。

    错误文案与运行时调用完全一致 —— 都来自 _post_chat / ChatError。
    """
    start = time.monotonic()
    try:
        _post_chat(api_url, api_key, [{"role": "user", "content": "请只回复：ok"}],
                   api_model=api_model)
    except ChatError as e:
        return False, str(e)
    ms = int((time.monotonic() - start) * 1000)
    return True, f"连接成功（{ms} ms · 模型 {_chat_model(api_model)}）"
