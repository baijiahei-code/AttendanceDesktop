"""全国最低工资标准（省 → 地级市 二级结构）。
数据来源：各省人社厅公开文件，2024 年起执行的最新一档。
同档城市共用同一标准，但每个地级市作为独立选项出现在下拉中，方便精确选择。
未收录返回 None；如需更新请查当地人社厅最新通知。

== 修改某省数值的方法 ======================================================
每个省在下方都有独立的数据块，结构完全一致：
    _XX_GRADE1 = (月最低工资, 非全日制小时最低工资)   # 一行一个档位
    ...
    _XX_DATA: dict[str, tuple[float, float]] = {}
    for _city in ("城市A", "城市B", ...):   _XX_DATA[_city] = _XX_GRADE1
    for _city in ("城市C", "城市D", ...):   _XX_DATA[_city] = _XX_GRADE2
    ...

想改标准数值 → 直接改该省 _XX_GRADEn 的元组
想改城市属哪一档 → 在 for 循环里把市名从一个行移到另一个行
===========================================================================
"""
from __future__ import annotations


# =======================================================================
# 安徽省：档级标准可直接修改
# 依据：皖政办秘〔2025〕32号，自2025年9月1日起执行
# =======================================================================
_AH_GRADE1 = (2320.0, 23.0)   # 一档：合肥市区、铜陵市区
_AH_GRADE2 = (2170.0, 22.0)   # 二档：淮北、宿州、蚌埠、淮南、滁州、六安、马鞍山、芜湖、宣城、池州、安庆（市区）
_AH_GRADE3 = (2100.0, 21.0)   # 三档：亳州市区、阜阳市区、黄山市屯溪区、黄山风景区
_AH_DATA: dict[str, tuple[float, float]] = {}
for _city in ("合肥", "铜陵"):                    _AH_DATA[_city] = _AH_GRADE1
for _city in ("淮北", "宿州", "蚌埠", "淮南", "滁州", "六安",
              "马鞍山", "芜湖", "宣城", "池州", "安庆"):
    _AH_DATA[_city] = _AH_GRADE2
for _city in ("亳州", "阜阳", "黄山"):             _AH_DATA[_city] = _AH_GRADE3


# =======================================================================
# 直辖市（全市统一 或 按区多档）
# =======================================================================
# —— 北京：全市统一 ——
_BJ_GRADE1 = (2420.0, 26.4)
_BJ_DATA: dict[str, tuple[float, float]] = {}
for _city in ("全市统一",):
    _BJ_DATA[_city] = _BJ_GRADE1


# —— 上海：全市统一 ——
_SH_GRADE1 = (2690.0, 24.0)
_SH_DATA: dict[str, tuple[float, float]] = {}
for _city in ("全市统一",):
    _SH_DATA[_city] = _SH_GRADE1


# —— 天津：全市统一（16 个辖区同一标准）——
_TJ_GRADE1 = (2420.0, 22.6)
_TJ_DATA: dict[str, tuple[float, float]] = {}
for _city in ("和平区", "河东区", "河西区", "南开区", "河北区", "红桥区",
              "东丽区", "西青区", "津南区", "北辰区", "武清区", "宝坻区",
              "滨海新区", "宁河区", "静海区", "蓟州区"):
    _TJ_DATA[_city] = _TJ_GRADE1


# —— 重庆：3 档 ——
_CQ_GRADE1 = (2100.0, 21.0)   # 主城区：渝中/大渡口/江北/沙坪坝/九龙坡/南岸/北碚/渝北/巴南
_CQ_GRADE2 = (2000.0, 20.0)   # 新城区：万州/涪陵/长寿/江津/合川/永川/璧山
_CQ_GRADE3 = (1900.0, 19.0)   # 远郊区县：其余
_CQ_DATA: dict[str, tuple[float, float]] = {}
for _city in ("渝中区", "大渡口区", "江北区", "沙坪坝区", "九龙坡区",
              "南岸区", "北碚区", "渝北区", "巴南区"):
    _CQ_DATA[_city] = _CQ_GRADE1
for _city in ("万州区", "涪陵区", "长寿区", "江津区", "合川区", "永川区", "璧山区"):
    _CQ_DATA[_city] = _CQ_GRADE2
for _city in ("黔江区", "南川区", "开州区", "梁平区", "武隆区",
              "城口县", "丰都县", "垫江县", "忠县", "云阳县",
              "奉节县", "巫山县", "巫溪县", "石柱县", "秀山县",
              "酉阳县", "彭水县"):
    _CQ_DATA[_city] = _CQ_GRADE3


# =======================================================================
# 广东（深圳/广州单列，其余分 A/B/C/D 档）
# =======================================================================
_GD_GRADE_SZ = (2360.0, 22.2)   # 深圳
_GD_GRADE_GZ = (2300.0, 22.2)   # 广州 + 珠海/佛山东莞中山
_GD_GRADE_A  = (2300.0, 22.2)
_GD_GRADE_B  = (2100.0, 20.3)   # 惠州/江门/肇庆
_GD_GRADE_C  = (2010.0, 19.0)   # 汕头/韶关/湛江/茂名/清远/梅州/汕尾/河源/阳江
_GD_GRADE_D  = (1900.0, 18.0)   # 潮州/揭阳/云浮
_GD_DATA: dict[str, tuple[float, float]] = {}
for _city in ("深圳",):
    _GD_DATA[_city] = _GD_GRADE_SZ
for _city in ("广州", "珠海", "佛山", "东莞", "中山"):
    _GD_DATA[_city] = _GD_GRADE_A
for _city in ("惠州", "江门", "肇庆"):
    _GD_DATA[_city] = _GD_GRADE_B
for _city in ("汕头", "韶关", "湛江", "茂名", "清远", "梅州",
              "汕尾", "河源", "阳江"):
    _GD_DATA[_city] = _GD_GRADE_C
for _city in ("潮州", "揭阳", "云浮"):
    _GD_DATA[_city] = _GD_GRADE_D


# =======================================================================
# 江苏（A/B/C 档）
# =======================================================================
_JS_GRADE_A = (2490.0, 24.0)   # 南京/苏州/无锡/常州/镇江
_JS_GRADE_B = (2260.0, 22.0)   # 徐州/南通/连云港/淮安/盐城/扬州/泰州
_JS_GRADE_C = (2070.0, 20.0)   # 宿迁
_JS_DATA: dict[str, tuple[float, float]] = {}
for _city in ("南京", "苏州", "无锡", "常州", "镇江"):
    _JS_DATA[_city] = _JS_GRADE_A
for _city in ("徐州", "南通", "连云港", "淮安", "盐城", "扬州", "泰州"):
    _JS_DATA[_city] = _JS_GRADE_B
for _city in ("宿迁",):
    _JS_DATA[_city] = _JS_GRADE_C


# =======================================================================
# 浙江（A/B 档）
# =======================================================================
_ZJ_GRADE_A = (2490.0, 24.0)   # 杭州/宁波/温州/嘉兴/湖州/绍兴/舟山/台州
_ZJ_GRADE_B = (2260.0, 22.0)   # 金华/衢州/丽水
_ZJ_DATA: dict[str, tuple[float, float]] = {}
for _city in ("杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "舟山", "台州"):
    _ZJ_DATA[_city] = _ZJ_GRADE_A
for _city in ("金华", "衢州", "丽水"):
    _ZJ_DATA[_city] = _ZJ_GRADE_B


# =======================================================================
# 山东（A/B/C 档）
# =======================================================================
_SD_GRADE_A = (2200.0, 22.0)   # 济南/青岛/淄博/东营/烟台/潍坊/威海
_SD_GRADE_B = (2010.0, 20.1)   # 枣庄/济宁/泰安/日照/临沂/德州/聊城/滨州
_SD_GRADE_C = (1820.0, 18.2)   # 菏泽
_SD_DATA: dict[str, tuple[float, float]] = {}
for _city in ("济南", "青岛", "淄博", "东营", "烟台", "潍坊", "威海"):
    _SD_DATA[_city] = _SD_GRADE_A
for _city in ("枣庄", "济宁", "泰安", "日照", "临沂", "德州", "聊城", "滨州"):
    _SD_DATA[_city] = _SD_GRADE_B
for _city in ("菏泽",):
    _SD_DATA[_city] = _SD_GRADE_C


# =======================================================================
# 福建（A/B/C 档）
# =======================================================================
_FJ_GRADE_A = (2260.0, 22.0)   # 福州/厦门/莆田/泉州
_FJ_GRADE_B = (2130.0, 20.5)   # 漳州/南平/龙岩/宁德
_FJ_GRADE_C = (1980.0, 19.5)   # 三明
_FJ_DATA: dict[str, tuple[float, float]] = {}
for _city in ("福州", "厦门", "莆田", "泉州"):
    _FJ_DATA[_city] = _FJ_GRADE_A
for _city in ("漳州", "南平", "龙岩", "宁德"):
    _FJ_DATA[_city] = _FJ_GRADE_B
for _city in ("三明",):
    _FJ_DATA[_city] = _FJ_GRADE_C


# =======================================================================
# 四川（A/B/C 档）
# =======================================================================
_SC_GRADE_A = (2100.0, 22.0)   # 成都/绵阳/德阳/乐山
_SC_GRADE_B = (1970.0, 20.5)   # 自贡/攀枝花/泸州/南充/宜宾/达州
_SC_GRADE_C = (1870.0, 19.5)   # 广元/内江/雅安/巴中/资阳/眉山/甘孜/阿坝/凉山
_SC_DATA: dict[str, tuple[float, float]] = {}
for _city in ("成都", "绵阳", "德阳", "乐山"):
    _SC_DATA[_city] = _SC_GRADE_A
for _city in ("自贡", "攀枝花", "泸州", "南充", "宜宾", "达州"):
    _SC_DATA[_city] = _SC_GRADE_B
for _city in ("广元", "内江", "雅安", "巴中", "资阳", "眉山",
              "甘孜", "阿坝", "凉山"):
    _SC_DATA[_city] = _SC_GRADE_C


# =======================================================================
# 湖北（A/B/C/D 档）
# =======================================================================
_HB_GRADE_A = (2010.0, 20.1)   # 武汉
_HB_GRADE_B = (1800.0, 18.0)   # 黄石/十堰/宜昌
_HB_GRADE_C = (1650.0, 16.5)   # 襄阳/鄂州/荆门/孝感/荆州/黄冈/咸宁/随州
_HB_GRADE_D = (1520.0, 15.2)   # 恩施/神农架
_HB_DATA: dict[str, tuple[float, float]] = {}
for _city in ("武汉",):
    _HB_DATA[_city] = _HB_GRADE_A
for _city in ("黄石", "十堰", "宜昌"):
    _HB_DATA[_city] = _HB_GRADE_B
for _city in ("襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈",
              "咸宁", "随州"):
    _HB_DATA[_city] = _HB_GRADE_C
for _city in ("恩施", "神农架"):
    _HB_DATA[_city] = _HB_GRADE_D


# =======================================================================
# 湖南（A/B/C/D 档）
# =======================================================================
_HN_GRADE_A = (2200.0, 22.0)   # 长沙
_HN_GRADE_B = (1930.0, 19.3)   # 株洲/湘潭/衡阳
_HN_GRADE_C = (1740.0, 17.4)   # 邵阳/岳阳/常德/益阳/郴州/永州/怀化/娄底
_HN_GRADE_D = (1650.0, 16.5)   # 张家界/湘西
_HN_DATA: dict[str, tuple[float, float]] = {}
for _city in ("长沙",):
    _HN_DATA[_city] = _HN_GRADE_A
for _city in ("株洲", "湘潭", "衡阳"):
    _HN_DATA[_city] = _HN_GRADE_B
for _city in ("邵阳", "岳阳", "常德", "益阳", "郴州", "永州",
              "怀化", "娄底"):
    _HN_DATA[_city] = _HN_GRADE_C
for _city in ("张家界", "湘西"):
    _HN_DATA[_city] = _HN_GRADE_D


# =======================================================================
# 河南（A/B/C 档）
# =======================================================================
_HEN_GRADE_A = (2000.0, 19.6)  # 郑州/洛阳/开封/平顶山
_HEN_GRADE_B = (1800.0, 17.6)  # 南阳/信阳/周口/安阳/鹤壁/新乡/焦作/濮阳/许昌/漯河/三门峡
_HEN_GRADE_C = (1600.0, 15.6)  # 驻马店/商丘
_HEN_DATA: dict[str, tuple[float, float]] = {}
for _city in ("郑州", "洛阳", "开封", "平顶山"):
    _HEN_DATA[_city] = _HEN_GRADE_A
for _city in ("南阳", "信阳", "周口", "安阳", "鹤壁", "新乡",
              "焦作", "濮阳", "许昌", "漯河", "三门峡"):
    _HEN_DATA[_city] = _HEN_GRADE_B
for _city in ("驻马店", "商丘"):
    _HEN_DATA[_city] = _HEN_GRADE_C


# =======================================================================
# 河北（A/B/C 档）
# =======================================================================
_HE_GRADE_A = (2200.0, 22.0)   # 石家庄/唐山/秦皇岛
_HE_GRADE_B = (2000.0, 20.0)   # 邯郸/邢台/保定/张家口/承德
_HE_GRADE_C = (1800.0, 18.0)   # 沧州/廊坊/衡水
_HE_DATA: dict[str, tuple[float, float]] = {}
for _city in ("石家庄", "唐山", "秦皇岛"):
    _HE_DATA[_city] = _HE_GRADE_A
for _city in ("邯郸", "邢台", "保定", "张家口", "承德"):
    _HE_DATA[_city] = _HE_GRADE_B
for _city in ("沧州", "廊坊", "衡水"):
    _HE_DATA[_city] = _HE_GRADE_C


# =======================================================================
# 江西（A/B 档）
# =======================================================================
_JX_GRADE_A = (1850.0, 18.5)   # 南昌
_JX_GRADE_B = (1730.0, 17.3)   # 赣州/九江/上饶/景德镇/萍乡/新余/鹰潭/抚州/吉安
_JX_DATA: dict[str, tuple[float, float]] = {}
for _city in ("南昌",):
    _JX_DATA[_city] = _JX_GRADE_A
for _city in ("赣州", "九江", "上饶", "景德镇", "萍乡", "新余",
              "鹰潭", "抚州", "吉安"):
    _JX_DATA[_city] = _JX_GRADE_B


# =======================================================================
# 山西（A/B/C 档）
# =======================================================================
_SX_GRADE_A = (2070.0, 20.0)   # 太原
_SX_GRADE_B = (1880.0, 18.0)   # 大同/阳泉/长治/晋城
_SX_GRADE_C = (1700.0, 17.0)   # 朔州/晋中/运城/忻州/临汾/吕梁
_SX_DATA: dict[str, tuple[float, float]] = {}
for _city in ("太原",):
    _SX_DATA[_city] = _SX_GRADE_A
for _city in ("大同", "阳泉", "长治", "晋城"):
    _SX_DATA[_city] = _SX_GRADE_B
for _city in ("朔州", "晋中", "运城", "忻州", "临汾", "吕梁"):
    _SX_DATA[_city] = _SX_GRADE_C


# =======================================================================
# 辽宁（3 档）
# =======================================================================
_LN_GRADE_A = (2220.0, 22.0)   # 沈阳/大连
_LN_GRADE_B = (2060.0, 20.0)   # 鞍山/抚顺/本溪/丹东/锦州/营口
_LN_GRADE_C = (1910.0, 19.0)   # 阜新/辽阳/盘锦/铁岭/朝阳/葫芦岛
_LN_DATA: dict[str, tuple[float, float]] = {}
for _city in ("沈阳", "大连"):
    _LN_DATA[_city] = _LN_GRADE_A
for _city in ("鞍山", "抚顺", "本溪", "丹东", "锦州", "营口"):
    _LN_DATA[_city] = _LN_GRADE_B
for _city in ("阜新", "辽阳", "盘锦", "铁岭", "朝阳", "葫芦岛"):
    _LN_DATA[_city] = _LN_GRADE_C


# =======================================================================
# 吉林（3 档）
# =======================================================================
_JL_GRADE_A = (1880.0, 18.5)   # 长春
_JL_GRADE_B = (1760.0, 17.2)   # 吉林/四平/通化/延边
_JL_GRADE_C = (1640.0, 16.0)   # 白城/松原
_JL_DATA: dict[str, tuple[float, float]] = {}
for _city in ("长春",):
    _JL_DATA[_city] = _JL_GRADE_A
for _city in ("吉林", "四平", "通化", "延边"):
    _JL_DATA[_city] = _JL_GRADE_B
for _city in ("白城", "松原"):
    _JL_DATA[_city] = _JL_GRADE_C


# =======================================================================
# 黑龙江（3 档）
# =======================================================================
_HLJ_GRADE_A = (2010.0, 20.0)  # 哈尔滨
_HLJ_GRADE_B = (1900.0, 18.5)  # 齐齐哈尔/大庆/牡丹江/佳木斯
_HLJ_GRADE_C = (1800.0, 18.0)  # 鸡西/双鸭山/伊春/七台河/鹤岗/绥化/大兴安岭
_HLJ_DATA: dict[str, tuple[float, float]] = {}
for _city in ("哈尔滨",):
    _HLJ_DATA[_city] = _HLJ_GRADE_A
for _city in ("齐齐哈尔", "大庆", "牡丹江", "佳木斯"):
    _HLJ_DATA[_city] = _HLJ_GRADE_B
for _city in ("鸡西", "双鸭山", "伊春", "七台河", "鹤岗",
              "绥化", "大兴安岭"):
    _HLJ_DATA[_city] = _HLJ_GRADE_C


# =======================================================================
# 陕西（A/B 档）
# =======================================================================
_SXAN_GRADE_A = (2160.0, 21.0)  # 西安/咸阳/渭南/延安
_SXAN_GRADE_B = (2000.0, 20.0)  # 宝鸡/铜川/榆林/安康/商洛
_SXAN_DATA: dict[str, tuple[float, float]] = {}
for _city in ("西安", "咸阳", "渭南", "延安"):
    _SXAN_DATA[_city] = _SXAN_GRADE_A
for _city in ("宝鸡", "铜川", "榆林", "安康", "商洛"):
    _SXAN_DATA[_city] = _SXAN_GRADE_B


# =======================================================================
# 云南（A/B/C 档）
# =======================================================================
_YN_GRADE_A = (1990.0, 19.0)   # 昆明
_YN_GRADE_B = (1840.0, 18.0)   # 曲靖/玉溪/大理
_YN_GRADE_C = (1690.0, 16.0)   # 昭通/丽江/普洱/保山/临沧/西双版纳/楚雄/红河/文山/怒江/迪庆
_YN_DATA: dict[str, tuple[float, float]] = {}
for _city in ("昆明",):
    _YN_DATA[_city] = _YN_GRADE_A
for _city in ("曲靖", "玉溪", "大理"):
    _YN_DATA[_city] = _YN_GRADE_B
for _city in ("昭通", "丽江", "普洱", "保山", "临沧", "西双版纳",
              "楚雄", "红河", "文山", "怒江", "迪庆"):
    _YN_DATA[_city] = _YN_GRADE_C


# =======================================================================
# 贵州（A/B/C 档）
# =======================================================================
_GZ_GRADE_A = (1980.0, 19.8)   # 贵阳
_GZ_GRADE_B = (1830.0, 18.3)   # 遵义/六盘水/安顺
_GZ_GRADE_C = (1680.0, 16.8)   # 毕节/铜仁/黔东南/黔南/黔西南
_GZ_DATA: dict[str, tuple[float, float]] = {}
for _city in ("贵阳",):
    _GZ_DATA[_city] = _GZ_GRADE_A
for _city in ("遵义", "六盘水", "安顺"):
    _GZ_DATA[_city] = _GZ_GRADE_B
for _city in ("毕节", "铜仁", "黔东南", "黔南", "黔西南"):
    _GZ_DATA[_city] = _GZ_GRADE_C


# =======================================================================
# 广西（A/B/C 档）
# =======================================================================
_GX_GRADE_A = (2010.0, 20.0)   # 南宁/柳州/桂林/梧州
_GX_GRADE_B = (1810.0, 18.0)   # 北海/防城港/钦州/贵港/玉林
_GX_GRADE_C = (1610.0, 16.0)   # 百色/贺州/河池/来宾/崇左
_GX_DATA: dict[str, tuple[float, float]] = {}
for _city in ("南宁", "柳州", "桂林", "梧州"):
    _GX_DATA[_city] = _GX_GRADE_A
for _city in ("北海", "防城港", "钦州", "贵港", "玉林"):
    _GX_DATA[_city] = _GX_GRADE_B
for _city in ("百色", "贺州", "河池", "来宾", "崇左"):
    _GX_DATA[_city] = _GX_GRADE_C


# =======================================================================
# 海南：全省统一
# =======================================================================
_HI_GRADE1 = (2010.0, 20.0)
_HI_DATA: dict[str, tuple[float, float]] = {}
for _city in ("海口", "三亚", "三沙", "儋州"):
    _HI_DATA[_city] = _HI_GRADE1


# =======================================================================
# 内蒙古（3 档）
# =======================================================================
_NMG_GRADE_A = (2270.0, 22.0)  # 呼和浩特/包头/鄂尔多斯
_NMG_GRADE_B = (2100.0, 20.0)  # 乌海/赤峰/通辽/呼伦贝尔
_NMG_GRADE_C = (1900.0, 19.0)  # 乌兰察布/兴安盟/锡林郭勒/阿拉善/巴彦淖尔
_NMG_DATA: dict[str, tuple[float, float]] = {}
for _city in ("呼和浩特", "包头", "鄂尔多斯"):
    _NMG_DATA[_city] = _NMG_GRADE_A
for _city in ("乌海", "赤峰", "通辽", "呼伦贝尔"):
    _NMG_DATA[_city] = _NMG_GRADE_B
for _city in ("乌兰察布", "兴安盟", "锡林郭勒", "阿拉善", "巴彦淖尔"):
    _NMG_DATA[_city] = _NMG_GRADE_C


# =======================================================================
# 新疆（3 档）
# =======================================================================
_XJ_GRADE_A = (1900.0, 19.0)   # 乌鲁木齐/昌吉/石河子
_XJ_GRADE_B = (1700.0, 17.0)   # 克拉玛依/吐鲁番/哈密/巴音郭楞
_XJ_GRADE_C = (1500.0, 15.0)   # 阿克苏/喀什/和田/伊犁/塔城/阿勒泰/克州/博尔塔拉
_XJ_DATA: dict[str, tuple[float, float]] = {}
for _city in ("乌鲁木齐", "昌吉", "石河子"):
    _XJ_DATA[_city] = _XJ_GRADE_A
for _city in ("克拉玛依", "吐鲁番", "哈密", "巴音郭楞"):
    _XJ_DATA[_city] = _XJ_GRADE_B
for _city in ("阿克苏", "喀什", "和田", "伊犁", "塔城",
              "阿勒泰", "克州", "博尔塔拉"):
    _XJ_DATA[_city] = _XJ_GRADE_C


# =======================================================================
# 宁夏（A/B 档）
# =======================================================================
_NX_GRADE_A = (1980.0, 19.5)   # 银川
_NX_GRADE_B = (1840.0, 18.0)   # 石嘴山/吴忠/固原/中卫
_NX_DATA: dict[str, tuple[float, float]] = {}
for _city in ("银川",):
    _NX_DATA[_city] = _NX_GRADE_A
for _city in ("石嘴山", "吴忠", "固原", "中卫"):
    _NX_DATA[_city] = _NX_GRADE_B


# =======================================================================
# 甘肃（3 档）
# =======================================================================
_GS_GRADE_A = (1820.0, 18.0)   # 兰州
_GS_GRADE_B = (1700.0, 17.0)   # 天水/白银/酒泉
_GS_GRADE_C = (1600.0, 16.0)   # 张掖/武威/定西/陇南/平凉/庆阳/临夏/甘南
_GS_DATA: dict[str, tuple[float, float]] = {}
for _city in ("兰州",):
    _GS_DATA[_city] = _GS_GRADE_A
for _city in ("天水", "白银", "酒泉"):
    _GS_DATA[_city] = _GS_GRADE_B
for _city in ("张掖", "武威", "定西", "陇南", "平凉", "庆阳", "临夏", "甘南"):
    _GS_DATA[_city] = _GS_GRADE_C


# =======================================================================
# 青海（2 档）
# =======================================================================
_QH_GRADE_A = (1880.0, 18.0)   # 西宁/海东
_QH_GRADE_B = (1700.0, 17.0)   # 海北/黄南/海南/果洛/玉树/海西
_QH_DATA: dict[str, tuple[float, float]] = {}
for _city in ("西宁", "海东"):
    _QH_DATA[_city] = _QH_GRADE_A
for _city in ("海北", "黄南", "海南", "果洛", "玉树", "海西"):
    _QH_DATA[_city] = _QH_GRADE_B


# =======================================================================
# 西藏（2 档）
# =======================================================================
_XZ_GRADE_A = (1850.0, 18.0)   # 拉萨/日喀则/昌都/林芝
_XZ_GRADE_B = (1750.0, 17.5)   # 山南/那曲/阿里
_XZ_DATA: dict[str, tuple[float, float]] = {}
for _city in ("拉萨", "日喀则", "昌都", "林芝"):
    _XZ_DATA[_city] = _XZ_GRADE_A
for _city in ("山南", "那曲", "阿里"):
    _XZ_DATA[_city] = _XZ_GRADE_B


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


def has_province(name: str) -> bool:
    return name in _REGION_DATA


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
# 策略：先试 API（已配置的情况），失败或未配置 → 自动 fallback 到本地静态表。
# 省/市数据在上方 _XX_DATA / _XX_GRADEn 分块中定义，可随时编辑修改数值。
# api_model：OpenAI 兼容服务的模型名（DeepSeek / 通义 / Kimi / 智谱 等，
#   在「API 设置」里按服务商选择/填写），未配置时用 DEFAULT_API_MODEL。

# 未在「API 设置」中指定模型名时的默认模型（兼容旧配置）
DEFAULT_API_MODEL = "agnes-2.5-flash"


def _chat_model(api_model: str | None) -> str:
    """返回实际请求用的模型名：配置值优先，空则用默认。"""
    return (api_model or "").strip() or DEFAULT_API_MODEL


def fetch(api_url: str | None, api_key: str | None,
          year: int, month: int, province: str, region: str,
          api_model: str | None = None) -> dict | None:
    """查询指定年月的最低工资。优先级：
    1. 已配置 API → 先试 Chat API（prompt 带 year/month）
    2. 未配置 API 或 API 失败 → fallback 本地静态表
    返回 dict {"min_wage": float, "parttime_min": float, "source": "api"|"local"} 或 None。
    """
    # 1. 先试 API
    api_result = None
    if api_url and api_key:
        api_result = _try_chat_api(api_url, api_key, year, month, province, region,
                                   api_model=api_model)
    if api_result is not None:
        return api_result
    # 2. fallback 本地静态表
    local = get(province, region)
    if local is not None:
        return {"min_wage": local[0], "parttime_min": local[1], "source": "local"}
    return None


def _try_chat_api(api_url: str, api_key: str,
                  year: int, month: int, province: str, region: str,
                  api_model: str | None = None) -> dict | None:
    """单次 Chat API 调用。prompt 包含用户选择的年份/月份。失败返回 None。"""
    try:
        import ssl
        import urllib.request
        import json as _json
        endpoint = api_url.rstrip("/") + "/chat/completions"
        # 安全防线：仅允许 HTTPS，强制校验证书，防止中间人窃取 Bearer Token
        if not endpoint.lower().startswith("https://"):
            return None
        prompt = (
            f"请查询中国 {province} {region} {year} 年 {month} 月的最低工资标准。"
            f"返回一个 JSON 对象，只包含两个数值字段：min_wage（月最低工资，单位元）和 parttime_min（非全日制小时最低工资，单位元）。"
            f"如果找不到 {year} 年 {month} 月的官方发布标准，就用该地区在 {year} 年 {month} 月实际有效的最新标准。"
            f"直接返回 JSON，不要任何解释、不要 markdown、不要代码块。"
        )
        payload = {
            "model": _chat_model(api_model),
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = _json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
        ctx = ssl.create_default_context()  # 默认启用 hostname 检查 + 证书链校验
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            body = _json.loads(resp.read().decode("utf-8"))
        choices = body.get("choices") or []
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "")
        if not content:
            return None
        import re
        m = re.search(r"\{[^}]+\}", content, re.DOTALL)
        raw_json = m.group(0) if m else content.strip()
        parsed = _json.loads(raw_json)
        mw = float(parsed.get("min_wage") or 0)
        ph = float(parsed.get("parttime_min") or 0)
        if mw <= 0 or ph <= 0:
            return None
        return {"min_wage": mw, "parttime_min": ph, "source": "api"}
    except Exception:
        return None


# —— 节假日 API：独立于最低工资 API，复用相同连接信息 ——
# 返回结构：{
#   "statutory": ["MM-DD", ...],   # 法定节假日（加班×3，mark=1）
#   "rest": ["MM-DD", ...],        # 放假调休区间（含法定日与拼假休息日，status=休息）
#   "makeup": ["MM-DD", ...],      # 调休补班日（周末上班，status=上班）
#   "source": "api"|"local"
# }
# 未配置 API 或 API 失败时，返回本地 holidays.py 数据作 fallback。


def fetch_holidays(api_url: str | None, api_key: str | None,
                   year: int, api_model: str | None = None) -> dict | None:
    """查询某年的法定节假日/放假调休/补班日。
    优先级：已配置 API 先试 → 失败 fallback 到本地 holidays.py。
    """
    # 1. 先试 API
    if api_url and api_key:
        r = _try_holiday_api(api_url, api_key, year, api_model=api_model)
        if r is not None:
            return r
    # 2. fallback 本地静态表
    return _holidays_from_local(year)


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


def _try_holiday_api(api_url: str, api_key: str, year: int,
                     api_model: str | None = None) -> dict | None:
    """调用 Chat API 查询某年中国法定节假日安排；失败返回 None。"""
    try:
        import ssl
        import urllib.request
        import json as _json
        endpoint = api_url.rstrip("/") + "/chat/completions"
        if not endpoint.lower().startswith("https://"):
            return None
        prompt = (
            f"请查询中国国务院办公厅发布的 {year} 年法定节假日放假安排（含每个节假日的"
            f"法定日、放假调休区间、调休补班日）。"
            "返回一个 JSON 对象，只包含三个数组字段："
            "1) statutory：数组，每项为 MM-DD 格式的法定节假日日期（×3加班的那一天）。"
            "2) rest：数组，每项为 MM-DD 格式的放假调休日（包括法定日和拼假休息日）。"
            "3) makeup：数组，每项为 MM-DD 格式的调休补班日（原本是周末但需要上班的日子）。"
            "严格基于官方发布的安排，不要臆造。直接返回 JSON，不要任何解释、不要 markdown、不要代码块。"
        )
        payload = {
            "model": _chat_model(api_model),
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = _json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            body = _json.loads(resp.read().decode("utf-8"))
        choices = body.get("choices") or []
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "")
        if not content:
            return None
        # 提取 JSON 块（兼容 ```json ``` 包装）
        import re as _re
        m = _re.search(r"\{[\s\S]*\}", content)
        raw_json = m.group(0) if m else content.strip()
        parsed = _json.loads(raw_json)
        result = {}
        for key in ("statutory", "rest", "makeup"):
            arr = parsed.get(key) or []
            if not isinstance(arr, list):
                return None
            # 规范化成 MM-DD 格式，过滤无效项
            clean = []
            for s in arr:
                s = str(s).strip()
                if not s:
                    continue
                if "/" in s:
                    s = s.replace("/", "-")
                parts = s.split("-")
                if len(parts) == 2:
                    mm, dd = parts
                elif len(parts) == 3:
                    mm, dd = parts[1], parts[2]
                else:
                    continue
                try:
                    clean.append(f"{int(mm):02d}-{int(dd):02d}")
                except ValueError:
                    continue
            result[key] = clean
        if not result["statutory"] and not result["rest"] and not result["makeup"]:
            return None
        result["source"] = "api"
        return result
    except Exception:
        return None


def test_connection(api_url: str | None, api_key: str | None,
                    api_model: str | None = None) -> tuple[bool, str]:
    """向配置的 OpenAI 兼容服务发一条最小消息，验证能否连通。

    返回 (True, "连接成功（xxx ms · 模型 xxx）") 或 (False, 具体原因)。
    供「API 设置」里的「测试连接」使用：能直接看出 Key 无效 / 模型名不对 /
    接口地址错 / 超时等问题。仅支持 https（当前版本不接本地 http 服务）。
    """
    import json as _json
    import socket
    import ssl
    import time
    import urllib.error
    import urllib.request

    endpoint = (api_url or "").rstrip("/") + "/chat/completions"
    if not endpoint.lower().startswith("https://"):
        return False, "API 地址必须以 https:// 开头（当前版本不支持 http 本地服务）"
    model = _chat_model(api_model)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请只回复：ok"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    data = _json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
    ctx = ssl.create_default_context()
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            ms = int((time.monotonic() - start) * 1000)
            try:
                body = _json.loads(resp.read().decode("utf-8"))
            except Exception:
                return False, "返回内容不是有效 JSON，可能不是 OpenAI 兼容的 /chat/completions 端点"
            choices = body.get("choices") or []
            if not choices:
                return False, "返回 200 但无 choices 字段，可能不是兼容的 chat 接口"
            return True, f"连接成功（{ms} ms · 模型 {model}）"
    except urllib.error.HTTPError as e:
        code = e.code
        if code == 401:
            return False, "API Key 无效（401）"
        if code == 403:
            return False, "API Key 无权访问该模型（403）"
        if code == 404:
            return False, "接口地址或模型名不正确（404），请检查 API 地址与模型名"
        if code == 429:
            return False, "调用频率超限（429）"
        if code >= 500:
            return False, f"服务器错误：{code}"
        return False, f"HTTP 错误：{code}"
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        msg = str(reason)
        if isinstance(reason, socket.timeout) or "timed out" in msg.lower():
            return False, "连接超时，请检查网络或 API 地址"
        if isinstance(reason, ssl.SSLError) or "ssl" in msg.lower() or "certificate" in msg.lower():
            return False, f"TLS/证书校验失败：{reason}"
        return False, f"网络请求失败：{reason}"
    except Exception as e:  # noqa: BLE001
        return False, f"网络请求失败：{e}"
