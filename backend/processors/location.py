from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional, Any

_LATIN_RE = re.compile(r"[a-zA-Z]")


@lru_cache(maxsize=None)
def _latin_variant_pattern(variant: str) -> re.Pattern[str]:
    return re.compile(r"\b" + re.escape(variant) + r"\b")


def _variant_pos(text: str, variant: str) -> int | None:
    """Position of variant in text, or None.

    Word-boundary matching for Latin-script variants avoids false
    matches like "Iran" inside "transiranian".  Substring matching
    for CJK variants since \\b doesn't work with Chinese characters.
    """
    if _LATIN_RE.search(variant):
        m = _latin_variant_pattern(variant).search(text)
        return m.start() if m else None
    idx = text.find(variant)
    return idx if idx != -1 else None


# City-level database: (country, city, variants_list, lat, lng)
# Cities are scanned first, then countries as fallback.
_CITIES: list[dict] = [
    # ── 中国 ──
    {"country": "中国", "city": "北京", "variants": ["北京", "Beijing", "Peking"], "lat": 39.9042, "lng": 116.4074},
    {"country": "中国", "city": "上海", "variants": ["上海", "Shanghai"], "lat": 31.2304, "lng": 121.4737},
    {"country": "中国", "city": "深圳", "variants": ["深圳", "Shenzhen"], "lat": 22.5431, "lng": 114.0579},
    {"country": "中国", "city": "广州", "variants": ["广州", "Guangzhou", "Canton"], "lat": 23.1291, "lng": 113.2644},
    {"country": "中国", "city": "香港", "variants": ["香港", "Hong Kong"], "lat": 22.3193, "lng": 114.1694},
    {"country": "中国", "city": "成都", "variants": ["成都", "Chengdu"], "lat": 30.5728, "lng": 104.0668},
    {"country": "中国", "city": "武汉", "variants": ["武汉", "Wuhan"], "lat": 30.5928, "lng": 114.3055},
    {"country": "中国", "city": "重庆", "variants": ["重庆", "Chongqing", "Chungking"], "lat": 29.4316, "lng": 106.9123},
    {"country": "中国", "city": "南京", "variants": ["南京", "Nanjing", "Nanking"], "lat": 32.0603, "lng": 118.7969},
    {"country": "中国", "city": "杭州", "variants": ["杭州", "Hangzhou"], "lat": 30.2741, "lng": 120.1551},
    {"country": "中国", "city": "西安", "variants": ["西安", "Xi'an", "Xian"], "lat": 34.3416, "lng": 108.9398},
    {"country": "中国", "city": "苏州", "variants": ["苏州", "Suzhou"], "lat": 31.2990, "lng": 120.5853},
    {"country": "中国", "city": "天津", "variants": ["天津", "Tianjin", "Tientsin"], "lat": 39.3434, "lng": 117.3616},
    {"country": "中国", "city": "长沙", "variants": ["长沙", "Changsha"], "lat": 28.2282, "lng": 112.9388},
    {"country": "中国", "city": "郑州", "variants": ["郑州", "Zhengzhou"], "lat": 34.7466, "lng": 113.6254},
    {"country": "中国", "city": "青岛", "variants": ["青岛", "Qingdao", "Tsingtao"], "lat": 36.0671, "lng": 120.3826},
    {"country": "中国", "city": "大连", "variants": ["大连", "Dalian"], "lat": 38.9140, "lng": 121.6147},
    {"country": "中国", "city": "厦门", "variants": ["厦门", "Xiamen", "Amoy"], "lat": 24.4798, "lng": 118.0894},
    {"country": "中国", "city": "宁波", "variants": ["宁波", "Ningbo"], "lat": 29.8746, "lng": 121.5485},
    {"country": "中国", "city": "无锡", "variants": ["无锡", "Wuxi"], "lat": 31.4912, "lng": 120.3119},
    {"country": "中国", "city": "合肥", "variants": ["合肥", "Hefei"], "lat": 31.8206, "lng": 117.2272},
    {"country": "中国", "city": "福州", "variants": ["福州", "Fuzhou"], "lat": 26.0745, "lng": 119.2965},
    {"country": "中国", "city": "济南", "variants": ["济南", "Jinan"], "lat": 36.6512, "lng": 117.1201},
    {"country": "中国", "city": "哈尔滨", "variants": ["哈尔滨", "Harbin"], "lat": 45.8038, "lng": 126.5350},
    {"country": "中国", "city": "沈阳", "variants": ["沈阳", "Shenyang"], "lat": 41.8045, "lng": 123.4315},
    {"country": "中国", "city": "长春", "variants": ["长春", "Changchun"], "lat": 43.8868, "lng": 125.3245},
    {"country": "中国", "city": "石家庄", "variants": ["石家庄", "Shijiazhuang"], "lat": 38.0423, "lng": 114.5143},
    {"country": "中国", "city": "南昌", "variants": ["南昌", "Nanchang"], "lat": 28.6765, "lng": 115.9101},
    {"country": "中国", "city": "南宁", "variants": ["南宁", "Nanning"], "lat": 22.8154, "lng": 108.3275},
    {"country": "中国", "city": "昆明", "variants": ["昆明", "Kunming"], "lat": 25.0296, "lng": 102.7103},
    {"country": "中国", "city": "贵阳", "variants": ["贵阳", "Guiyang"], "lat": 26.6470, "lng": 106.6302},
    {"country": "中国", "city": "兰州", "variants": ["兰州", "Lanzhou"], "lat": 36.0617, "lng": 103.8343},
    {"country": "中国", "city": "乌鲁木齐", "variants": ["乌鲁木齐", "Urumqi", "Urumchi"], "lat": 43.8256, "lng": 87.6168},
    {"country": "中国", "city": "呼和浩特", "variants": ["呼和浩特", "Hohhot"], "lat": 40.8414, "lng": 111.7519},
    {"country": "中国", "city": "银川", "variants": ["银川", "Yinchuan"], "lat": 38.4874, "lng": 106.2301},
    {"country": "中国", "city": "西宁", "variants": ["西宁", "Xining"], "lat": 36.6171, "lng": 101.7782},
    {"country": "中国", "city": "拉萨", "variants": ["拉萨", "Lhasa"], "lat": 29.6517, "lng": 91.1727},
    {"country": "中国", "city": "海口", "variants": ["海口", "Haikou"], "lat": 20.0442, "lng": 110.1999},
    {"country": "中国", "city": "三亚", "variants": ["三亚", "Sanya"], "lat": 18.2528, "lng": 109.5119},
    {"country": "中国", "city": "台北", "variants": ["台北", "Taipei"], "lat": 25.0330, "lng": 121.5654},
    {"country": "中国", "city": "澳门", "variants": ["澳门", "Macau", "Macao"], "lat": 22.1987, "lng": 113.5439},
    {"country": "中国", "city": "珠海", "variants": ["珠海", "Zhuhai"], "lat": 22.2707, "lng": 113.5767},
    {"country": "中国", "city": "东莞", "variants": ["东莞", "Dongguan"], "lat": 23.0207, "lng": 113.7516},
    {"country": "中国", "city": "佛山", "variants": ["佛山", "Foshan"], "lat": 23.0218, "lng": 113.1218},
    {"country": "中国", "city": "中山", "variants": ["中山", "Zhongshan"], "lat": 22.5165, "lng": 113.3928},
    {"country": "中国", "city": "惠州", "variants": ["惠州", "Huizhou"], "lat": 23.1107, "lng": 114.4179},
    {"country": "中国", "city": "温州", "variants": ["温州", "Wenzhou"], "lat": 27.9948, "lng": 120.6995},
    {"country": "中国", "city": "常州", "variants": ["常州", "Changzhou"], "lat": 31.8112, "lng": 119.9740},
    {"country": "中国", "city": "南通", "variants": ["南通", "Nantong"], "lat": 31.9802, "lng": 120.8938},
    {"country": "中国", "city": "徐州", "variants": ["徐州", "Xuzhou"], "lat": 34.1991, "lng": 117.2856},
    {"country": "中国", "city": "扬州", "variants": ["扬州", "Yangzhou"], "lat": 32.3945, "lng": 119.4129},
    {"country": "中国", "city": "镇江", "variants": ["镇江", "Zhenjiang"], "lat": 32.1966, "lng": 119.4451},
    {"country": "中国", "city": "绍兴", "variants": ["绍兴", "Shaoxing"], "lat": 30.0341, "lng": 120.5803},
    {"country": "中国", "city": "嘉兴", "variants": ["嘉兴", "Jiaxing"], "lat": 30.7469, "lng": 120.5008},
    {"country": "中国", "city": "湖州", "variants": ["湖州", "Huzhou"], "lat": 30.8946, "lng": 120.1027},
    {"country": "中国", "city": "金华", "variants": ["金华", "Jinhua"], "lat": 29.0895, "lng": 119.6474},
    {"country": "中国", "city": "台州", "variants": ["台州", "Taizhou"], "lat": 28.6564, "lng": 121.4201},
    {"country": "中国", "city": "丽水", "variants": ["丽水", "Lishui"], "lat": 28.4672, "lng": 119.9228},
    {"country": "中国", "city": "衢州", "variants": ["衢州", "Quzhou"], "lat": 28.9346, "lng": 118.8788},
    {"country": "中国", "city": "舟山", "variants": ["舟山", "Zhoushan"], "lat": 29.9897, "lng": 122.2062},
    {"country": "中国", "city": "马鞍山", "variants": ["马鞍山", "Ma'anshan"], "lat": 31.6654, "lng": 118.5073},
    {"country": "中国", "city": "芜湖", "variants": ["芜湖", "Wuhu"], "lat": 31.3665, "lng": 118.3853},
    {"country": "中国", "city": "安庆", "variants": ["安庆", "Anqing"], "lat": 30.5020, "lng": 117.0312},
    {"country": "中国", "city": "蚌埠", "variants": ["蚌埠", "Bengbu"], "lat": 32.9235, "lng": 117.3821},
    {"country": "中国", "city": "阜阳", "variants": ["阜阳", "Fuyang"], "lat": 32.8907, "lng": 115.8158},
    {"country": "中国", "city": "宿州", "variants": ["宿州", "Suzhou"], "lat": 33.6562, "lng": 116.9802},
    {"country": "中国", "city": "六安", "variants": ["六安", "Lu'an"], "lat": 31.7532, "lng": 116.5216},
    {"country": "中国", "city": "亳州", "variants": ["亳州", "Bozhou"], "lat": 33.8443, "lng": 115.7791},
    {"country": "中国", "city": "池州", "variants": ["池州", "Chizhou"], "lat": 30.6592, "lng": 117.4912},
    {"country": "中国", "city": "宣城", "variants": ["宣城", "Xuancheng"], "lat": 30.9415, "lng": 118.7583},
    {"country": "中国", "city": "铜陵", "variants": ["铜陵", "Tongling"], "lat": 30.9461, "lng": 117.8160},
    {"country": "中国", "city": "淮北", "variants": ["淮北", "Huaibei"], "lat": 33.9588, "lng": 116.7853},
    {"country": "中国", "city": "淮南", "variants": ["淮南", "Huainan"], "lat": 32.6347, "lng": 116.9928},
    {"country": "中国", "city": "黄山", "variants": ["黄山", "Huangshan"], "lat": 29.7165, "lng": 118.3385},
    {"country": "中国", "city": "滁州", "variants": ["滁州", "Chuzhou"], "lat": 32.3065, "lng": 118.3154},
    {"country": "中国", "city": "阜阳", "variants": ["阜阳", "Fuyang"], "lat": 32.8907, "lng": 115.8158},
    {"country": "中国", "city": "景德镇", "variants": ["景德镇", "Jingdezhen"], "lat": 29.2901, "lng": 117.2188},
    {"country": "中国", "city": "萍乡", "variants": ["萍乡", "Pingxiang"], "lat": 27.6251, "lng": 113.8513},
    {"country": "中国", "city": "九江", "variants": ["九江", "Jiujiang"], "lat": 29.7000, "lng": 115.9928},
    {"country": "中国", "city": "新余", "variants": ["新余", "Xinyu"], "lat": 27.8151, "lng": 114.9341},
    {"country": "中国", "city": "鹰潭", "variants": ["鹰潭", "Yingtan"], "lat": 28.2525, "lng": 117.0304},
    {"country": "中国", "city": "赣州", "variants": ["赣州", "Ganzhou"], "lat": 25.8544, "lng": 114.9289},
    {"country": "中国", "city": "宜春", "variants": ["宜春", "Yichun"], "lat": 27.8151, "lng": 114.3911},
    {"country": "中国", "city": "上饶", "variants": ["上饶", "Shangrao"], "lat": 28.4554, "lng": 117.9429},
    {"country": "中国", "city": "吉安", "variants": ["吉安", "Ji'an"], "lat": 27.1117, "lng": 114.9841},
    {"country": "中国", "city": "抚州", "variants": ["抚州", "Fuzhou"], "lat": 27.9811, "lng": 116.3599},
    {"country": "中国", "city": "湘潭", "variants": ["湘潭", "Xiangtan"], "lat": 27.8314, "lng": 112.9449},
    {"country": "中国", "city": "株洲", "variants": ["株洲", "Zhuzhou"], "lat": 27.8314, "lng": 113.1514},
    {"country": "中国", "city": "衡阳", "variants": ["衡阳", "Hengyang"], "lat": 26.8932, "lng": 112.5704},
    {"country": "中国", "city": "邵阳", "variants": ["邵阳", "Shaoyang"], "lat": 27.2555, "lng": 111.4714},
    {"country": "中国", "city": "岳阳", "variants": ["岳阳", "Yueyang"], "lat": 29.3607, "lng": 113.1359},
    {"country": "中国", "city": "常德", "variants": ["常德", "Changde"], "lat": 29.0195, "lng": 111.6797},
    {"country": "中国", "city": "张家界", "variants": ["张家界", "Zhangjiajie"], "lat": 29.1167, "lng": 110.4800},
    {"country": "中国", "city": "益阳", "variants": ["益阳", "Yiyang"], "lat": 28.5701, "lng": 112.3640},
    {"country": "中国", "city": "郴州", "variants": ["郴州", "Chenzhou"], "lat": 25.7915, "lng": 113.0350},
    {"country": "中国", "city": "永州", "variants": ["永州", "Yongzhou"], "lat": 26.4264, "lng": 111.6108},
    {"country": "中国", "city": "怀化", "variants": ["怀化", "Huaihua"], "lat": 27.5551, "lng": 109.9760},
    {"country": "中国", "city": "娄底", "variants": ["娄底", "Loudi"], "lat": 27.7015, "lng": 112.0045},
    {"country": "中国", "city": "湘西", "variants": ["湘西", "Xiangxi"], "lat": 28.3071, "lng": 109.7386},
    {"country": "中国", "city": "韶关", "variants": ["韶关", "Shaoguan"], "lat": 24.7836, "lng": 113.5971},
    {"country": "中国", "city": "汕头", "variants": ["汕头", "Shantou"], "lat": 23.3541, "lng": 116.6860},
    {"country": "中国", "city": "湛江", "variants": ["湛江", "Zhanjiang"], "lat": 21.2741, "lng": 110.3535},
    {"country": "中国", "city": "茂名", "variants": ["茂名", "Maoming"], "lat": 21.6580, "lng": 110.9147},
    {"country": "中国", "city": "肇庆", "variants": ["肇庆", "Zhaoqing"], "lat": 23.0469, "lng": 112.4642},
    {"country": "中国", "city": "江门", "variants": ["江门", "Jiangmen"], "lat": 22.5948, "lng": 113.0800},
    {"country": "中国", "city": "阳江", "variants": ["阳江", "Yangjiang"], "lat": 21.8585, "lng": 111.9776},
    {"country": "中国", "city": "清远", "variants": ["清远", "Qingyuan"], "lat": 23.6850, "lng": 113.0633},
    {"country": "中国", "city": "东莞", "variants": ["东莞", "Dongguan"], "lat": 23.0207, "lng": 113.7516},
    {"country": "中国", "city": "潮州", "variants": ["潮州", "Chaozhou"], "lat": 23.6617, "lng": 116.6389},
    {"country": "中国", "city": "揭阳", "variants": ["揭阳", "Jieyang"], "lat": 23.5491, "lng": 116.3665},
    {"country": "中国", "city": "云浮", "variants": ["云浮", "Yunfu"], "lat": 22.9314, "lng": 112.0365},
    {"country": "中国", "city": "南宁", "variants": ["南宁", "Nanning"], "lat": 22.8154, "lng": 108.3275},
    {"country": "中国", "city": "柳州", "variants": ["柳州", "Liuzhou"], "lat": 24.3183, "lng": 109.4025},
    {"country": "中国", "city": "桂林", "variants": ["桂林", "Guilin"], "lat": 25.2741, "lng": 110.2993},
    {"country": "中国", "city": "梧州", "variants": ["梧州", "Wuzhou"], "lat": 23.4818, "lng": 111.2977},
    {"country": "中国", "city": "北海", "variants": ["北海", "Beihai"], "lat": 21.4815, "lng": 109.1194},
    {"country": "中国", "city": "钦州", "variants": ["钦州", "Qinzhou"], "lat": 21.9604, "lng": 108.6405},
    {"country": "中国", "city": "贵港", "variants": ["贵港", "Guigang"], "lat": 23.1122, "lng": 109.6054},
    {"country": "中国", "city": "玉林", "variants": ["玉林", "Yulin"], "lat": 22.6303, "lng": 110.1540},
    {"country": "中国", "city": "百色", "variants": ["百色", "Baise"], "lat": 23.9005, "lng": 106.6157},
    {"country": "中国", "city": "贺州", "variants": ["贺州", "Hezhou"], "lat": 24.4122, "lng": 111.5519},
    {"country": "中国", "city": "河池", "variants": ["河池", "Hechi"], "lat": 24.6937, "lng": 108.0776},
    {"country": "中国", "city": "来宾", "variants": ["来宾", "Laibin"], "lat": 23.7607, "lng": 109.2260},
    {"country": "中国", "city": "崇左", "variants": ["崇左", "Chongzuo"], "lat": 22.3816, "lng": 107.3605},
    {"country": "中国", "city": "海口", "variants": ["海口", "Haikou"], "lat": 20.0442, "lng": 110.1999},
    {"country": "中国", "city": "成都", "variants": ["成都", "Chengdu"], "lat": 30.5728, "lng": 104.0668},
    {"country": "中国", "city": "自贡", "variants": ["自贡", "Zigong"], "lat": 29.3390, "lng": 104.7784},
    {"country": "中国", "city": "攀枝花", "variants": ["攀枝花", "Panzhihua"], "lat": 26.5528, "lng": 101.7184},
    {"country": "中国", "city": "泸州", "variants": ["泸州", "Luzhou"], "lat": 28.8721, "lng": 105.4431},
    {"country": "中国", "city": "德阳", "variants": ["德阳", "Deyang"], "lat": 31.1268, "lng": 104.3978},
    {"country": "中国", "city": "绵阳", "variants": ["绵阳", "Mianyang"], "lat": 31.4810, "lng": 104.6800},
    {"country": "中国", "city": "广元", "variants": ["广元", "Guangyuan"], "lat": 32.4413, "lng": 105.8444},
    {"country": "中国", "city": "遂宁", "variants": ["遂宁", "Suining"], "lat": 30.5347, "lng": 105.5916},
    {"country": "中国", "city": "内江", "variants": ["内江", "Neijiang"], "lat": 29.5831, "lng": 105.0571},
    {"country": "中国", "city": "乐山", "variants": ["乐山", "Leshan"], "lat": 29.5559, "lng": 103.7655},
    {"country": "中国", "city": "南充", "variants": ["南充", "Nanchong"], "lat": 30.8378, "lng": 106.1107},
    {"country": "中国", "city": "眉山", "variants": ["眉山", "Meishan"], "lat": 30.0810, "lng": 103.8627},
    {"country": "中国", "city": "宜宾", "variants": ["宜宾", "Yibin"], "lat": 28.7519, "lng": 104.6302},
    {"country": "中国", "city": "广安", "variants": ["广安", "Guang'an"], "lat": 30.4637, "lng": 106.6326},
    {"country": "中国", "city": "达州", "variants": ["达州", "Dazhou"], "lat": 31.2165, "lng": 107.4720},
    {"country": "中国", "city": "雅安", "variants": ["雅安", "Ya'an"], "lat": 29.9897, "lng": 103.0208},
    {"country": "中国", "city": "巴中", "variants": ["巴中", "Bazhong"], "lat": 31.8593, "lng": 106.7637},
    {"country": "中国", "city": "资阳", "variants": ["资阳", "Ziyang"], "lat": 30.1252, "lng": 104.6392},
    {"country": "中国", "city": "阿坝", "variants": ["阿坝", "Aba"], "lat": 31.8982, "lng": 102.2213},
    {"country": "中国", "city": "甘孜", "variants": ["甘孜", "Ganzi"], "lat": 30.0516, "lng": 101.9603},
    {"country": "中国", "city": "凉山", "variants": ["凉山", "Liangshan"], "lat": 27.8819, "lng": 102.2681},
    {"country": "中国", "city": "贵阳", "variants": ["贵阳", "Guiyang"], "lat": 26.6470, "lng": 106.6302},
    {"country": "中国", "city": "六盘水", "variants": ["六盘水", "Liupanshui"], "lat": 26.5959, "lng": 104.8359},
    {"country": "中国", "city": "遵义", "variants": ["遵义", "Zunyi"], "lat": 27.7309, "lng": 106.9373},
    {"country": "中国", "city": "安顺", "variants": ["安顺", "Anshun"], "lat": 26.2521, "lng": 105.9388},
    {"country": "中国", "city": "毕节", "variants": ["毕节", "Bijie"], "lat": 27.2983, "lng": 105.2886},
    {"country": "中国", "city": "铜仁", "variants": ["铜仁", "Tongren"], "lat": 27.7205, "lng": 109.1933},
    {"country": "中国", "city": "黔西南", "variants": ["黔西南", "Qianxinan"], "lat": 25.0866, "lng": 104.9018},
    {"country": "中国", "city": "黔东南", "variants": ["黔东南", "Qiandongnan"], "lat": 26.5783, "lng": 107.9802},
    {"country": "中国", "city": "黔南", "variants": ["黔南", "Qiannan"], "lat": 26.2576, "lng": 107.5192},
    {"country": "中国", "city": "昆明", "variants": ["昆明", "Kunming"], "lat": 25.0296, "lng": 102.7103},
    {"country": "中国", "city": "曲靖", "variants": ["曲靖", "Qujing"], "lat": 25.5015, "lng": 103.7919},
    {"country": "中国", "city": "玉溪", "variants": ["玉溪", "Yuxi"], "lat": 24.3506, "lng": 102.5516},
    {"country": "中国", "city": "保山", "variants": ["保山", "Baoshan"], "lat": 25.1125, "lng": 99.1614},
    {"country": "中国", "city": "昭通", "variants": ["昭通", "Zhaotong"], "lat": 27.3374, "lng": 103.7184},
    {"country": "中国", "city": "丽江", "variants": ["丽江", "Lijiang"], "lat": 26.8721, "lng": 100.2299},
    {"country": "中国", "city": "普洱", "variants": ["普洱", "Pu'er"], "lat": 22.8252, "lng": 100.9674},
    {"country": "中国", "city": "临沧", "variants": ["临沧", "Lincang"], "lat": 23.8841, "lng": 100.0859},
    {"country": "中国", "city": "楚雄", "variants": ["楚雄", "Chuxiong"], "lat": 25.0356, "lng": 101.5422},
    {"country": "中国", "city": "红河", "variants": ["红河", "Honghe"], "lat": 23.3736, "lng": 103.3814},
    {"country": "中国", "city": "文山", "variants": ["文山", "Wenshan"], "lat": 23.3736, "lng": 104.2467},
    {"country": "中国", "city": "西双版纳", "variants": ["西双版纳", "Xishuangbanna"], "lat": 22.0074, "lng": 100.8018},
    {"country": "中国", "city": "大理", "variants": ["大理", "Dali"], "lat": 25.6058, "lng": 100.2677},
    {"country": "中国", "city": "德宏", "variants": ["德宏", "Dehong"], "lat": 24.4336, "lng": 98.5878},
    {"country": "中国", "city": "怒江", "variants": ["怒江", "Nujiang"], "lat": 25.8505, "lng": 98.8586},
    {"country": "中国", "city": "迪庆", "variants": ["迪庆", "Diqing"], "lat": 27.8221, "lng": 99.7035},
    {"country": "中国", "city": "拉萨", "variants": ["拉萨", "Lhasa"], "lat": 29.6517, "lng": 91.1727},
    {"country": "中国", "city": "日喀则", "variants": ["日喀则", "Shigatse"], "lat": 29.2754, "lng": 88.8844},
    {"country": "中国", "city": "昌都", "variants": ["昌都", "Qamdo"], "lat": 31.1454, "lng": 97.1799},
    {"country": "中国", "city": "林芝", "variants": ["林芝", "Nyingchi"], "lat": 29.6469, "lng": 94.3615},
    {"country": "中国", "city": "山南", "variants": ["山南", "Shannan"], "lat": 29.2364, "lng": 91.7709},
    {"country": "中国", "city": "那曲", "variants": ["那曲", "Nagqu"], "lat": 31.4791, "lng": 92.0505},
    {"country": "中国", "city": "阿里", "variants": ["阿里", "Ngari"], "lat": 32.5009, "lng": 80.1203},
    {"country": "中国", "city": "西安", "variants": ["西安", "Xi'an", "Xian"], "lat": 34.3416, "lng": 108.9398},
    {"country": "中国", "city": "铜川", "variants": ["铜川", "Tongchuan"], "lat": 34.9017, "lng": 108.9615},
    {"country": "中国", "city": "宝鸡", "variants": ["宝鸡", "Baoji"], "lat": 34.3631, "lng": 107.2334},
    {"country": "中国", "city": "咸阳", "variants": ["咸阳", "Xianyang"], "lat": 34.3416, "lng": 108.7056},
    {"country": "中国", "city": "渭南", "variants": ["渭南", "Weinan"], "lat": 34.5008, "lng": 109.4977},
    {"country": "中国", "city": "延安", "variants": ["延安", "Yan'an"], "lat": 36.5952, "lng": 109.4908},
    {"country": "中国", "city": "汉中", "variants": ["汉中", "Hanzhong"], "lat": 33.0666, "lng": 107.0290},
    {"country": "中国", "city": "榆林", "variants": ["榆林", "Yulin"], "lat": 38.2785, "lng": 109.7337},
    {"country": "中国", "city": "安康", "variants": ["安康", "Ankang"], "lat": 32.6957, "lng": 109.0207},
    {"country": "中国", "city": "商洛", "variants": ["商洛", "Shangluo"], "lat": 33.8637, "lng": 109.9417},
    {"country": "中国", "city": "兰州", "variants": ["兰州", "Lanzhou"], "lat": 36.0617, "lng": 103.8343},
    {"country": "中国", "city": "嘉峪关", "variants": ["嘉峪关", "Jiayuguan"], "lat": 39.7751, "lng": 98.2892},
    {"country": "中国", "city": "金昌", "variants": ["金昌", "Jinchang"], "lat": 38.5221, "lng": 102.1915},
    {"country": "中国", "city": "白银", "variants": ["白银", "Baiyin"], "lat": 36.5454, "lng": 104.1447},
    {"country": "中国", "city": "天水", "variants": ["天水", "Tianshui"], "lat": 34.5659, "lng": 105.7245},
    {"country": "中国", "city": "武威", "variants": ["武威", "Wuwei"], "lat": 37.9287, "lng": 102.6340},
    {"country": "中国", "city": "张掖", "variants": ["张掖", "Zhangye"], "lat": 38.9280, "lng": 100.4557},
    {"country": "中国", "city": "平凉", "variants": ["平凉", "Pingliang"], "lat": 35.5441, "lng": 106.6682},
    {"country": "中国", "city": "酒泉", "variants": ["酒泉", "Jiuquan"], "lat": 39.7329, "lng": 98.4975},
    {"country": "中国", "city": "庆阳", "variants": ["庆阳", "Qingyang"], "lat": 35.7145, "lng": 107.6458},
    {"country": "中国", "city": "定西", "variants": ["定西", "Dingxi"], "lat": 35.5807, "lng": 104.6306},
    {"country": "中国", "city": "陇南", "variants": ["陇南", "Longnan"], "lat": 33.4015, "lng": 104.9241},
    {"country": "中国", "city": "临夏", "variants": ["临夏", "Linxia"], "lat": 35.5951, "lng": 103.2109},
    {"country": "中国", "city": "甘南", "variants": ["甘南", "Gannan"], "lat": 34.9818, "lng": 102.9118},
    {"country": "中国", "city": "西宁", "variants": ["西宁", "Xining"], "lat": 36.6171, "lng": 101.7782},
    {"country": "中国", "city": "海东", "variants": ["海东", "Haidong"], "lat": 36.5142, "lng": 102.1232},
    {"country": "中国", "city": "海北", "variants": ["海北", "Haibei"], "lat": 36.9529, "lng": 100.9002},
    {"country": "中国", "city": "黄南", "variants": ["黄南", "Huangnan"], "lat": 35.5175, "lng": 102.0108},
    {"country": "中国", "city": "海南", "variants": ["海南", "Hainan"], "lat": 36.2888, "lng": 101.0040},
    {"country": "中国", "city": "果洛", "variants": ["果洛", "Golog"], "lat": 34.4720, "lng": 100.2491},
    {"country": "中国", "city": "玉树", "variants": ["玉树", "Yushu"], "lat": 33.0154, "lng": 97.0077},
    {"country": "中国", "city": "海西", "variants": ["海西", "Haixi"], "lat": 37.3739, "lng": 97.3696},
    {"country": "中国", "city": "银川", "variants": ["银川", "Yinchuan"], "lat": 38.4874, "lng": 106.2301},
    {"country": "中国", "city": "石嘴山", "variants": ["石嘴山", "Shizuishan"], "lat": 39.0388, "lng": 106.3934},
    {"country": "中国", "city": "吴忠", "variants": ["吴忠", "Wuzhong"], "lat": 37.9941, "lng": 106.1865},
    {"country": "中国", "city": "固原", "variants": ["固原", "Guyuan"], "lat": 36.0185, "lng": 106.2811},
    {"country": "中国", "city": "中卫", "variants": ["中卫", "Zhongwei"], "lat": 37.5140, "lng": 105.1862},
    {"country": "中国", "city": "乌鲁木齐", "variants": ["乌鲁木齐", "Urumqi", "Urumchi"], "lat": 43.8256, "lng": 87.6168},
    {"country": "中国", "city": "克拉玛依", "variants": ["克拉玛依", "Karamay"], "lat": 45.5802, "lng": 84.8918},
    {"country": "中国", "city": "吐鲁番", "variants": ["吐鲁番", "Turpan"], "lat": 42.9513, "lng": 89.1895},
    {"country": "中国", "city": "哈密", "variants": ["哈密", "Hami"], "lat": 42.8334, "lng": 93.5142},
    {"country": "中国", "city": "昌吉", "variants": ["昌吉", "Changji"], "lat": 44.0191, "lng": 87.3095},
    {"country": "中国", "city": "博尔塔拉", "variants": ["博尔塔拉", "Bortala"], "lat": 44.9032, "lng": 82.0720},
    {"country": "中国", "city": "巴音郭楞", "variants": ["巴音郭楞", "Bayingolin"], "lat": 41.7601, "lng": 86.1584},
    {"country": "中国", "city": "阿克苏", "variants": ["阿克苏", "Aksu"], "lat": 41.1689, "lng": 80.2603},
    {"country": "中国", "city": "克孜勒苏", "variants": ["克孜勒苏", "Kizilsu"], "lat": 39.7156, "lng": 76.1746},
    {"country": "中国", "city": "喀什", "variants": ["喀什", "Kashgar"], "lat": 39.4704, "lng": 75.9898},
    {"country": "中国", "city": "和田", "variants": ["和田", "Hotan"], "lat": 37.1125, "lng": 79.9304},
    {"country": "中国", "city": "伊犁", "variants": ["伊犁", "Ili"], "lat": 43.9177, "lng": 81.3238},
    {"country": "中国", "city": "塔城", "variants": ["塔城", "Tacheng"], "lat": 46.7455, "lng": 82.9859},
    {"country": "中国", "city": "阿勒泰", "variants": ["阿勒泰", "Altay"], "lat": 47.8428, "lng": 88.1388},
    {"country": "中国", "city": "石河子", "variants": ["石河子", "Shihezi"], "lat": 44.2991, "lng": 86.0743},
    {"country": "中国", "city": "阿拉尔", "variants": ["阿拉尔", "Aral"], "lat": 40.5531, "lng": 81.2830},
    {"country": "中国", "city": "五家渠", "variants": ["五家渠", "Wujiaqu"], "lat": 44.1881, "lng": 87.5529},
    {"country": "中国", "city": "台北", "variants": ["台北", "Taipei"], "lat": 25.0330, "lng": 121.5654},
    {"country": "中国", "city": "高雄", "variants": ["高雄", "Kaohsiung"], "lat": 22.6273, "lng": 120.3019},
    {"country": "中国", "city": "基隆", "variants": ["基隆", "Keelung"], "lat": 25.1329, "lng": 121.7436},
    {"country": "中国", "city": "新竹", "variants": ["新竹", "Hsinchu"], "lat": 24.8138, "lng": 120.9647},
    {"country": "中国", "city": "台中", "variants": ["台中", "Taichung"], "lat": 24.1477, "lng": 120.6736},
    {"country": "中国", "city": "嘉义", "variants": ["嘉义", "Chiayi"], "lat": 23.4801, "lng": 120.4495},
    {"country": "中国", "city": "台南", "variants": ["台南", "Tainan"], "lat": 22.9997, "lng": 120.2128},
    {"country": "中国", "city": "澳门", "variants": ["澳门", "Macau", "Macao"], "lat": 22.1987, "lng": 113.5439},
    # ── 中国 县级市/重点县 ──
    {"country": "中国", "city": "昆山", "variants": ["昆山", "Kunshan"], "lat": 31.3842, "lng": 120.9792},
    {"country": "中国", "city": "江阴", "variants": ["江阴", "Jiangyin"], "lat": 31.9155, "lng": 120.2784},
    {"country": "中国", "city": "张家港", "variants": ["张家港", "Zhangjiagang"], "lat": 31.8766, "lng": 120.5473},
    {"country": "中国", "city": "常熟", "variants": ["常熟", "Changshu"], "lat": 31.6507, "lng": 120.7505},
    {"country": "中国", "city": "太仓", "variants": ["太仓", "Taicang"], "lat": 31.4524, "lng": 121.1016},
    {"country": "中国", "city": "宜兴", "variants": ["宜兴", "Yixing"], "lat": 31.3411, "lng": 119.8235},
    {"country": "中国", "city": "溧阳", "variants": ["溧阳", "Liyang"], "lat": 31.4142, "lng": 119.4865},
    {"country": "中国", "city": "义乌", "variants": ["义乌", "Yiwu"], "lat": 29.3055, "lng": 120.0751},
    {"country": "中国", "city": "慈溪", "variants": ["慈溪", "Cixi"], "lat": 30.1695, "lng": 121.2473},
    {"country": "中国", "city": "诸暨", "variants": ["诸暨", "Zhuji"], "lat": 29.7159, "lng": 120.2366},
    {"country": "中国", "city": "海宁", "variants": ["海宁", "Haining"], "lat": 30.5327, "lng": 120.6808},
    {"country": "中国", "city": "桐乡", "variants": ["桐乡", "Tongxiang"], "lat": 30.6319, "lng": 120.5296},
    {"country": "中国", "city": "瑞安", "variants": ["瑞安", "Rui'an"], "lat": 27.7835, "lng": 120.6503},
    {"country": "中国", "city": "乐清", "variants": ["乐清", "Yueqing"], "lat": 28.1189, "lng": 120.9627},
    {"country": "中国", "city": "温岭", "variants": ["温岭", "Wenling"], "lat": 28.3699, "lng": 121.3671},
    {"country": "中国", "city": "临海", "variants": ["临海", "Linhai"], "lat": 28.8478, "lng": 121.1636},
    {"country": "中国", "city": "东阳", "variants": ["东阳", "Dongyang"], "lat": 29.2866, "lng": 120.2341},
    {"country": "中国", "city": "永康", "variants": ["永康", "Yongkang"], "lat": 28.8946, "lng": 120.0335},
    {"country": "中国", "city": "晋江", "variants": ["晋江", "Jinjiang"], "lat": 24.8186, "lng": 118.5763},
    {"country": "中国", "city": "石狮", "variants": ["石狮", "Shishi"], "lat": 24.7371, "lng": 118.6584},
    {"country": "中国", "city": "南安", "variants": ["南安", "Nan'an"], "lat": 24.9609, "lng": 118.3820},
    {"country": "中国", "city": "福清", "variants": ["福清", "Fuqing"], "lat": 25.7256, "lng": 119.3834},
    {"country": "中国", "city": "长乐", "variants": ["长乐", "Changle"], "lat": 25.9643, "lng": 119.5239},
    {"country": "中国", "city": "滕州", "variants": ["滕州", "Tengzhou"], "lat": 35.1010, "lng": 117.1579},
    {"country": "中国", "city": "曲阜", "variants": ["曲阜", "Qufu"], "lat": 35.5807, "lng": 116.9918},
    {"country": "中国", "city": "荣成", "variants": ["荣成", "Rongcheng"], "lat": 37.1663, "lng": 122.4930},
    {"country": "中国", "city": "新泰", "variants": ["新泰", "Xintai"], "lat": 35.9093, "lng": 117.7687},
    {"country": "中国", "city": "肥城", "variants": ["肥城", "Feicheng"], "lat": 36.1914, "lng": 116.7658},
    {"country": "中国", "city": "寿光", "variants": ["寿光", "Shouguang"], "lat": 36.8579, "lng": 118.7856},
    {"country": "中国", "city": "邹城", "variants": ["邹城", "Zoucheng"], "lat": 35.4033, "lng": 117.0041},
    {"country": "中国", "city": "诸城", "variants": ["诸城", "Zhucheng"], "lat": 35.9971, "lng": 119.4144},
    {"country": "中国", "city": "胶州", "variants": ["胶州", "Jiaozhou"], "lat": 36.2658, "lng": 120.0261},
    {"country": "中国", "city": "巩义", "variants": ["巩义", "Gongyi"], "lat": 34.7542, "lng": 113.0216},
    {"country": "中国", "city": "新郑", "variants": ["新郑", "Xinzheng"], "lat": 34.3980, "lng": 113.7405},
    {"country": "中国", "city": "禹州", "variants": ["禹州", "Yuzhou"], "lat": 34.1586, "lng": 113.4846},
    {"country": "中国", "city": "浏阳", "variants": ["浏阳", "Liuyang"], "lat": 28.1636, "lng": 113.6341},
    {"country": "中国", "city": "醴陵", "variants": ["醴陵", "Liling"], "lat": 27.6557, "lng": 113.5024},
    {"country": "中国", "city": "耒阳", "variants": ["耒阳", "Leiyang"], "lat": 26.4179, "lng": 112.8477},
    {"country": "中国", "city": "仙桃", "variants": ["仙桃", "Xiantao"], "lat": 30.3378, "lng": 113.4428},
    {"country": "中国", "city": "潜江", "variants": ["潜江", "Qianjiang"], "lat": 30.4036, "lng": 112.8963},
    {"country": "中国", "city": "天门", "variants": ["天门", "Tianmen"], "lat": 30.6644, "lng": 113.1622},
    {"country": "中国", "city": "大冶", "variants": ["大冶", "Daye"], "lat": 30.0972, "lng": 114.9688},
    {"country": "中国", "city": "丹江口", "variants": ["丹江口", "Danjiangkou"], "lat": 32.5427, "lng": 111.5093},
    {"country": "中国", "city": "恩施", "variants": ["恩施", "Enshi"], "lat": 30.2741, "lng": 109.4863},
    {"country": "中国", "city": "利川", "variants": ["利川", "Lichuan"], "lat": 30.2932, "lng": 108.9388},
    {"country": "中国", "city": "洪湖", "variants": ["洪湖", "Honghu"], "lat": 29.8255, "lng": 113.4563},
    {"country": "中国", "city": "松滋", "variants": ["松滋", "Songzi"], "lat": 30.1733, "lng": 111.7572},
    {"country": "中国", "city": "枝江", "variants": ["枝江", "Zhijiang"], "lat": 30.4280, "lng": 111.7569},
    {"country": "中国", "city": "峨眉山", "variants": ["峨眉山", "Emeishan"], "lat": 29.6004, "lng": 103.4845},
    {"country": "中国", "city": "西昌", "variants": ["西昌", "Xichang"], "lat": 27.8985, "lng": 102.2701},
    {"country": "中国", "city": "广汉", "variants": ["广汉", "Guanghan"], "lat": 30.9807, "lng": 104.2811},
    {"country": "中国", "city": "都江堰", "variants": ["都江堰", "Dujiangyan"], "lat": 30.9966, "lng": 103.6220},
    {"country": "中国", "city": "江油", "variants": ["江油", "Jiangyou"], "lat": 31.7678, "lng": 104.7453},
    {"country": "中国", "city": "阆中", "variants": ["阆中", "Langzhong"], "lat": 31.5500, "lng": 105.9741},
    {"country": "中国", "city": "仁怀", "variants": ["仁怀", "Renhuai"], "lat": 27.8123, "lng": 106.4055},
    {"country": "中国", "city": "大理", "variants": ["大理", "Dali"], "lat": 25.6058, "lng": 100.2677},
    {"country": "中国", "city": "腾冲", "variants": ["腾冲", "Tengchong"], "lat": 25.0251, "lng": 98.4912},
    {"country": "中国", "city": "瑞丽", "variants": ["瑞丽", "Ruili"], "lat": 24.0147, "lng": 97.8599},
    {"country": "中国", "city": "香格里拉", "variants": ["香格里拉", "Shangri-La"], "lat": 27.8293, "lng": 99.7026},
    {"country": "中国", "city": "安宁", "variants": ["安宁", "Anning"], "lat": 24.9211, "lng": 102.4893},
    {"country": "中国", "city": "楚雄", "variants": ["楚雄", "Chuxiong"], "lat": 25.0356, "lng": 101.5422},
    {"country": "中国", "city": "宣威", "variants": ["宣威", "Xuanwei"], "lat": 26.2223, "lng": 104.1074},
    {"country": "中国", "city": "弥勒", "variants": ["弥勒", "Mile"], "lat": 24.4144, "lng": 103.4317},
    {"country": "中国", "city": "个旧", "variants": ["个旧", "Gejiu"], "lat": 23.3612, "lng": 103.1603},
    {"country": "中国", "city": "开远", "variants": ["开远", "Kaiyuan"], "lat": 23.7011, "lng": 103.2584},
    {"country": "中国", "city": "敦煌", "variants": ["敦煌", "Dunhuang"], "lat": 40.1419, "lng": 94.6628},
    {"country": "中国", "city": "玉门", "variants": ["玉门", "Yumen"], "lat": 39.8236, "lng": 97.0450},
    {"country": "中国", "city": "格尔木", "variants": ["格尔木", "Golmud"], "lat": 36.4075, "lng": 94.9089},
    {"country": "中国", "city": "德令哈", "variants": ["德令哈", "Delhi"], "lat": 37.3698, "lng": 97.3621},
    {"country": "中国", "city": "茫崖", "variants": ["茫崖", "Mangya"], "lat": 38.2467, "lng": 90.1598},
    {"country": "中国", "city": "满洲里", "variants": ["满洲里", "Manzhouli"], "lat": 49.5951, "lng": 117.4560},
    {"country": "中国", "city": "二连浩特", "variants": ["二连浩特", "Erenhot"], "lat": 43.6488, "lng": 111.9661},
    {"country": "中国", "city": "阿尔山", "variants": ["阿尔山", "Arxan"], "lat": 47.1806, "lng": 119.9409},
    {"country": "中国", "city": "锡林浩特", "variants": ["锡林浩特", "Xilinhot"], "lat": 43.9335, "lng": 116.0853},
    {"country": "中国", "city": "霍尔果斯", "variants": ["霍尔果斯", "Horgos"], "lat": 44.1977, "lng": 80.4219},
    {"country": "中国", "city": "阿拉山口", "variants": ["阿拉山口", "Alashankou"], "lat": 45.1679, "lng": 82.5591},
    {"country": "中国", "city": "喀纳斯", "variants": ["喀纳斯", "Kanas"], "lat": 48.7062, "lng": 87.0588},
    {"country": "中国", "city": "珲春", "variants": ["珲春", "Hunchun"], "lat": 42.8688, "lng": 130.3652},
    {"country": "中国", "city": "绥芬河", "variants": ["绥芬河", "Suifenhe"], "lat": 44.4138, "lng": 131.1660},
    {"country": "中国", "city": "黑河", "variants": ["黑河", "Heihe"], "lat": 50.2447, "lng": 127.5046},
    {"country": "中国", "city": "漠河", "variants": ["漠河", "Mohe"], "lat": 52.9725, "lng": 122.5385},
    {"country": "中国", "city": "抚远", "variants": ["抚远", "Fuyuan"], "lat": 48.3672, "lng": 134.3065},
    {"country": "中国", "city": "同江", "variants": ["同江", "Tongjiang"], "lat": 47.6499, "lng": 132.4989},
    {"country": "中国", "city": "东兴", "variants": ["东兴", "Dongxing"], "lat": 21.5500, "lng": 108.0596},
    {"country": "中国", "city": "凭祥", "variants": ["凭祥", "Pingxiang"], "lat": 22.0936, "lng": 106.7656},
    {"country": "中国", "city": "靖西", "variants": ["靖西", "Jingxi"], "lat": 23.1338, "lng": 106.4145},
    {"country": "中国", "city": "博鳌", "variants": ["博鳌", "Boao"], "lat": 19.1591, "lng": 110.5831},
    {"country": "中国", "city": "文昌", "variants": ["文昌", "Wenchang"], "lat": 19.6189, "lng": 110.7518},
    {"country": "中国", "city": "儋州", "variants": ["儋州", "Danzhou"], "lat": 19.5218, "lng": 109.5746},
    {"country": "中国", "city": "琼海", "variants": ["琼海", "Qionghai"], "lat": 19.2503, "lng": 110.4615},
    {"country": "中国", "city": "万宁", "variants": ["万宁", "Wanning"], "lat": 18.7933, "lng": 110.3931},
    {"country": "中国", "city": "雄安", "variants": ["雄安", "Xiong'an"], "lat": 39.0513, "lng": 115.9720},
    {"country": "中国", "city": "井冈山", "variants": ["井冈山", "Jinggangshan"], "lat": 26.6763, "lng": 114.1278},
    {"country": "中国", "city": "瑞金", "variants": ["瑞金", "Ruijin"], "lat": 25.8844, "lng": 116.0341},
    {"country": "中国", "city": "韶山", "variants": ["韶山", "Shaoshan"], "lat": 27.9203, "lng": 112.5263},
    {"country": "中国", "city": "曹县", "variants": ["曹县", "Caoxian"], "lat": 34.8246, "lng": 115.5470},
    {"country": "中国", "city": "汶川", "variants": ["汶川", "Wenchuan"], "lat": 31.4764, "lng": 103.5812},
    {"country": "中国", "city": "北川", "variants": ["北川", "Beichuan"], "lat": 31.8327, "lng": 104.4573},
    {"country": "中国", "city": "玉树", "variants": ["玉树", "Yushu"], "lat": 33.0154, "lng": 97.0077},
    {"country": "中国", "city": "芦山", "variants": ["芦山", "Lushan"], "lat": 30.1513, "lng": 102.9345},
    {"country": "中国", "city": "鲁甸", "variants": ["鲁甸", "Ludian"], "lat": 27.1873, "lng": 103.5615},
    {"country": "中国", "city": "九寨沟", "variants": ["九寨沟", "Jiuzhaigou"], "lat": 33.2508, "lng": 103.9172},
    {"country": "中国", "city": "稻城", "variants": ["稻城", "Daocheng"], "lat": 29.0379, "lng": 100.2911},
    {"country": "中国", "city": "色达", "variants": ["色达", "Seda"], "lat": 32.2711, "lng": 100.3306},
    {"country": "中国", "city": "理塘", "variants": ["理塘", "Litang"], "lat": 29.9962, "lng": 100.2706},
    {"country": "中国", "city": "康定", "variants": ["康定", "Kangding"], "lat": 30.0558, "lng": 101.9654},
    {"country": "中国", "city": "马尔康", "variants": ["马尔康", "Barkam"], "lat": 31.9057, "lng": 102.2087},
    {"country": "中国", "city": "凤凰", "variants": ["凤凰", "Fenghuang"], "lat": 27.9572, "lng": 109.5998},
    {"country": "中国", "city": "武隆", "variants": ["武隆", "Wulong"], "lat": 29.3290, "lng": 107.7962},
    {"country": "中国", "city": "神农架", "variants": ["神农架", "Shennongjia"], "lat": 31.7521, "lng": 110.6785},
    {"country": "中国", "city": "武夷山", "variants": ["武夷山", "Wuyishan"], "lat": 27.7368, "lng": 118.0326},
    {"country": "中国", "city": "普陀山", "variants": ["普陀山", "Putuoshan"], "lat": 30.0108, "lng": 122.3881},
    {"country": "中国", "city": "平潭", "variants": ["平潭", "Pingtan"], "lat": 25.5094, "lng": 119.7874},
    {"country": "中国", "city": "三沙", "variants": ["三沙", "Sansha"], "lat": 16.8333, "lng": 112.3333},
    {"country": "中国", "city": "涠洲岛", "variants": ["涠洲岛", "Weizhou Island"], "lat": 21.0421, "lng": 109.1118},
    {"country": "中国", "city": "长岛", "variants": ["长岛", "Changdao"], "lat": 37.9262, "lng": 120.7204},
    {"country": "中国", "city": "嵊泗", "variants": ["嵊泗", "Shengsi"], "lat": 30.7280, "lng": 122.4673},
    {"country": "中国", "city": "洞头", "variants": ["洞头", "Dongtou"], "lat": 27.8308, "lng": 121.1456},
    # ── 美国 ──
    {"country": "美国", "city": "华盛顿", "variants": ["华盛顿", "Washington DC", "Washington, D.C.", "Washington D.C"], "lat": 38.9072, "lng": -77.0369},
    {"country": "美国", "city": "纽约", "variants": ["纽约", "New York", "NYC", "曼哈顿", "Manhattan", "华尔街", "Wall Street"], "lat": 40.7128, "lng": -74.0060},
    {"country": "美国", "city": "旧金山", "variants": ["旧金山", "San Francisco", "硅谷", "Silicon Valley", "Palo Alto", "帕洛阿尔托", "山景城", "Mountain View"], "lat": 37.7749, "lng": -122.4194},
    {"country": "美国", "city": "洛杉矶", "variants": ["洛杉矶", "Los Angeles", "LA", "好莱坞", "Hollywood"], "lat": 34.0522, "lng": -118.2437},
    {"country": "美国", "city": "芝加哥", "variants": ["芝加哥", "Chicago"], "lat": 41.8781, "lng": -87.6298},
    {"country": "美国", "city": "休斯顿", "variants": ["休斯顿", "Houston", "休斯敦"], "lat": 29.7604, "lng": -95.3698},
    {"country": "美国", "city": "迈阿密", "variants": ["迈阿密", "Miami"], "lat": 25.7617, "lng": -80.1918},
    {"country": "美国", "city": "西雅图", "variants": ["西雅图", "Seattle"], "lat": 47.6062, "lng": -122.3321},
    {"country": "美国", "city": "波士顿", "variants": ["波士顿", "Boston"], "lat": 42.3601, "lng": -71.0589},
    {"country": "美国", "city": "拉斯维加斯", "variants": ["拉斯维加斯", "Las Vegas"], "lat": 36.1699, "lng": -115.1398},
    {"country": "美国", "city": "丹佛", "variants": ["丹佛", "Denver"], "lat": 39.7392, "lng": -104.9903},
    {"country": "美国", "city": "亚特兰大", "variants": ["亚特兰大", "Atlanta"], "lat": 33.7490, "lng": -84.3880},
    {"country": "美国", "city": "底特律", "variants": ["底特律", "Detroit"], "lat": 42.3314, "lng": -83.0458},
    {"country": "美国", "city": "费城", "variants": ["费城", "Philadelphia", "Philly"], "lat": 39.9526, "lng": -75.1652},
    {"country": "美国", "city": "凤凰城", "variants": ["凤凰城", "Phoenix"], "lat": 33.4484, "lng": -112.0740},
    {"country": "美国", "city": "奥斯汀", "variants": ["奥斯汀", "Austin"], "lat": 30.2672, "lng": -97.7431},
    {"country": "美国", "city": "波特兰", "variants": ["波特兰", "Portland"], "lat": 45.5152, "lng": -122.6784},
    {"country": "美国", "city": "圣迭戈", "variants": ["圣迭戈", "San Diego"], "lat": 32.7157, "lng": -117.1611},
    {"country": "美国", "city": "纳什维尔", "variants": ["纳什维尔", "Nashville"], "lat": 36.1627, "lng": -86.7816},
    {"country": "美国", "city": "新奥尔良", "variants": ["新奥尔良", "New Orleans"], "lat": 29.9511, "lng": -90.0715},
    # ── 日本 ──
    {"country": "日本", "city": "东京", "variants": ["东京", "Tokyo"], "lat": 35.6762, "lng": 139.6503},
    {"country": "日本", "city": "大阪", "variants": ["大阪", "Osaka"], "lat": 34.6937, "lng": 135.5023},
    {"country": "日本", "city": "京都", "variants": ["京都", "Kyoto"], "lat": 35.0116, "lng": 135.7681},
    {"country": "日本", "city": "横滨", "variants": ["横滨", "Yokohama"], "lat": 35.4437, "lng": 139.6380},
    {"country": "日本", "city": "名古屋", "variants": ["名古屋", "Nagoya"], "lat": 35.1815, "lng": 136.9066},
    {"country": "日本", "city": "那霸（冲绳）", "variants": ["冲绳", "Okinawa", "那霸", "Naha"], "lat": 26.2124, "lng": 127.6809},
    {"country": "日本", "city": "福冈", "variants": ["福冈", "Fukuoka"], "lat": 33.5904, "lng": 130.4017},
    {"country": "日本", "city": "札幌", "variants": ["札幌", "Sapporo"], "lat": 43.0618, "lng": 141.3545},
    # ── 英国 ──
    {"country": "英国", "city": "伦敦", "variants": ["伦敦", "London", "City of London"], "lat": 51.5074, "lng": -0.1278},
    {"country": "英国", "city": "曼彻斯特", "variants": ["曼彻斯特", "Manchester"], "lat": 53.4808, "lng": -2.2426},
    {"country": "英国", "city": "伯明翰", "variants": ["伯明翰", "Birmingham"], "lat": 52.4862, "lng": -1.8904},
    {"country": "英国", "city": "利物浦", "variants": ["利物浦", "Liverpool"], "lat": 53.4084, "lng": -2.9916},
    {"country": "英国", "city": "爱丁堡", "variants": ["爱丁堡", "Edinburgh"], "lat": 55.9533, "lng": -3.1883},
    {"country": "英国", "city": "剑桥", "variants": ["剑桥", "Cambridge"], "lat": 52.2053, "lng": 0.1218},
    # ── 德国 ──
    {"country": "德国", "city": "柏林", "variants": ["柏林", "Berlin"], "lat": 52.5200, "lng": 13.4050},
    {"country": "德国", "city": "慕尼黑", "variants": ["慕尼黑", "Munich", "München"], "lat": 48.1351, "lng": 11.5820},
    {"country": "德国", "city": "法兰克福", "variants": ["法兰克福", "Frankfurt"], "lat": 50.1109, "lng": 8.6821},
    {"country": "德国", "city": "汉堡", "variants": ["汉堡", "Hamburg"], "lat": 53.5511, "lng": 9.9937},
    {"country": "德国", "city": "科隆", "variants": ["科隆", "Cologne", "Köln"], "lat": 50.9375, "lng": 6.9603},
    # ── 法国 ──
    {"country": "法国", "city": "巴黎", "variants": ["巴黎", "Paris"], "lat": 48.8566, "lng": 2.3522},
    {"country": "法国", "city": "马赛", "variants": ["马赛", "Marseille"], "lat": 43.2965, "lng": 5.3698},
    {"country": "法国", "city": "里昂", "variants": ["里昂", "Lyon"], "lat": 45.7640, "lng": 4.8357},
    {"country": "法国", "city": "波尔多", "variants": ["波尔多", "Bordeaux"], "lat": 44.8378, "lng": -0.5792},
    # ── 意大利 ──
    {"country": "意大利", "city": "罗马", "variants": ["罗马", "Rome", "Roma"], "lat": 41.9028, "lng": 12.4964},
    {"country": "意大利", "city": "米兰", "variants": ["米兰", "Milan", "Milano"], "lat": 45.4642, "lng": 9.1900},
    {"country": "意大利", "city": "威尼斯", "variants": ["威尼斯", "Venice", "Venezia"], "lat": 45.4408, "lng": 12.3155},
    {"country": "意大利", "city": "佛罗伦萨", "variants": ["佛罗伦萨", "Florence", "Firenze"], "lat": 43.7696, "lng": 11.2558},
    # ── 俄罗斯 ──
    {"country": "俄罗斯", "city": "莫斯科", "variants": ["莫斯科", "Moscow"], "lat": 55.7558, "lng": 37.6173},
    {"country": "俄罗斯", "city": "圣彼得堡", "variants": ["圣彼得堡", "Saint Petersburg", "St. Petersburg"], "lat": 59.9343, "lng": 30.3351},
    {"country": "俄罗斯", "city": "符拉迪沃斯托克", "variants": ["符拉迪沃斯托克", "Vladivostok", "海参崴"], "lat": 43.1155, "lng": 131.8855},
    {"country": "俄罗斯", "city": "新西伯利亚", "variants": ["新西伯利亚", "Novosibirsk"], "lat": 55.0084, "lng": 82.9357},
    # ── 印度 ──
    {"country": "印度", "city": "新德里", "variants": ["新德里", "New Delhi", "Delhi", "德里"], "lat": 28.6139, "lng": 77.2090},
    {"country": "印度", "city": "孟买", "variants": ["孟买", "Mumbai", "Bombay"], "lat": 19.0760, "lng": 72.8777},
    {"country": "印度", "city": "班加罗尔", "variants": ["班加罗尔", "Bangalore", "Bengaluru"], "lat": 12.9716, "lng": 77.5946},
    {"country": "印度", "city": "加尔各答", "variants": ["加尔各答", "Kolkata", "Calcutta"], "lat": 22.5726, "lng": 88.3639},
    {"country": "印度", "city": "金奈", "variants": ["金奈", "Chennai", "Madras"], "lat": 13.0827, "lng": 80.2707},
    {"country": "印度", "city": "海得拉巴", "variants": ["海得拉巴", "Hyderabad"], "lat": 17.3850, "lng": 78.4867},
    # ── 韩国 ──
    {"country": "韩国", "city": "首尔", "variants": ["首尔", "Seoul"], "lat": 37.5665, "lng": 126.9780},
    {"country": "韩国", "city": "釜山", "variants": ["釜山", "Busan", "Pusan"], "lat": 35.1796, "lng": 129.0756},
    {"country": "韩国", "city": "仁川", "variants": ["仁川", "Incheon"], "lat": 37.4563, "lng": 126.7052},
    # ── 澳大利亚 ──
    {"country": "澳大利亚", "city": "堪培拉", "variants": ["堪培拉", "Canberra"], "lat": -35.2809, "lng": 149.1300},
    {"country": "澳大利亚", "city": "悉尼", "variants": ["悉尼", "Sydney"], "lat": -33.8688, "lng": 151.2093},
    {"country": "澳大利亚", "city": "墨尔本", "variants": ["墨尔本", "Melbourne"], "lat": -37.8136, "lng": 144.9631},
    {"country": "澳大利亚", "city": "布里斯班", "variants": ["布里斯班", "Brisbane"], "lat": -27.4698, "lng": 153.0251},
    {"country": "澳大利亚", "city": "珀斯", "variants": ["珀斯", "Perth"], "lat": -31.9505, "lng": 115.8605},
    {"country": "澳大利亚", "city": "新南威尔士", "variants": ["新南威尔士州", "新南威尔士", "New South Wales", "NSW"], "lat": -33.8688, "lng": 151.2093},
    {"country": "澳大利亚", "city": "昆士兰", "variants": ["昆士兰州", "昆士兰", "Queensland"], "lat": -27.4698, "lng": 153.0251},
    # ── 巴西 ──
    {"country": "巴西", "city": "巴西利亚", "variants": ["巴西利亚", "Brasilia", "Brasília"], "lat": -15.7934, "lng": -47.8822},
    {"country": "巴西", "city": "里约热内卢", "variants": ["里约热内卢", "Rio de Janeiro", "里约"], "lat": -22.9068, "lng": -43.1729},
    {"country": "巴西", "city": "圣保罗", "variants": ["圣保罗", "São Paulo", "Sao Paulo"], "lat": -23.5505, "lng": -46.6333},
    {"country": "巴西", "city": "玛瑙斯", "variants": ["玛瑙斯", "Manaus"], "lat": -3.1190, "lng": -60.0250},
    # ── 加拿大 ──
    {"country": "加拿大", "city": "渥太华", "variants": ["渥太华", "Ottawa"], "lat": 45.4215, "lng": -75.6972},
    {"country": "加拿大", "city": "多伦多", "variants": ["多伦多", "Toronto"], "lat": 43.6532, "lng": -79.3832},
    {"country": "加拿大", "city": "温哥华", "variants": ["温哥华", "Vancouver"], "lat": 49.2827, "lng": -123.1207},
    {"country": "加拿大", "city": "蒙特利尔", "variants": ["蒙特利尔", "Montreal", "Montréal"], "lat": 45.5017, "lng": -73.5673},
    # ── 中东 ──
    {"country": "沙特阿拉伯", "city": "利雅得", "variants": ["利雅得", "Riyadh"], "lat": 24.7136, "lng": 46.6753},
    {"country": "沙特阿拉伯", "city": "NEOM", "variants": ["NEOM", "尼尤姆"], "lat": 28.0000, "lng": 35.0000},
    {"country": "阿联酋", "city": "迪拜", "variants": ["迪拜", "Dubai"], "lat": 25.2048, "lng": 55.2708},
    {"country": "阿联酋", "city": "阿布扎比", "variants": ["阿布扎比", "Abu Dhabi"], "lat": 24.4539, "lng": 54.3773},
    {"country": "伊朗", "city": "德黑兰", "variants": ["德黑兰", "Tehran"], "lat": 35.6892, "lng": 51.3890},
    {"country": "伊朗", "city": "伊斯法罕", "variants": ["伊斯法罕", "Isfahan"], "lat": 32.6546, "lng": 51.6680},
    {"country": "以色列", "city": "特拉维夫", "variants": ["特拉维夫", "Tel Aviv"], "lat": 32.0853, "lng": 34.7818},
    {"country": "以色列", "city": "耶路撒冷", "variants": ["耶路撒冷", "Jerusalem"], "lat": 31.7683, "lng": 35.2137},
    {"country": "巴勒斯坦", "city": "加沙", "variants": ["加沙", "Gaza"], "lat": 31.5017, "lng": 34.4668},
    {"country": "土耳其", "city": "伊斯坦布尔", "variants": ["伊斯坦布尔", "Istanbul", "İstanbul"], "lat": 41.0082, "lng": 28.9784},
    {"country": "土耳其", "city": "安卡拉", "variants": ["安卡拉", "Ankara"], "lat": 39.9334, "lng": 32.8597},
    # ── 非洲 ──
    {"country": "南非", "city": "比勒陀利亚", "variants": ["比勒陀利亚", "Pretoria"], "lat": -25.7449, "lng": 28.1877},
    {"country": "南非", "city": "约翰内斯堡", "variants": ["约翰内斯堡", "Johannesburg", "Jo'burg"], "lat": -26.2041, "lng": 28.0473},
    {"country": "南非", "city": "开普敦", "variants": ["开普敦", "Cape Town"], "lat": -33.9249, "lng": 18.4241},
    {"country": "尼日利亚", "city": "拉各斯", "variants": ["拉各斯", "Lagos"], "lat": 6.5244, "lng": 3.3792},
    {"country": "尼日利亚", "city": "阿布贾", "variants": ["阿布贾", "Abuja"], "lat": 9.0765, "lng": 7.3986},
    {"country": "埃及", "city": "开罗", "variants": ["开罗", "Cairo"], "lat": 30.0444, "lng": 31.2357},
    {"country": "埃及", "city": "亚历山大", "variants": ["亚历山大", "Alexandria"], "lat": 31.2001, "lng": 29.9187},
    {"country": "肯尼亚", "city": "内罗毕", "variants": ["内罗毕", "Nairobi"], "lat": -1.2921, "lng": 36.8219},
    {"country": "加纳", "city": "阿克拉", "variants": ["阿克拉", "Accra"], "lat": 5.6037, "lng": -0.1870},
    {"country": "刚果", "city": "金沙萨", "variants": ["金沙萨", "Kinshasa"], "lat": -4.4419, "lng": 15.2663},
    {"country": "莫桑比克", "city": "马普托", "variants": ["马普托", "Maputo"], "lat": -25.9692, "lng": 32.5732},
    {"country": "马拉维", "city": "利隆圭", "variants": ["利隆圭", "Lilongwe"], "lat": -13.9626, "lng": 33.7741},
    # ── 东南亚 ──
    {"country": "印尼", "city": "雅加达", "variants": ["雅加达", "Jakarta"], "lat": -6.2088, "lng": 106.8456},
    {"country": "印尼", "city": "努山塔拉", "variants": ["努山塔拉", "Nusantara"], "lat": -0.9717, "lng": 116.7274},
    {"country": "菲律宾", "city": "马尼拉", "variants": ["马尼拉", "Manila"], "lat": 14.5995, "lng": 120.9842},
    {"country": "越南", "city": "河内", "variants": ["河内", "Hanoi"], "lat": 21.0278, "lng": 105.8342},
    {"country": "越南", "city": "胡志明市", "variants": ["胡志明市", "Ho Chi Minh City", "Saigon", "西贡"], "lat": 10.8231, "lng": 106.6297},
    {"country": "泰国", "city": "曼谷", "variants": ["曼谷", "Bangkok"], "lat": 13.7563, "lng": 100.5018},
    {"country": "马来西亚", "city": "吉隆坡", "variants": ["吉隆坡", "Kuala Lumpur"], "lat": 3.1390, "lng": 101.6869},
    {"country": "新加坡", "city": "新加坡", "variants": ["新加坡", "Singapore"], "lat": 1.3521, "lng": 103.8198},
    {"country": "缅甸", "city": "内比都", "variants": ["内比都", "Naypyidaw", "Nay Pyi Taw"], "lat": 19.7633, "lng": 96.0785},
    {"country": "缅甸", "city": "仰光", "variants": ["仰光", "Yangon", "Rangoon"], "lat": 16.8403, "lng": 96.1735},
    # ── 欧洲其他 ──
    {"country": "西班牙", "city": "马德里", "variants": ["马德里", "Madrid"], "lat": 40.4168, "lng": -3.7038},
    {"country": "西班牙", "city": "巴塞罗那", "variants": ["巴塞罗那", "Barcelona"], "lat": 41.3874, "lng": 2.1686},
    {"country": "荷兰", "city": "阿姆斯特丹", "variants": ["阿姆斯特丹", "Amsterdam"], "lat": 52.3676, "lng": 4.9041},
    {"country": "荷兰", "city": "鹿特丹", "variants": ["鹿特丹", "Rotterdam"], "lat": 51.9244, "lng": 4.4777},
    {"country": "瑞士", "city": "苏黎世", "variants": ["苏黎世", "Zurich", "Zürich"], "lat": 47.3769, "lng": 8.5417},
    {"country": "瑞士", "city": "日内瓦", "variants": ["日内瓦", "Geneva", "Genève"], "lat": 46.2044, "lng": 6.1432},
    {"country": "瑞士", "city": "达沃斯", "variants": ["达沃斯", "Davos"], "lat": 46.8021, "lng": 9.8358},
    {"country": "瑞典", "city": "斯德哥尔摩", "variants": ["斯德哥尔摩", "Stockholm"], "lat": 59.3293, "lng": 18.0686},
    {"country": "挪威", "city": "奥斯陆", "variants": ["奥斯陆", "Oslo"], "lat": 59.9139, "lng": 10.7522},
    {"country": "丹麦", "city": "哥本哈根", "variants": ["哥本哈根", "Copenhagen", "København"], "lat": 55.6761, "lng": 12.5683},
    {"country": "芬兰", "city": "赫尔辛基", "variants": ["赫尔辛基", "Helsinki"], "lat": 60.1699, "lng": 24.9384},
    {"country": "波兰", "city": "华沙", "variants": ["华沙", "Warsaw", "Warszawa"], "lat": 52.2297, "lng": 21.0122},
    {"country": "波兰", "city": "克拉科夫", "variants": ["克拉科夫", "Krakow", "Kraków"], "lat": 50.0647, "lng": 19.9450},
    {"country": "捷克", "city": "布拉格", "variants": ["布拉格", "Prague", "Praha"], "lat": 50.0755, "lng": 14.4378},
    {"country": "奥地利", "city": "维也纳", "variants": ["维也纳", "Vienna", "Wien"], "lat": 48.2082, "lng": 16.3738},
    {"country": "匈牙利", "city": "布达佩斯", "variants": ["布达佩斯", "Budapest"], "lat": 47.4979, "lng": 19.0402},
    {"country": "比利时", "city": "布鲁塞尔", "variants": ["布鲁塞尔", "Brussels", "Bruxelles"], "lat": 50.8503, "lng": 4.3517},
    {"country": "希腊", "city": "雅典", "variants": ["雅典", "Athens"], "lat": 37.9838, "lng": 23.7275},
    {"country": "葡萄牙", "city": "里斯本", "variants": ["里斯本", "Lisbon", "Lisboa"], "lat": 38.7223, "lng": -9.1393},
    {"country": "乌克兰", "city": "基辅", "variants": ["基辅", "Kyiv", "Kiev"], "lat": 50.4501, "lng": 30.5234},
    {"country": "乌克兰", "city": "哈尔科夫", "variants": ["哈尔科夫", "Kharkiv"], "lat": 49.9935, "lng": 36.2304},
    {"country": "乌克兰", "city": "敖德萨", "variants": ["敖德萨", "Odesa", "Odessa"], "lat": 46.4825, "lng": 30.7233},
    {"country": "罗马尼亚", "city": "布加勒斯特", "variants": ["布加勒斯特", "Bucharest", "București"], "lat": 44.4268, "lng": 26.1025},
    # ── 拉丁美洲 ──
    {"country": "墨西哥", "city": "墨西哥城", "variants": ["墨西哥城", "Mexico City", "CDMX"], "lat": 19.4326, "lng": -99.1332},
    {"country": "阿根廷", "city": "布宜诺斯艾利斯", "variants": ["布宜诺斯艾利斯", "Buenos Aires"], "lat": -34.6037, "lng": -58.3816},
    {"country": "智利", "city": "圣地亚哥", "variants": ["圣地亚哥", "Santiago", "Santiago de Chile"], "lat": -33.4489, "lng": -70.6693},
    {"country": "哥伦比亚", "city": "波哥大", "variants": ["波哥大", "Bogotá", "Bogota"], "lat": 4.7110, "lng": -74.0721},
    {"country": "秘鲁", "city": "利马", "variants": ["利马", "Lima"], "lat": -12.0464, "lng": -77.0428},
    {"country": "古巴", "city": "哈瓦那", "variants": ["哈瓦那", "Havana", "La Habana"], "lat": 23.1136, "lng": -82.3666},
    {"country": "委内瑞拉", "city": "加拉加斯", "variants": ["加拉加斯", "Caracas"], "lat": 10.4806, "lng": -66.9036},
    # ── 大洋洲 ──
    {"country": "新西兰", "city": "惠灵顿", "variants": ["惠灵顿", "Wellington"], "lat": -41.2865, "lng": 174.7762},
    {"country": "新西兰", "city": "奥克兰", "variants": ["奥克兰", "Auckland"], "lat": -36.8485, "lng": 174.7633},
    # ── 北极/南极 ──
    {"country": "格陵兰", "city": "努克", "variants": ["格陵兰", "Greenland", "努克", "Nuuk"], "lat": 64.1814, "lng": -51.6941},
    {"country": "南极", "city": "南极", "variants": ["南极", "Antarctica", "South Pole", "南极洲"], "lat": -82.8628, "lng": 135.0000},
    {"country": "北极", "city": "北极", "variants": ["北极", "Arctic", "North Pole"], "lat": 78.0000, "lng": 15.0000},
    {"country": "斯瓦尔巴群岛", "city": "朗伊尔城", "variants": ["斯瓦尔巴", "Svalbard", "朗伊尔", "Longyearbyen"], "lat": 78.2232, "lng": 15.6267},
    # ── 墨西哥 (扩展) ──
    {"country": "墨西哥", "city": "蒙特雷", "variants": ["蒙特雷", "Monterrey"], "lat": 25.6866, "lng": -100.3161},
    {"country": "墨西哥", "city": "瓜达拉哈拉", "variants": ["瓜达拉哈拉", "Guadalajara"], "lat": 20.6597, "lng": -103.3496},
    {"country": "墨西哥", "city": "坎昆", "variants": ["坎昆", "Cancun", "Cancún"], "lat": 21.1619, "lng": -86.8515},
    {"country": "墨西哥", "city": "蒂华纳", "variants": ["蒂华纳", "Tijuana"], "lat": 32.5149, "lng": -117.0382},
    {"country": "墨西哥", "city": "普埃布拉", "variants": ["普埃布拉", "Puebla"], "lat": 19.0414, "lng": -98.2063},
    {"country": "墨西哥", "city": "梅里达", "variants": ["梅里达", "Merida", "Mérida"], "lat": 20.9674, "lng": -89.5926},
    # ── 巴基斯坦 ──
    {"country": "巴基斯坦", "city": "伊斯兰堡", "variants": ["伊斯兰堡", "Islamabad"], "lat": 33.6844, "lng": 73.0479},
    {"country": "巴基斯坦", "city": "卡拉奇", "variants": ["卡拉奇", "Karachi"], "lat": 24.8607, "lng": 67.0011},
    {"country": "巴基斯坦", "city": "拉合尔", "variants": ["拉合尔", "Lahore"], "lat": 31.5497, "lng": 74.3436},
    {"country": "巴基斯坦", "city": "拉瓦尔品第", "variants": ["拉瓦尔品第", "Rawalpindi"], "lat": 33.5651, "lng": 73.0169},
    {"country": "巴基斯坦", "city": "白沙瓦", "variants": ["白沙瓦", "Peshawar"], "lat": 34.0151, "lng": 71.5249},
    {"country": "巴基斯坦", "city": "奎达", "variants": ["奎达", "Quetta"], "lat": 30.1798, "lng": 66.9750},
    # ── 朝鲜 ──
    {"country": "朝鲜", "city": "平壤", "variants": ["平壤", "Pyongyang"], "lat": 39.0392, "lng": 125.7625},
    {"country": "朝鲜", "city": "开城", "variants": ["开城", "Kaesong"], "lat": 37.9713, "lng": 126.5575},
    {"country": "朝鲜", "city": "新义州", "variants": ["新义州", "Sinuiju"], "lat": 40.1006, "lng": 124.3967},
    # ── 韩国 (扩展) ──
    {"country": "韩国", "city": "大邱", "variants": ["大邱", "Daegu"], "lat": 35.8714, "lng": 128.6014},
    {"country": "韩国", "city": "大田", "variants": ["大田", "Daejeon"], "lat": 36.3504, "lng": 127.3845},
    {"country": "韩国", "city": "光州", "variants": ["光州", "Gwangju"], "lat": 35.1595, "lng": 126.8526},
    {"country": "韩国", "city": "蔚山", "variants": ["蔚山", "Ulsan"], "lat": 35.5384, "lng": 129.3114},
    {"country": "韩国", "city": "济州", "variants": ["济州", "Jeju"], "lat": 33.4996, "lng": 126.5312},
    # ── 孟加拉国 ──
    {"country": "孟加拉国", "city": "达卡", "variants": ["达卡", "Dhaka"], "lat": 23.8103, "lng": 90.4125},
    {"country": "孟加拉国", "city": "吉大港", "variants": ["吉大港", "Chittagong"], "lat": 22.3569, "lng": 91.7832},
    # ── 哈萨克斯坦 ──
    {"country": "哈萨克斯坦", "city": "阿斯塔纳", "variants": ["阿斯塔纳", "Astana", "努尔苏丹", "Nur-Sultan"], "lat": 51.1694, "lng": 71.4491},
    {"country": "哈萨克斯坦", "city": "阿拉木图", "variants": ["阿拉木图", "Almaty"], "lat": 43.2220, "lng": 76.8512},
    # ── 乌兹别克斯坦 ──
    {"country": "乌兹别克斯坦", "city": "塔什干", "variants": ["塔什干", "Tashkent"], "lat": 41.2995, "lng": 69.2401},
    {"country": "乌兹别克斯坦", "city": "撒马尔罕", "variants": ["撒马尔罕", "Samarkand"], "lat": 39.6270, "lng": 66.9750},
    # ── 蒙古 ──
    {"country": "蒙古", "city": "乌兰巴托", "variants": ["乌兰巴托", "Ulaanbaatar", "Ulan Bator"], "lat": 47.8864, "lng": 106.9057},
    # ── 阿富汗 ──
    {"country": "阿富汗", "city": "喀布尔", "variants": ["喀布尔", "Kabul"], "lat": 34.5553, "lng": 69.2075},
    {"country": "阿富汗", "city": "坎大哈", "variants": ["坎大哈", "Kandahar"], "lat": 31.6289, "lng": 65.7372},
    # ── 伊拉克 ──
    {"country": "伊拉克", "city": "巴格达", "variants": ["巴格达", "Baghdad"], "lat": 33.3152, "lng": 44.3661},
    {"country": "伊拉克", "city": "摩苏尔", "variants": ["摩苏尔", "Mosul"], "lat": 36.3350, "lng": 43.1186},
    {"country": "伊拉克", "city": "巴士拉", "variants": ["巴士拉", "Basra"], "lat": 30.5260, "lng": 47.7738},
    {"country": "伊拉克", "city": "埃尔比勒", "variants": ["埃尔比勒", "Erbil", "Arbil"], "lat": 36.1901, "lng": 44.0089},
    # ── 叙利亚 ──
    {"country": "叙利亚", "city": "大马士革", "variants": ["大马士革", "Damascus"], "lat": 33.5138, "lng": 36.2765},
    {"country": "叙利亚", "city": "阿勒颇", "variants": ["阿勒颇", "Aleppo"], "lat": 36.2021, "lng": 37.1343},
    # ── 也门 ──
    {"country": "也门", "city": "萨那", "variants": ["萨那", "Sanaa"], "lat": 15.3694, "lng": 44.1910},
    {"country": "也门", "city": "亚丁", "variants": ["亚丁", "Aden"], "lat": 12.7855, "lng": 45.0187},
    # ── 约旦 ──
    {"country": "约旦", "city": "安曼", "variants": ["安曼", "Amman"], "lat": 31.9454, "lng": 35.9284},
    # ── 黎巴嫩 ──
    {"country": "黎巴嫩", "city": "贝鲁特", "variants": ["贝鲁特", "Beirut"], "lat": 33.8938, "lng": 35.5018},
    # ── 卡塔尔 ──
    {"country": "卡塔尔", "city": "多哈", "variants": ["多哈", "Doha"], "lat": 25.2854, "lng": 51.5310},
    # ── 科威特 ──
    {"country": "科威特", "city": "科威特城", "variants": ["科威特城", "Kuwait City"], "lat": 29.3759, "lng": 47.9774},
    # ── 巴林 ──
    {"country": "巴林", "city": "麦纳麦", "variants": ["麦纳麦", "Manama"], "lat": 26.2285, "lng": 50.5860},
    # ── 阿曼 ──
    {"country": "阿曼", "city": "马斯喀特", "variants": ["马斯喀特", "Muscat"], "lat": 23.5880, "lng": 58.3829},
    # ── 柬埔寨 ──
    {"country": "柬埔寨", "city": "金边", "variants": ["金边", "Phnom Penh"], "lat": 11.5564, "lng": 104.9282},
    {"country": "柬埔寨", "city": "暹粒", "variants": ["暹粒", "Siem Reap"], "lat": 13.3671, "lng": 103.8448},
    # ── 老挝 ──
    {"country": "老挝", "city": "万象", "variants": ["万象", "Vientiane"], "lat": 17.9757, "lng": 102.6331},
    # ── 文莱 ──
    {"country": "文莱", "city": "斯里巴加湾", "variants": ["斯里巴加湾", "Bandar Seri Begawan"], "lat": 4.9031, "lng": 114.9398},
    # ── 尼泊尔 ──
    {"country": "尼泊尔", "city": "加德满都", "variants": ["加德满都", "Kathmandu"], "lat": 27.7172, "lng": 85.3240},
    # ── 斯里兰卡 ──
    {"country": "斯里兰卡", "city": "科伦坡", "variants": ["科伦坡", "Colombo"], "lat": 6.9271, "lng": 79.8612},
    # ── 马尔代夫 ──
    {"country": "马尔代夫", "city": "马累", "variants": ["马累", "Male", "Malé"], "lat": 4.1755, "lng": 73.5093},
    # ── 缅甸 (扩展) ──
    {"country": "缅甸", "city": "曼德勒", "variants": ["曼德勒", "Mandalay"], "lat": 21.9588, "lng": 96.0891},
    # ── 东帝汶 ──
    {"country": "东帝汶", "city": "帝力", "variants": ["帝力", "Dili"], "lat": -8.5569, "lng": 125.5603},
    # ── 不丹 ──
    {"country": "不丹", "city": "廷布", "variants": ["廷布", "Thimphu"], "lat": 27.4728, "lng": 89.6390},
    # ── 吉尔吉斯斯坦 ──
    {"country": "吉尔吉斯斯坦", "city": "比什凯克", "variants": ["比什凯克", "Bishkek"], "lat": 42.8746, "lng": 74.5698},
    # ── 塔吉克斯坦 ──
    {"country": "塔吉克斯坦", "city": "杜尚别", "variants": ["杜尚别", "Dushanbe"], "lat": 38.5598, "lng": 68.7870},
    # ── 土库曼斯坦 ──
    {"country": "土库曼斯坦", "city": "阿什哈巴德", "variants": ["阿什哈巴德", "Ashgabat"], "lat": 37.9601, "lng": 58.3794},
    # ── 阿塞拜疆 ──
    {"country": "阿塞拜疆", "city": "巴库", "variants": ["巴库", "Baku"], "lat": 40.4093, "lng": 49.8671},
    # ── 格鲁吉亚 ──
    {"country": "格鲁吉亚", "city": "第比利斯", "variants": ["第比利斯", "Tbilisi"], "lat": 41.7151, "lng": 44.8271},
    # ── 亚美尼亚 ──
    {"country": "亚美尼亚", "city": "埃里温", "variants": ["埃里温", "Yerevan"], "lat": 40.1792, "lng": 44.4991},
    # ── 白俄罗斯 ──
    {"country": "白俄罗斯", "city": "明斯克", "variants": ["明斯克", "Minsk"], "lat": 53.9006, "lng": 27.5590},
    # ── 爱沙尼亚 ──
    {"country": "爱沙尼亚", "city": "塔林", "variants": ["塔林", "Tallinn"], "lat": 59.4370, "lng": 24.7536},
    # ── 拉脱维亚 ──
    {"country": "拉脱维亚", "city": "里加", "variants": ["里加", "Riga"], "lat": 56.9496, "lng": 24.1052},
    # ── 立陶宛 ──
    {"country": "立陶宛", "city": "维尔纽斯", "variants": ["维尔纽斯", "Vilnius"], "lat": 54.6872, "lng": 25.2797},
    # ── 爱尔兰 ──
    {"country": "爱尔兰", "city": "都柏林", "variants": ["都柏林", "Dublin"], "lat": 53.3498, "lng": -6.2603},
    # ── 冰岛 ──
    {"country": "冰岛", "city": "雷克雅未克", "variants": ["雷克雅未克", "Reykjavik", "Reykjavík"], "lat": 64.1466, "lng": -21.9426},
    # ── 克罗地亚 ──
    {"country": "克罗地亚", "city": "萨格勒布", "variants": ["萨格勒布", "Zagreb"], "lat": 45.8150, "lng": 15.9819},
    # ── 塞尔维亚 ──
    {"country": "塞尔维亚", "city": "贝尔格莱德", "variants": ["贝尔格莱德", "Belgrade"], "lat": 44.7866, "lng": 20.4489},
    # ── 斯洛文尼亚 ──
    {"country": "斯洛文尼亚", "city": "卢布尔雅那", "variants": ["卢布尔雅那", "Ljubljana"], "lat": 46.0569, "lng": 14.5058},
    # ── 斯洛伐克 ──
    {"country": "斯洛伐克", "city": "布拉迪斯拉发", "variants": ["布拉迪斯拉发", "Bratislava"], "lat": 48.1486, "lng": 17.1077},
    # ── 保加利亚 ──
    {"country": "保加利亚", "city": "索非亚", "variants": ["索非亚", "Sofia"], "lat": 42.6977, "lng": 23.3219},
    # ── 黑山 ──
    {"country": "黑山", "city": "波德戈里察", "variants": ["波德戈里察", "Podgorica"], "lat": 42.4304, "lng": 19.2594},
    # ── 科索沃 ──
    {"country": "科索沃", "city": "普里什蒂纳", "variants": ["普里什蒂纳", "Pristina"], "lat": 42.6629, "lng": 21.1655},
    # ── 波黑 ──
    {"country": "波黑", "city": "萨拉热窝", "variants": ["萨拉热窝", "Sarajevo"], "lat": 43.8563, "lng": 18.4131},
    # ── 北马其顿 ──
    {"country": "北马其顿", "city": "斯科普里", "variants": ["斯科普里", "Skopje"], "lat": 41.9973, "lng": 21.4280},
    # ── 阿尔巴尼亚 ──
    {"country": "阿尔巴尼亚", "city": "地拉那", "variants": ["地拉那", "Tirana"], "lat": 41.3275, "lng": 19.8187},
    # ── 摩洛哥 ──
    {"country": "摩洛哥", "city": "拉巴特", "variants": ["拉巴特", "Rabat"], "lat": 34.0209, "lng": -6.8416},
    {"country": "摩洛哥", "city": "卡萨布兰卡", "variants": ["卡萨布兰卡", "Casablanca"], "lat": 33.5731, "lng": -7.5898},
    # ── 阿尔及利亚 ──
    {"country": "阿尔及利亚", "city": "阿尔及尔", "variants": ["阿尔及尔", "Algiers"], "lat": 36.7538, "lng": 3.0588},
    # ── 突尼斯 ──
    {"country": "突尼斯", "city": "突尼斯市", "variants": ["突尼斯市", "Tunis"], "lat": 36.8065, "lng": 10.1815},
    # ── 利比亚 ──
    {"country": "利比亚", "city": "的黎波里", "variants": ["的黎波里", "Tripoli"], "lat": 32.8872, "lng": 13.1913},
    # ── 苏丹 ──
    {"country": "苏丹", "city": "喀土穆", "variants": ["喀土穆", "Khartoum"], "lat": 15.5007, "lng": 32.5599},
    # ── 南苏丹 ──
    {"country": "南苏丹", "city": "朱巴", "variants": ["朱巴", "Juba"], "lat": 4.8594, "lng": 31.5713},
    # ── 埃塞俄比亚 ──
    {"country": "埃塞俄比亚", "city": "亚的斯亚贝巴", "variants": ["亚的斯亚贝巴", "Addis Ababa"], "lat": 9.0320, "lng": 38.7469},
    # ── 索马里 ──
    {"country": "索马里", "city": "摩加迪沙", "variants": ["摩加迪沙", "Mogadishu"], "lat": 2.0469, "lng": 45.3182},
    # ── 厄立特里亚 ──
    {"country": "厄立特里亚", "city": "阿斯马拉", "variants": ["阿斯马拉", "Asmara"], "lat": 15.3229, "lng": 38.9251},
    # ── 坦桑尼亚 ──
    {"country": "坦桑尼亚", "city": "多多马", "variants": ["多多马", "Dodoma"], "lat": -6.1630, "lng": 35.7516},
    {"country": "坦桑尼亚", "city": "达累斯萨拉姆", "variants": ["达累斯萨拉姆", "Dar es Salaam"], "lat": -6.7924, "lng": 39.2083},
    # ── 乌干达 ──
    {"country": "乌干达", "city": "坎帕拉", "variants": ["坎帕拉", "Kampala"], "lat": 0.3476, "lng": 32.5825},
    # ── 卢旺达 ──
    {"country": "卢旺达", "city": "基加利", "variants": ["基加利", "Kigali"], "lat": -1.9441, "lng": 30.0619},
    # ── 安哥拉 ──
    {"country": "安哥拉", "city": "罗安达", "variants": ["罗安达", "Luanda"], "lat": -8.8390, "lng": 13.2894},
    # ── 津巴布韦 ──
    {"country": "津巴布韦", "city": "哈拉雷", "variants": ["哈拉雷", "Harare"], "lat": -17.8252, "lng": 31.0335},
    # ── 赞比亚 ──
    {"country": "赞比亚", "city": "卢萨卡", "variants": ["卢萨卡", "Lusaka"], "lat": -15.3875, "lng": 28.3228},
    # ── 博茨瓦纳 ──
    {"country": "博茨瓦纳", "city": "哈博罗内", "variants": ["哈博罗内", "Gaborone"], "lat": -24.6282, "lng": 25.9231},
    # ── 纳米比亚 ──
    {"country": "纳米比亚", "city": "温得和克", "variants": ["温得和克", "Windhoek"], "lat": -22.5609, "lng": 17.0658},
    # ── 塞内加尔 ──
    {"country": "塞内加尔", "city": "达喀尔", "variants": ["达喀尔", "Dakar"], "lat": 14.7167, "lng": -17.4677},
    # ── 科特迪瓦 ──
    {"country": "科特迪瓦", "city": "亚穆苏克罗", "variants": ["亚穆苏克罗", "Yamoussoukro"], "lat": 6.8276, "lng": -5.2893},
    {"country": "科特迪瓦", "city": "阿比让", "variants": ["阿比让", "Abidjan"], "lat": 5.3600, "lng": -4.0083},
    # ── 喀麦隆 ──
    {"country": "喀麦隆", "city": "雅温得", "variants": ["雅温得", "Yaounde", "Yaoundé"], "lat": 3.8480, "lng": 11.5021},
    # ── 塞拉利昂 ──
    {"country": "塞拉利昂", "city": "弗里敦", "variants": ["弗里敦", "Freetown"], "lat": 8.4844, "lng": -13.2344},
    # ── 利比里亚 ──
    {"country": "利比里亚", "city": "蒙罗维亚", "variants": ["蒙罗维亚", "Monrovia"], "lat": 6.3004, "lng": -10.7960},
    # ── 马里 ──
    {"country": "马里", "city": "巴马科", "variants": ["巴马科", "Bamako"], "lat": 12.6392, "lng": -8.0029},
    # ── 布基纳法索 ──
    {"country": "布基纳法索", "city": "瓦加杜古", "variants": ["瓦加杜古", "Ouagadougou"], "lat": 12.3714, "lng": -1.5197},
    # ── 尼日尔 ──
    {"country": "尼日尔", "city": "尼亚美", "variants": ["尼亚美", "Niamey"], "lat": 13.5127, "lng": 2.1126},
    # ── 乍得 ──
    {"country": "乍得", "city": "恩贾梅纳", "variants": ["恩贾梅纳", "Ndjamena", "N'Djamena"], "lat": 12.1128, "lng": 15.0493},
    # ── 中非共和国 ──
    {"country": "中非", "city": "班吉", "variants": ["班吉", "Bangui"], "lat": 4.3947, "lng": 18.5582},
    # ── 刚果布 ──
    {"country": "刚果布", "city": "布拉柴维尔", "variants": ["布拉柴维尔", "Brazzaville"], "lat": -4.2634, "lng": 15.2429},
    # ── 加蓬 ──
    {"country": "加蓬", "city": "利伯维尔", "variants": ["利伯维尔", "Libreville"], "lat": 0.4162, "lng": 9.4673},
    # ── 几内亚 ──
    {"country": "几内亚", "city": "科纳克里", "variants": ["科纳克里", "Conakry"], "lat": 9.6412, "lng": -13.5784},
    # ── 毛里塔尼亚 ──
    {"country": "毛里塔尼亚", "city": "努瓦克肖特", "variants": ["努瓦克肖特", "Nouakchott"], "lat": 18.0735, "lng": -15.9582},
    # ── 塞浦路斯 ──
    {"country": "塞浦路斯", "city": "尼科西亚", "variants": ["尼科西亚", "Nicosia"], "lat": 35.1856, "lng": 33.3823},
    # ── 马耳他 ──
    {"country": "马耳他", "city": "瓦莱塔", "variants": ["瓦莱塔", "Valletta"], "lat": 35.8997, "lng": 14.5147},
    # ── 卢森堡 ──
    {"country": "卢森堡", "city": "卢森堡市", "variants": ["卢森堡市", "Luxembourg City", "Luxembourg"], "lat": 49.6117, "lng": 6.1300},
    # ── 摩尔多瓦 ──
    {"country": "摩尔多瓦", "city": "基希讷乌", "variants": ["基希讷乌", "Chisinau", "Chișinău"], "lat": 47.0105, "lng": 28.8638},
    # ── 厄瓜多尔 ──
    {"country": "厄瓜多尔", "city": "基多", "variants": ["基多", "Quito"], "lat": -0.1807, "lng": -78.4678},
    {"country": "厄瓜多尔", "city": "瓜亚基尔", "variants": ["瓜亚基尔", "Guayaquil"], "lat": -2.1700, "lng": -79.9224},
    # ── 玻利维亚 ──
    {"country": "玻利维亚", "city": "苏克雷", "variants": ["苏克雷", "Sucre"], "lat": -19.0333, "lng": -65.2627},
    {"country": "玻利维亚", "city": "拉巴斯", "variants": ["拉巴斯", "La Paz"], "lat": -16.5000, "lng": -68.1500},
    # ── 乌拉圭 ──
    {"country": "乌拉圭", "city": "蒙得维的亚", "variants": ["蒙得维的亚", "Montevideo"], "lat": -34.9011, "lng": -56.1645},
    # ── 巴拉圭 ──
    {"country": "巴拉圭", "city": "亚松森", "variants": ["亚松森", "Asuncion", "Asunción"], "lat": -25.2637, "lng": -57.5759},
    # ── 巴拿马 ──
    {"country": "巴拿马", "city": "巴拿马城", "variants": ["巴拿马城", "Panama City"], "lat": 8.9824, "lng": -79.5199},
    # ── 哥斯达黎加 ──
    {"country": "哥斯达黎加", "city": "圣何塞", "variants": ["圣何塞", "San Jose", "San José"], "lat": 9.9281, "lng": -84.0907},
    # ── 洪都拉斯 ──
    {"country": "洪都拉斯", "city": "特古西加尔巴", "variants": ["特古西加尔巴", "Tegucigalpa"], "lat": 14.0723, "lng": -87.1921},
    # ── 萨尔瓦多 ──
    {"country": "萨尔瓦多", "city": "圣萨尔瓦多", "variants": ["圣萨尔瓦多", "San Salvador"], "lat": 13.6929, "lng": -89.2182},
    # ── 危地马拉 ──
    {"country": "危地马拉", "city": "危地马拉城", "variants": ["危地马拉城", "Guatemala City"], "lat": 14.6349, "lng": -90.5069},
    # ── 尼加拉瓜 ──
    {"country": "尼加拉瓜", "city": "马那瓜", "variants": ["马那瓜", "Managua"], "lat": 12.1140, "lng": -86.2362},
    # ── 多米尼加 ──
    {"country": "多米尼加", "city": "圣多明各", "variants": ["圣多明各", "Santo Domingo"], "lat": 18.4861, "lng": -69.9312},
    # ── 海地 ──
    {"country": "海地", "city": "太子港", "variants": ["太子港", "Port-au-Prince"], "lat": 18.5944, "lng": -72.3074},
    # ── 牙买加 ──
    {"country": "牙买加", "city": "金斯敦", "variants": ["金斯敦", "Kingston"], "lat": 17.9712, "lng": -76.7939},
    # ── 巴哈马 ──
    {"country": "巴哈马", "city": "拿骚", "variants": ["拿骚", "Nassau"], "lat": 25.0343, "lng": -77.3963},
    # ── 特立尼达和多巴哥 ──
    {"country": "特立尼达和多巴哥", "city": "西班牙港", "variants": ["西班牙港", "Port of Spain"], "lat": 10.6549, "lng": -61.5019},
    # ── 斐济 ──
    {"country": "斐济", "city": "苏瓦", "variants": ["苏瓦", "Suva"], "lat": -18.1416, "lng": 178.4419},
    # ── 巴布亚新几内亚 ──
    {"country": "巴布亚新几内亚", "city": "莫尔兹比港", "variants": ["莫尔兹比港", "Port Moresby"], "lat": -9.4438, "lng": 147.1803},
    # ── 毛里求斯 ──
    {"country": "毛里求斯", "city": "路易港", "variants": ["路易港", "Port Louis"], "lat": -20.1609, "lng": 57.5012},
    # ── 马达加斯加 ──
    {"country": "马达加斯加", "city": "塔那那利佛", "variants": ["塔那那利佛", "Antananarivo"], "lat": -18.8792, "lng": 47.5079},
    # ── 印尼 (扩展) ──
    {"country": "印尼", "city": "泗水", "variants": ["泗水", "Surabaya"], "lat": -7.2575, "lng": 112.7521},
    {"country": "印尼", "city": "万隆", "variants": ["万隆", "Bandung"], "lat": -6.9175, "lng": 107.6191},
    {"country": "印尼", "city": "棉兰", "variants": ["棉兰", "Medan"], "lat": 3.5952, "lng": 98.6722},
    {"country": "印尼", "city": "巴厘岛", "variants": ["巴厘岛", "Bali", "登巴萨", "Denpasar"], "lat": -8.6705, "lng": 115.2126},
    # ── 菲律宾 (扩展) ──
    {"country": "菲律宾", "city": "宿务", "variants": ["宿务", "Cebu"], "lat": 10.3157, "lng": 123.8854},
    {"country": "菲律宾", "city": "达沃", "variants": ["达沃", "Davao"], "lat": 7.0730, "lng": 125.6128},
    # ── 越南 (扩展) ──
    {"country": "越南", "city": "岘港", "variants": ["岘港", "Da Nang"], "lat": 16.0544, "lng": 108.2022},
    {"country": "越南", "city": "海防", "variants": ["海防", "Haiphong"], "lat": 20.8449, "lng": 106.6881},
    # ── 泰国 (扩展) ──
    {"country": "泰国", "city": "清迈", "variants": ["清迈", "Chiang Mai"], "lat": 18.7883, "lng": 98.9853},
    {"country": "泰国", "city": "普吉", "variants": ["普吉", "Phuket"], "lat": 7.8804, "lng": 98.3923},
    {"country": "泰国", "city": "芭提雅", "variants": ["芭提雅", "Pattaya"], "lat": 12.9236, "lng": 100.8825},
    # ── 马来西亚 (扩展) ──
    {"country": "马来西亚", "city": "槟城", "variants": ["槟城", "Penang", "George Town"], "lat": 5.4141, "lng": 100.3288},
    {"country": "马来西亚", "city": "新山", "variants": ["新山", "Johor Bahru"], "lat": 1.4927, "lng": 103.7414},
    {"country": "马来西亚", "city": "哥打基纳巴卢", "variants": ["哥打基纳巴卢", "Kota Kinabalu"], "lat": 5.9804, "lng": 116.0735},
    # ── 沙特 (扩展) ──
    {"country": "沙特阿拉伯", "city": "吉达", "variants": ["吉达", "Jeddah"], "lat": 21.5433, "lng": 39.1728},
    {"country": "沙特阿拉伯", "city": "麦加", "variants": ["麦加", "Mecca", "Makkah"], "lat": 21.3891, "lng": 39.8579},
    {"country": "沙特阿拉伯", "city": "麦地那", "variants": ["麦地那", "Medina"], "lat": 24.5247, "lng": 39.5692},
    # ── 伊朗 (扩展) ──
    {"country": "伊朗", "city": "马什哈德", "variants": ["马什哈德", "Mashhad"], "lat": 36.2605, "lng": 59.6168},
    {"country": "伊朗", "city": "设拉子", "variants": ["设拉子", "Shiraz"], "lat": 29.5926, "lng": 52.5836},
    {"country": "伊朗", "city": "大不里士", "variants": ["大不里士", "Tabriz"], "lat": 38.0800, "lng": 46.2919},
    # ── 土耳其 (扩展) ──
    {"country": "土耳其", "city": "伊兹密尔", "variants": ["伊兹密尔", "Izmir"], "lat": 38.4237, "lng": 27.1428},
    {"country": "土耳其", "city": "安塔利亚", "variants": ["安塔利亚", "Antalya"], "lat": 36.8969, "lng": 30.7133},
    # ── 俄罗斯 (扩展) ──
    {"country": "俄罗斯", "city": "叶卡捷琳堡", "variants": ["叶卡捷琳堡", "Yekaterinburg"], "lat": 56.8389, "lng": 60.6057},
    {"country": "俄罗斯", "city": "喀山", "variants": ["喀山", "Kazan"], "lat": 55.7879, "lng": 49.1233},
    {"country": "俄罗斯", "city": "索契", "variants": ["索契", "Sochi"], "lat": 43.6028, "lng": 39.7342},
    {"country": "俄罗斯", "city": "加里宁格勒", "variants": ["加里宁格勒", "Kaliningrad"], "lat": 54.7104, "lng": 20.4522},
    {"country": "俄罗斯", "city": "摩尔曼斯克", "variants": ["摩尔曼斯克", "Murmansk"], "lat": 68.9585, "lng": 33.0827},
    # ── 印度 (扩展) ──
    {"country": "印度", "city": "艾哈迈达巴德", "variants": ["艾哈迈达巴德", "Ahmedabad"], "lat": 23.0225, "lng": 72.5714},
    {"country": "印度", "city": "浦那", "variants": ["浦那", "Pune"], "lat": 18.5204, "lng": 73.8567},
    {"country": "印度", "city": "斋浦尔", "variants": ["斋浦尔", "Jaipur"], "lat": 26.9124, "lng": 75.7873},
    {"country": "印度", "city": "勒克瑙", "variants": ["勒克瑙", "Lucknow"], "lat": 26.8467, "lng": 80.9462},
    # ── 巴西 (扩展) ──
    {"country": "巴西", "city": "萨尔瓦多", "variants": ["萨尔瓦多", "Salvador"], "lat": -12.9714, "lng": -38.5014},
    {"country": "巴西", "city": "福塔莱萨", "variants": ["福塔莱萨", "Fortaleza"], "lat": -3.7319, "lng": -38.5267},
    {"country": "巴西", "city": "贝洛奥里藏特", "variants": ["贝洛奥里藏特", "Belo Horizonte"], "lat": -19.9167, "lng": -43.9345},
    {"country": "巴西", "city": "累西腓", "variants": ["累西腓", "Recife"], "lat": -8.0476, "lng": -34.8770},
    # ── 阿根廷 (扩展) ──
    {"country": "阿根廷", "city": "科尔多瓦", "variants": ["科尔多瓦", "Cordoba", "Córdoba"], "lat": -31.4201, "lng": -64.1888},
    {"country": "阿根廷", "city": "罗萨里奥", "variants": ["罗萨里奥", "Rosario"], "lat": -32.9468, "lng": -60.6393},
    # ── 智利 (扩展) ──
    {"country": "智利", "city": "瓦尔帕莱索", "variants": ["瓦尔帕莱索", "Valparaiso", "Valparaíso"], "lat": -33.0472, "lng": -71.6127},
    # ── 哥伦比亚 (扩展) ──
    {"country": "哥伦比亚", "city": "麦德林", "variants": ["麦德林", "Medellin", "Medellín"], "lat": 6.2476, "lng": -75.5658},
    {"country": "哥伦比亚", "city": "卡利", "variants": ["卡利", "Cali"], "lat": 3.4516, "lng": -76.5320},
    {"country": "哥伦比亚", "city": "卡塔赫纳", "variants": ["卡塔赫纳", "Cartagena"], "lat": 10.3910, "lng": -75.5144},
    # ── 秘鲁 (扩展) ──
    {"country": "秘鲁", "city": "库斯科", "variants": ["库斯科", "Cusco", "Cuzco"], "lat": -13.5320, "lng": -71.9675},
    # ── 加拿大 (扩展) ──
    {"country": "加拿大", "city": "卡尔加里", "variants": ["卡尔加里", "Calgary"], "lat": 51.0447, "lng": -114.0719},
    {"country": "加拿大", "city": "埃德蒙顿", "variants": ["埃德蒙顿", "Edmonton"], "lat": 53.5461, "lng": -113.4938},
    {"country": "加拿大", "city": "魁北克城", "variants": ["魁北克城", "Quebec City", "Québec"], "lat": 46.8139, "lng": -71.2080},
    # ── 澳大利亚 (扩展) ──
    {"country": "澳大利亚", "city": "阿德莱德", "variants": ["阿德莱德", "Adelaide"], "lat": -34.9285, "lng": 138.6007},
    {"country": "澳大利亚", "city": "达尔文", "variants": ["达尔文", "Darwin"], "lat": -12.4634, "lng": 130.8456},
    {"country": "澳大利亚", "city": "霍巴特", "variants": ["霍巴特", "Hobart"], "lat": -42.8821, "lng": 147.3272},
    # ── 西班牙 (扩展) ──
    {"country": "西班牙", "city": "瓦伦西亚", "variants": ["瓦伦西亚", "Valencia"], "lat": 39.4699, "lng": -0.3763},
    {"country": "西班牙", "city": "塞维利亚", "variants": ["塞维利亚", "Seville", "Sevilla"], "lat": 37.3891, "lng": -5.9845},
    {"country": "西班牙", "city": "毕尔巴鄂", "variants": ["毕尔巴鄂", "Bilbao"], "lat": 43.2630, "lng": -2.9350},
    # ── 意大利 (扩展) ──
    {"country": "意大利", "city": "那不勒斯", "variants": ["那不勒斯", "Naples", "Napoli"], "lat": 40.8518, "lng": 14.2681},
    {"country": "意大利", "city": "都灵", "variants": ["都灵", "Turin", "Torino"], "lat": 45.0703, "lng": 7.6869},
    # ── 德国 (扩展) ──
    {"country": "德国", "city": "斯图加特", "variants": ["斯图加特", "Stuttgart"], "lat": 48.7758, "lng": 9.1829},
    {"country": "德国", "city": "杜塞尔多夫", "variants": ["杜塞尔多夫", "Dusseldorf", "Düsseldorf"], "lat": 51.2277, "lng": 6.7735},
    {"country": "德国", "city": "莱比锡", "variants": ["莱比锡", "Leipzig"], "lat": 51.3397, "lng": 12.3731},
    # ── 法国 (扩展) ──
    {"country": "法国", "city": "尼斯", "variants": ["尼斯", "Nice"], "lat": 43.7102, "lng": 7.2620},
    {"country": "法国", "city": "图卢兹", "variants": ["图卢兹", "Toulouse"], "lat": 43.6047, "lng": 1.4442},
    {"country": "法国", "city": "斯特拉斯堡", "variants": ["斯特拉斯堡", "Strasbourg"], "lat": 48.5734, "lng": 7.7521},
    # ── 英国 (扩展) ──
    {"country": "英国", "city": "格拉斯哥", "variants": ["格拉斯哥", "Glasgow"], "lat": 55.8642, "lng": -4.2518},
    {"country": "英国", "city": "牛津", "variants": ["牛津", "Oxford"], "lat": 51.7520, "lng": -1.2577},
    {"country": "英国", "city": "贝尔法斯特", "variants": ["贝尔法斯特", "Belfast"], "lat": 54.5973, "lng": -5.9301},
    # ── 荷兰 (扩展) ──
    {"country": "荷兰", "city": "海牙", "variants": ["海牙", "The Hague", "Den Haag"], "lat": 52.0705, "lng": 4.3007},
    # ── 瑞典 (扩展) ──
    {"country": "瑞典", "city": "哥德堡", "variants": ["哥德堡", "Gothenburg", "Göteborg"], "lat": 57.7089, "lng": 11.9746},
    {"country": "瑞典", "city": "马尔默", "variants": ["马尔默", "Malmo", "Malmö"], "lat": 55.6050, "lng": 13.0038},
    # ── 挪威 (扩展) ──
    {"country": "挪威", "city": "卑尔根", "variants": ["卑尔根", "Bergen"], "lat": 60.3913, "lng": 5.3221},
    # ── 芬兰 (扩展) ──
    {"country": "芬兰", "city": "坦佩雷", "variants": ["坦佩雷", "Tampere"], "lat": 61.4978, "lng": 23.7610},
    # ── 波兰 (扩展) ──
    {"country": "波兰", "city": "格但斯克", "variants": ["格但斯克", "Gdansk", "Gdańsk"], "lat": 54.3520, "lng": 18.6466},
    # ── 瑞士 (扩展) ──
    {"country": "瑞士", "city": "伯尔尼", "variants": ["伯尔尼", "Bern"], "lat": 46.9480, "lng": 7.4474},
    {"country": "瑞士", "city": "巴塞尔", "variants": ["巴塞尔", "Basel"], "lat": 47.5596, "lng": 7.5886},
    # ── 日本 (扩展) ──
    {"country": "日本", "city": "神户", "variants": ["神户", "Kobe"], "lat": 34.6901, "lng": 135.1955},
    {"country": "日本", "city": "广岛", "variants": ["广岛", "Hiroshima"], "lat": 34.3853, "lng": 132.4553},
    {"country": "日本", "city": "仙台", "variants": ["仙台", "Sendai"], "lat": 38.2682, "lng": 140.8694},
    # ── 南非 (扩展) ──
    {"country": "南非", "city": "德班", "variants": ["德班", "Durban"], "lat": -29.8587, "lng": 31.0218},
    # ── 埃及 (扩展) ──
    {"country": "埃及", "city": "苏伊士", "variants": ["苏伊士", "Suez"], "lat": 29.9668, "lng": 32.5498},
    # ── 尼日利亚 (扩展) ──
    {"country": "尼日利亚", "city": "卡诺", "variants": ["卡诺", "Kano"], "lat": 12.0022, "lng": 8.5920},
    {"country": "尼日利亚", "city": "哈科特港", "variants": ["哈科特港", "Port Harcourt"], "lat": 4.8156, "lng": 7.0498},
    {"country": "尼日利亚", "city": "伊巴丹", "variants": ["伊巴丹", "Ibadan"], "lat": 7.3775, "lng": 3.9470},
    {"country": "尼日利亚", "city": "卡杜纳", "variants": ["卡杜纳", "Kaduna"], "lat": 10.5264, "lng": 7.4388},
    {"country": "尼日利亚", "city": "贝宁城", "variants": ["贝宁城", "Benin City"], "lat": 6.3350, "lng": 5.6037},
    # ── 北非 (扩展) ──
    {"country": "摩洛哥", "city": "马拉喀什", "variants": ["马拉喀什", "Marrakech", "Marrakesh"], "lat": 31.6295, "lng": -7.9811},
    {"country": "摩洛哥", "city": "非斯", "variants": ["非斯", "Fes", "Fez"], "lat": 34.0331, "lng": -5.0000},
    {"country": "摩洛哥", "city": "丹吉尔", "variants": ["丹吉尔", "Tangier", "Tanger"], "lat": 35.7673, "lng": -5.7998},
    {"country": "摩洛哥", "city": "阿加迪尔", "variants": ["阿加迪尔", "Agadir"], "lat": 30.4278, "lng": -9.5981},
    {"country": "阿尔及利亚", "city": "奥兰", "variants": ["奥兰", "Oran"], "lat": 35.6971, "lng": -0.6308},
    {"country": "阿尔及利亚", "city": "君士坦丁", "variants": ["君士坦丁", "Constantine"], "lat": 36.3650, "lng": 6.6147},
    {"country": "阿尔及利亚", "city": "安纳巴", "variants": ["安纳巴", "Annaba"], "lat": 36.9000, "lng": 7.7667},
    {"country": "突尼斯", "city": "斯法克斯", "variants": ["斯法克斯", "Sfax"], "lat": 34.7400, "lng": 10.7600},
    {"country": "突尼斯", "city": "苏塞", "variants": ["苏塞", "Sousse"], "lat": 35.8333, "lng": 10.6333},
    {"country": "利比亚", "city": "班加西", "variants": ["班加西", "Benghazi"], "lat": 32.1167, "lng": 20.0667},
    {"country": "利比亚", "city": "米苏拉塔", "variants": ["米苏拉塔", "Misrata"], "lat": 32.3754, "lng": 15.0925},
    {"country": "苏丹", "city": "苏丹港", "variants": ["苏丹港", "Port Sudan"], "lat": 19.6158, "lng": 37.2164},
    {"country": "苏丹", "city": "恩图曼", "variants": ["恩图曼", "Omdurman"], "lat": 15.6445, "lng": 32.4779},
    # ── 东非 (扩展) ──
    {"country": "埃塞俄比亚", "city": "德雷达瓦", "variants": ["德雷达瓦", "Dire Dawa"], "lat": 9.6000, "lng": 41.8500},
    {"country": "埃塞俄比亚", "city": "默克莱", "variants": ["默克莱", "Mekelle", "Mekele"], "lat": 13.4967, "lng": 39.4753},
    {"country": "埃塞俄比亚", "city": "巴赫达尔", "variants": ["巴赫达尔", "Bahir Dar"], "lat": 11.5936, "lng": 37.3908},
    {"country": "索马里", "city": "哈尔格萨", "variants": ["哈尔格萨", "Hargeisa"], "lat": 9.5600, "lng": 44.0650},
    {"country": "索马里", "city": "柏培拉", "variants": ["柏培拉", "Berbera"], "lat": 10.4397, "lng": 45.0143},
    {"country": "索马里", "city": "基斯马尤", "variants": ["基斯马尤", "Kismayo"], "lat": -0.3582, "lng": 42.5454},
    {"country": "肯尼亚", "city": "蒙巴萨", "variants": ["蒙巴萨", "Mombasa"], "lat": -4.0435, "lng": 39.6682},
    {"country": "肯尼亚", "city": "基苏木", "variants": ["基苏木", "Kisumu"], "lat": -0.0917, "lng": 34.7680},
    {"country": "坦桑尼亚", "city": "桑给巴尔", "variants": ["桑给巴尔", "Zanzibar", "Zanzibar City"], "lat": -6.1659, "lng": 39.2026},
    {"country": "坦桑尼亚", "city": "阿鲁沙", "variants": ["阿鲁沙", "Arusha"], "lat": -3.3869, "lng": 36.6830},
    {"country": "坦桑尼亚", "city": "姆万扎", "variants": ["姆万扎", "Mwanza"], "lat": -2.5167, "lng": 32.9000},
    {"country": "乌干达", "city": "恩德培", "variants": ["恩德培", "Entebbe"], "lat": 0.0514, "lng": 32.4637},
    {"country": "乌干达", "city": "古卢", "variants": ["古卢", "Gulu"], "lat": 2.7746, "lng": 32.2990},
    {"country": "卢旺达", "city": "布塔雷", "variants": ["布塔雷", "Butare", "Huye"], "lat": -2.5967, "lng": 29.7394},
    {"country": "马达加斯加", "city": "图阿马西纳", "variants": ["图阿马西纳", "Toamasina", "Tamatave"], "lat": -18.1492, "lng": 49.4023},
    {"country": "马达加斯加", "city": "安齐拉贝", "variants": ["安齐拉贝", "Antsirabe"], "lat": -19.8667, "lng": 47.0333},
    {"country": "吉布提", "city": "吉布提市", "variants": ["吉布提市", "Djibouti City", "Djibouti"], "lat": 11.5806, "lng": 43.1480},
    {"country": "布隆迪", "city": "布琼布拉", "variants": ["布琼布拉", "Bujumbura"], "lat": -3.3761, "lng": 29.3600},
    {"country": "布隆迪", "city": "基特加", "variants": ["基特加", "Gitega"], "lat": -3.4264, "lng": 29.9306},
    {"country": "科摩罗", "city": "莫罗尼", "variants": ["莫罗尼", "Moroni"], "lat": -11.7172, "lng": 43.2473},
    {"country": "塞舌尔", "city": "维多利亚", "variants": ["维多利亚", "Victoria"], "lat": -4.6191, "lng": 55.4513},
    {"country": "毛里求斯", "city": "鸠比", "variants": ["鸠比", "Curepipe"], "lat": -20.3162, "lng": 57.5280},
    # ── 西非 (扩展) ──
    {"country": "加纳", "city": "库马西", "variants": ["库马西", "Kumasi"], "lat": 6.6666, "lng": -1.6163},
    {"country": "加纳", "city": "塔马利", "variants": ["塔马利", "Tamale"], "lat": 9.4075, "lng": -0.8533},
    {"country": "加纳", "city": "特马", "variants": ["特马", "Tema"], "lat": 5.6380, "lng": -0.0167},
    {"country": "塞内加尔", "city": "捷斯", "variants": ["捷斯", "Thiès", "Thies"], "lat": 14.7894, "lng": -16.9270},
    {"country": "塞内加尔", "city": "图巴", "variants": ["图巴", "Touba"], "lat": 14.8500, "lng": -15.8833},
    {"country": "科特迪瓦", "city": "布瓦凯", "variants": ["布瓦凯", "Bouaké", "Bouake"], "lat": 7.6833, "lng": -5.0333},
    {"country": "科特迪瓦", "city": "圣佩德罗", "variants": ["圣佩德罗", "San Pedro", "San-Pédro"], "lat": 4.7333, "lng": -6.6167},
    {"country": "喀麦隆", "city": "杜阿拉", "variants": ["杜阿拉", "Douala"], "lat": 4.0511, "lng": 9.7679},
    {"country": "喀麦隆", "city": "加鲁阿", "variants": ["加鲁阿", "Garoua"], "lat": 9.3000, "lng": 13.4000},
    {"country": "喀麦隆", "city": "巴门达", "variants": ["巴门达", "Bamenda"], "lat": 5.9333, "lng": 10.1667},
    {"country": "马里", "city": "廷巴克图", "variants": ["廷巴克图", "Timbuktu", "Tombouctou"], "lat": 16.7667, "lng": -3.0000},
    {"country": "马里", "city": "莫普提", "variants": ["莫普提", "Mopti"], "lat": 14.5000, "lng": -4.2000},
    {"country": "马里", "city": "塞古", "variants": ["塞古", "Ségou", "Segou"], "lat": 13.4500, "lng": -6.2667},
    {"country": "布基纳法索", "city": "博博迪乌拉索", "variants": ["博博迪乌拉索", "Bobo-Dioulasso"], "lat": 11.1833, "lng": -4.2833},
    {"country": "尼日尔", "city": "津德尔", "variants": ["津德尔", "Zinder"], "lat": 13.8000, "lng": 8.9833},
    {"country": "尼日尔", "city": "阿加德兹", "variants": ["阿加德兹", "Agadez"], "lat": 16.9733, "lng": 7.9911},
    {"country": "几内亚", "city": "恩泽雷科雷", "variants": ["恩泽雷科雷", "Nzérékoré", "Nzerekore"], "lat": 7.7500, "lng": -8.8167},
    {"country": "几内亚", "city": "康康", "variants": ["康康", "Kankan"], "lat": 10.3833, "lng": -9.3000},
    {"country": "毛里塔尼亚", "city": "努瓦迪布", "variants": ["努瓦迪布", "Nouadhibou"], "lat": 20.9333, "lng": -17.0333},
    {"country": "冈比亚", "city": "班珠尔", "variants": ["班珠尔", "Banjul"], "lat": 13.4531, "lng": -16.5775},
    {"country": "冈比亚", "city": "萨拉昆达", "variants": ["萨拉昆达", "Serrekunda", "Serekunda"], "lat": 13.4383, "lng": -16.6778},
    {"country": "几内亚比绍", "city": "比绍", "variants": ["比绍", "Bissau"], "lat": 11.8636, "lng": -15.5846},
    {"country": "多哥", "city": "洛美", "variants": ["洛美", "Lomé", "Lome"], "lat": 6.1304, "lng": 1.2233},
    {"country": "多哥", "city": "卡拉", "variants": ["卡拉", "Kara"], "lat": 9.5500, "lng": 1.1833},
    {"country": "贝宁", "city": "波多诺伏", "variants": ["波多诺伏", "Porto-Novo"], "lat": 6.4969, "lng": 2.6289},
    {"country": "贝宁", "city": "科托努", "variants": ["科托努", "Cotonou"], "lat": 6.3703, "lng": 2.3912},
    {"country": "塞拉利昂", "city": "博城", "variants": ["博城", "Bo"], "lat": 7.9564, "lng": -11.7400},
    {"country": "塞拉利昂", "city": "凯内马", "variants": ["凯内马", "Kenema"], "lat": 7.8767, "lng": -11.1900},
    {"country": "利比里亚", "city": "布坎南", "variants": ["布坎南", "Buchanan"], "lat": 5.8767, "lng": -10.0467},
    {"country": "佛得角", "city": "普拉亚", "variants": ["普拉亚", "Praia"], "lat": 14.9170, "lng": -23.5090},
    {"country": "佛得角", "city": "明德卢", "variants": ["明德卢", "Mindelo"], "lat": 16.8833, "lng": -24.9833},
    # ── 中非 (扩展) ──
    {"country": "刚果", "city": "卢本巴希", "variants": ["卢本巴希", "Lubumbashi"], "lat": -11.6646, "lng": 27.4794},
    {"country": "刚果", "city": "戈马", "variants": ["戈马", "Goma"], "lat": -1.6741, "lng": 29.2345},
    {"country": "刚果", "city": "布卡武", "variants": ["布卡武", "Bukavu"], "lat": -2.5000, "lng": 28.8667},
    {"country": "刚果", "city": "基桑加尼", "variants": ["基桑加尼", "Kisangani"], "lat": 0.5167, "lng": 25.2000},
    {"country": "刚果", "city": "姆布吉马伊", "variants": ["姆布吉马伊", "Mbuji-Mayi"], "lat": -6.1333, "lng": 23.6000},
    {"country": "刚果布", "city": "黑角", "variants": ["黑角", "Pointe-Noire"], "lat": -4.7889, "lng": 11.8653},
    {"country": "乍得", "city": "蒙杜", "variants": ["蒙杜", "Moundou"], "lat": 8.5667, "lng": 16.0833},
    {"country": "加蓬", "city": "让蒂尔港", "variants": ["让蒂尔港", "Port-Gentil"], "lat": -0.7193, "lng": 8.7815},
    {"country": "赤道几内亚", "city": "马拉博", "variants": ["马拉博", "Malabo"], "lat": 3.7523, "lng": 8.7741},
    {"country": "赤道几内亚", "city": "巴塔", "variants": ["巴塔", "Bata"], "lat": 1.8500, "lng": 9.7500},
    {"country": "圣多美和普林西比", "city": "圣多美", "variants": ["圣多美", "São Tomé", "Sao Tome"], "lat": 0.3360, "lng": 6.7270},
    # ── 南部非洲 (扩展) ──
    {"country": "安哥拉", "city": "本格拉", "variants": ["本格拉", "Benguela"], "lat": -12.5783, "lng": 13.4072},
    {"country": "安哥拉", "city": "万博", "variants": ["万博", "Huambo"], "lat": -12.7667, "lng": 15.7333},
    {"country": "安哥拉", "city": "洛比托", "variants": ["洛比托", "Lobito"], "lat": -12.3481, "lng": 13.5456},
    {"country": "津巴布韦", "city": "布拉瓦约", "variants": ["布拉瓦约", "Bulawayo"], "lat": -20.1500, "lng": 28.5833},
    {"country": "津巴布韦", "city": "穆塔雷", "variants": ["穆塔雷", "Mutare"], "lat": -18.9667, "lng": 32.6667},
    {"country": "赞比亚", "city": "恩多拉", "variants": ["恩多拉", "Ndola"], "lat": -12.9667, "lng": 28.6333},
    {"country": "赞比亚", "city": "基特韦", "variants": ["基特韦", "Kitwe"], "lat": -12.8167, "lng": 28.2000},
    {"country": "莫桑比克", "city": "贝拉", "variants": ["贝拉", "Beira"], "lat": -19.8333, "lng": 34.8500},
    {"country": "莫桑比克", "city": "楠普拉", "variants": ["楠普拉", "Nampula"], "lat": -15.1167, "lng": 39.2667},
    {"country": "马拉维", "city": "布兰太尔", "variants": ["布兰太尔", "Blantyre"], "lat": -15.7861, "lng": 35.0058},
    {"country": "博茨瓦纳", "city": "弗朗西斯敦", "variants": ["弗朗西斯敦", "Francistown"], "lat": -21.1667, "lng": 27.5167},
    {"country": "纳米比亚", "city": "鲸湾港", "variants": ["鲸湾港", "Walvis Bay"], "lat": -22.9575, "lng": 14.5053},
    {"country": "纳米比亚", "city": "斯瓦科普蒙德", "variants": ["斯瓦科普蒙德", "Swakopmund"], "lat": -22.6833, "lng": 14.5333},
    {"country": "莱索托", "city": "马塞卢", "variants": ["马塞卢", "Maseru"], "lat": -29.3150, "lng": 27.4876},
    {"country": "斯威士兰", "city": "姆巴巴内", "variants": ["姆巴巴内", "Mbabane"], "lat": -26.3200, "lng": 31.1349},
    {"country": "斯威士兰", "city": "曼齐尼", "variants": ["曼齐尼", "Manzini"], "lat": -26.4833, "lng": 31.3667},
    # ── 美国 (扩展) ──
    {"country": "美国", "city": "圣安东尼奥", "variants": ["圣安东尼奥", "San Antonio"], "lat": 29.4241, "lng": -98.4936},
    {"country": "美国", "city": "达拉斯", "variants": ["达拉斯", "Dallas"], "lat": 32.7767, "lng": -96.7970},
    {"country": "美国", "city": "圣何塞", "variants": ["圣何塞", "San Jose"], "lat": 37.3382, "lng": -121.8863},
    {"country": "美国", "city": "夏洛特", "variants": ["夏洛特", "Charlotte"], "lat": 35.2271, "lng": -80.8431},
    {"country": "美国", "city": "印第安纳波利斯", "variants": ["印第安纳波利斯", "Indianapolis"], "lat": 39.7684, "lng": -86.1581},
    {"country": "美国", "city": "哥伦布", "variants": ["哥伦布", "Columbus"], "lat": 39.9612, "lng": -82.9988},
    {"country": "美国", "city": "明尼阿波利斯", "variants": ["明尼阿波利斯", "Minneapolis"], "lat": 44.9778, "lng": -93.2650},
    {"country": "美国", "city": "匹兹堡", "variants": ["匹兹堡", "Pittsburgh"], "lat": 40.4406, "lng": -79.9959},
    {"country": "美国", "city": "辛辛那提", "variants": ["辛辛那提", "Cincinnati"], "lat": 39.1031, "lng": -84.5120},
    {"country": "美国", "city": "堪萨斯城", "variants": ["堪萨斯城", "Kansas City"], "lat": 39.0997, "lng": -94.5786},
    {"country": "美国", "city": "盐湖城", "variants": ["盐湖城", "Salt Lake City"], "lat": 40.7608, "lng": -111.8910},
    {"country": "美国", "city": "罗利", "variants": ["罗利", "Raleigh"], "lat": 35.7796, "lng": -78.6382},
    {"country": "美国", "city": "密尔沃基", "variants": ["密尔沃基", "Milwaukee"], "lat": 43.0389, "lng": -87.9065},
    {"country": "美国", "city": "坦帕", "variants": ["坦帕", "Tampa"], "lat": 27.9506, "lng": -82.4572},
    {"country": "美国", "city": "奥兰多", "variants": ["奥兰多", "Orlando"], "lat": 28.5383, "lng": -81.3792},
    {"country": "美国", "city": "圣路易斯", "variants": ["圣路易斯", "St. Louis", "Saint Louis"], "lat": 38.6270, "lng": -90.1994},
    {"country": "美国", "city": "克利夫兰", "variants": ["克利夫兰", "Cleveland"], "lat": 41.4993, "lng": -81.6944},
    {"country": "美国", "city": "萨克拉门托", "variants": ["萨克拉门托", "Sacramento"], "lat": 38.5816, "lng": -121.4944},
    {"country": "美国", "city": "巴尔的摩", "variants": ["巴尔的摩", "Baltimore"], "lat": 39.2904, "lng": -76.6122},
    {"country": "美国", "city": "圣保罗", "variants": ["Saint Paul", "St Paul"], "lat": 44.9537, "lng": -93.0900},
    # ── 香港/澳门 (修正归属) ──
    {"country": "中国", "city": "中环", "variants": ["中环", "Central"], "lat": 22.2797, "lng": 114.1586},
    {"country": "中国", "city": "铜锣湾", "variants": ["铜锣湾", "Causeway Bay"], "lat": 22.2807, "lng": 114.1838},
]

# Build variant → city lookup (case-insensitive, one pass)
_VARIANT_MAP: list[tuple[str, dict]] = []
for c in _CITIES:
    for v in c["variants"]:
        _VARIANT_MAP.append((v.lower(), c))

# Country-level fallback (used only when no city is found in text)
_COUNTRIES: list[dict] = [
    # Capitals instead of geographic centroids
    {"country": "美国", "variants": ["美国", "US", "USA", "United States", "America"], "lat": 38.9072, "lng": -77.0369, "capital": "华盛顿"},
    {"country": "中国", "variants": ["中国", "China", "PRC"], "lat": 39.9042, "lng": 116.4074, "capital": "北京"},
    {"country": "俄罗斯", "variants": ["俄罗斯", "Russia"], "lat": 55.7558, "lng": 37.6173, "capital": "莫斯科"},
    {"country": "英国", "variants": ["英国", "UK", "Britain", "United Kingdom"], "lat": 51.5074, "lng": -0.1278, "capital": "伦敦"},
    {"country": "德国", "variants": ["德国", "Germany"], "lat": 52.5200, "lng": 13.4050, "capital": "柏林"},
    {"country": "法国", "variants": ["法国", "France"], "lat": 48.8566, "lng": 2.3522, "capital": "巴黎"},
    {"country": "日本", "variants": ["日本", "Japan"], "lat": 35.6762, "lng": 139.6503, "capital": "东京"},
    {"country": "印度", "variants": ["印度", "India"], "lat": 28.6139, "lng": 77.2090, "capital": "新德里"},
    {"country": "巴西", "variants": ["巴西", "Brazil"], "lat": -15.7934, "lng": -47.8822, "capital": "巴西利亚"},
    {"country": "澳大利亚", "variants": ["澳大利亚", "Australia"], "lat": -35.2809, "lng": 149.1300, "capital": "堪培拉"},
    {"country": "加拿大", "variants": ["加拿大", "Canada"], "lat": 45.4215, "lng": -75.6972, "capital": "渥太华"},
    {"country": "韩国", "variants": ["韩国", "South Korea", "Korea"], "lat": 37.5665, "lng": 126.9780, "capital": "首尔"},
    {"country": "伊朗", "variants": ["伊朗", "Iran"], "lat": 35.6892, "lng": 51.3890, "capital": "德黑兰"},
    {"country": "以色列", "variants": ["以色列", "Israel"], "lat": 31.7683, "lng": 35.2137, "capital": "耶路撒冷"},
    {"country": "巴勒斯坦", "variants": ["巴勒斯坦", "Palestine"], "lat": 31.5017, "lng": 34.4668, "capital": "拉姆安拉"},
    {"country": "乌克兰", "variants": ["乌克兰", "Ukraine"], "lat": 50.4501, "lng": 30.5234, "capital": "基辅"},
    {"country": "土耳其", "variants": ["土耳其", "Turkey"], "lat": 39.9334, "lng": 32.8597, "capital": "安卡拉"},
    {"country": "沙特阿拉伯", "variants": ["沙特阿拉伯", "沙特", "Saudi Arabia", "Saudi"], "lat": 24.7136, "lng": 46.6753, "capital": "利雅得"},
    {"country": "阿联酋", "variants": ["阿联酋", "UAE", "United Arab Emirates"], "lat": 25.2048, "lng": 55.2708, "capital": "阿布扎比"},
    {"country": "欧盟", "variants": ["欧盟", "European Union", "EU", "Europe", "欧洲", "Eurozone"], "lat": 50.8503, "lng": 4.3517, "capital": "布鲁塞尔"},
    # ── 东亚 ──
    {"country": "朝鲜", "variants": ["朝鲜", "North Korea", "DPRK"], "lat": 39.0392, "lng": 125.7625, "capital": "平壤"},
    {"country": "蒙古", "variants": ["蒙古", "Mongolia"], "lat": 47.8864, "lng": 106.9057, "capital": "乌兰巴托"},
    # ── 东南亚 ──
    {"country": "印尼", "variants": ["印尼", "印度尼西亚", "Indonesia"], "lat": -6.2088, "lng": 106.8456, "capital": "雅加达"},
    {"country": "越南", "variants": ["越南", "Vietnam"], "lat": 21.0278, "lng": 105.8342, "capital": "河内"},
    {"country": "泰国", "variants": ["泰国", "Thailand"], "lat": 13.7563, "lng": 100.5018, "capital": "曼谷"},
    {"country": "马来西亚", "variants": ["马来西亚", "Malaysia"], "lat": 3.1390, "lng": 101.6869, "capital": "吉隆坡"},
    {"country": "新加坡", "variants": ["新加坡", "Singapore"], "lat": 1.3521, "lng": 103.8198, "capital": "新加坡"},
    {"country": "菲律宾", "variants": ["菲律宾", "Philippines"], "lat": 14.5995, "lng": 120.9842, "capital": "马尼拉"},
    {"country": "缅甸", "variants": ["缅甸", "Myanmar", "Burma"], "lat": 19.7633, "lng": 96.0785, "capital": "内比都"},
    {"country": "柬埔寨", "variants": ["柬埔寨", "Cambodia"], "lat": 11.5564, "lng": 104.9282, "capital": "金边"},
    {"country": "老挝", "variants": ["老挝", "Laos"], "lat": 17.9757, "lng": 102.6331, "capital": "万象"},
    {"country": "文莱", "variants": ["文莱", "Brunei"], "lat": 4.9031, "lng": 114.9398, "capital": "斯里巴加湾"},
    {"country": "东帝汶", "variants": ["东帝汶", "Timor-Leste", "East Timor"], "lat": -8.5569, "lng": 125.5603, "capital": "帝力"},
    # ── 南亚 ──
    {"country": "巴基斯坦", "variants": ["巴基斯坦", "Pakistan"], "lat": 33.6844, "lng": 73.0479, "capital": "伊斯兰堡"},
    {"country": "孟加拉国", "variants": ["孟加拉国", "孟加拉", "Bangladesh"], "lat": 23.8103, "lng": 90.4125, "capital": "达卡"},
    {"country": "尼泊尔", "variants": ["尼泊尔", "Nepal"], "lat": 27.7172, "lng": 85.3240, "capital": "加德满都"},
    {"country": "斯里兰卡", "variants": ["斯里兰卡", "Sri Lanka"], "lat": 6.9271, "lng": 79.8612, "capital": "科伦坡"},
    {"country": "马尔代夫", "variants": ["马尔代夫", "Maldives"], "lat": 4.1755, "lng": 73.5093, "capital": "马累"},
    {"country": "不丹", "variants": ["不丹", "Bhutan"], "lat": 27.4728, "lng": 89.6390, "capital": "廷布"},
    {"country": "阿富汗", "variants": ["阿富汗", "Afghanistan"], "lat": 34.5553, "lng": 69.2075, "capital": "喀布尔"},
    # ── 中亚 ──
    {"country": "哈萨克斯坦", "variants": ["哈萨克斯坦", "Kazakhstan"], "lat": 51.1694, "lng": 71.4491, "capital": "阿斯塔纳"},
    {"country": "乌兹别克斯坦", "variants": ["乌兹别克斯坦", "Uzbekistan"], "lat": 41.2995, "lng": 69.2401, "capital": "塔什干"},
    {"country": "吉尔吉斯斯坦", "variants": ["吉尔吉斯斯坦", "Kyrgyzstan"], "lat": 42.8746, "lng": 74.5698, "capital": "比什凯克"},
    {"country": "塔吉克斯坦", "variants": ["塔吉克斯坦", "Tajikistan"], "lat": 38.5598, "lng": 68.7870, "capital": "杜尚别"},
    {"country": "土库曼斯坦", "variants": ["土库曼斯坦", "Turkmenistan"], "lat": 37.9601, "lng": 58.3794, "capital": "阿什哈巴德"},
    # ── 中东 (扩展) ──
    {"country": "伊拉克", "variants": ["伊拉克", "Iraq"], "lat": 33.3152, "lng": 44.3661, "capital": "巴格达"},
    {"country": "叙利亚", "variants": ["叙利亚", "Syria"], "lat": 33.5138, "lng": 36.2765, "capital": "大马士革"},
    {"country": "也门", "variants": ["也门", "Yemen"], "lat": 15.3694, "lng": 44.1910, "capital": "萨那"},
    {"country": "约旦", "variants": ["约旦", "Jordan"], "lat": 31.9454, "lng": 35.9284, "capital": "安曼"},
    {"country": "黎巴嫩", "variants": ["黎巴嫩", "Lebanon"], "lat": 33.8938, "lng": 35.5018, "capital": "贝鲁特"},
    {"country": "卡塔尔", "variants": ["卡塔尔", "Qatar"], "lat": 25.2854, "lng": 51.5310, "capital": "多哈"},
    {"country": "科威特", "variants": ["科威特", "Kuwait"], "lat": 29.3759, "lng": 47.9774, "capital": "科威特城"},
    {"country": "巴林", "variants": ["巴林", "Bahrain"], "lat": 26.2285, "lng": 50.5860, "capital": "麦纳麦"},
    {"country": "阿曼", "variants": ["阿曼", "Oman"], "lat": 23.5880, "lng": 58.3829, "capital": "马斯喀特"},
    # ── 高加索 ──
    {"country": "阿塞拜疆", "variants": ["阿塞拜疆", "Azerbaijan"], "lat": 40.4093, "lng": 49.8671, "capital": "巴库"},
    {"country": "格鲁吉亚", "variants": ["格鲁吉亚", "Georgia"], "lat": 41.7151, "lng": 44.8271, "capital": "第比利斯"},
    {"country": "亚美尼亚", "variants": ["亚美尼亚", "Armenia"], "lat": 40.1792, "lng": 44.4991, "capital": "埃里温"},
    # ── 东欧/独联体 ──
    {"country": "白俄罗斯", "variants": ["白俄罗斯", "Belarus"], "lat": 53.9006, "lng": 27.5590, "capital": "明斯克"},
    {"country": "摩尔多瓦", "variants": ["摩尔多瓦", "Moldova"], "lat": 47.0105, "lng": 28.8638, "capital": "基希讷乌"},
    # ── 波罗的海 ──
    {"country": "爱沙尼亚", "variants": ["爱沙尼亚", "Estonia"], "lat": 59.4370, "lng": 24.7536, "capital": "塔林"},
    {"country": "拉脱维亚", "variants": ["拉脱维亚", "Latvia"], "lat": 56.9496, "lng": 24.1052, "capital": "里加"},
    {"country": "立陶宛", "variants": ["立陶宛", "Lithuania"], "lat": 54.6872, "lng": 25.2797, "capital": "维尔纽斯"},
    # ── 北欧 ──
    {"country": "瑞典", "variants": ["瑞典", "Sweden"], "lat": 59.3293, "lng": 18.0686, "capital": "斯德哥尔摩"},
    {"country": "挪威", "variants": ["挪威", "Norway"], "lat": 59.9139, "lng": 10.7522, "capital": "奥斯陆"},
    {"country": "丹麦", "variants": ["丹麦", "Denmark"], "lat": 55.6761, "lng": 12.5683, "capital": "哥本哈根"},
    {"country": "芬兰", "variants": ["芬兰", "Finland"], "lat": 60.1699, "lng": 24.9384, "capital": "赫尔辛基"},
    {"country": "冰岛", "variants": ["冰岛", "Iceland"], "lat": 64.1466, "lng": -21.9426, "capital": "雷克雅未克"},
    # ── 西欧 ──
    {"country": "爱尔兰", "variants": ["爱尔兰", "Ireland"], "lat": 53.3498, "lng": -6.2603, "capital": "都柏林"},
    {"country": "荷兰", "variants": ["荷兰", "Netherlands", "Holland"], "lat": 52.3676, "lng": 4.9041, "capital": "阿姆斯特丹"},
    {"country": "比利时", "variants": ["比利时", "Belgium"], "lat": 50.8503, "lng": 4.3517, "capital": "布鲁塞尔"},
    {"country": "卢森堡", "variants": ["卢森堡", "Luxembourg"], "lat": 49.6117, "lng": 6.1300, "capital": "卢森堡市"},
    {"country": "瑞士", "variants": ["瑞士", "Switzerland"], "lat": 46.9480, "lng": 7.4474, "capital": "伯尔尼"},
    {"country": "奥地利", "variants": ["奥地利", "Austria"], "lat": 48.2082, "lng": 16.3738, "capital": "维也纳"},
    # ── 南欧 ──
    {"country": "西班牙", "variants": ["西班牙", "Spain"], "lat": 40.4168, "lng": -3.7038, "capital": "马德里"},
    {"country": "葡萄牙", "variants": ["葡萄牙", "Portugal"], "lat": 38.7223, "lng": -9.1393, "capital": "里斯本"},
    {"country": "意大利", "variants": ["意大利", "Italy"], "lat": 41.9028, "lng": 12.4964, "capital": "罗马"},
    {"country": "希腊", "variants": ["希腊", "Greece"], "lat": 37.9838, "lng": 23.7275, "capital": "雅典"},
    {"country": "马耳他", "variants": ["马耳他", "Malta"], "lat": 35.8997, "lng": 14.5147, "capital": "瓦莱塔"},
    {"country": "塞浦路斯", "variants": ["塞浦路斯", "Cyprus"], "lat": 35.1856, "lng": 33.3823, "capital": "尼科西亚"},
    # ── 中东欧 ──
    {"country": "波兰", "variants": ["波兰", "Poland"], "lat": 52.2297, "lng": 21.0122, "capital": "华沙"},
    {"country": "捷克", "variants": ["捷克", "Czech", "Czech Republic", "Czechia"], "lat": 50.0755, "lng": 14.4378, "capital": "布拉格"},
    {"country": "斯洛伐克", "variants": ["斯洛伐克", "Slovakia"], "lat": 48.1486, "lng": 17.1077, "capital": "布拉迪斯拉发"},
    {"country": "匈牙利", "variants": ["匈牙利", "Hungary"], "lat": 47.4979, "lng": 19.0402, "capital": "布达佩斯"},
    {"country": "罗马尼亚", "variants": ["罗马尼亚", "Romania"], "lat": 44.4268, "lng": 26.1025, "capital": "布加勒斯特"},
    {"country": "保加利亚", "variants": ["保加利亚", "Bulgaria"], "lat": 42.6977, "lng": 23.3219, "capital": "索非亚"},
    # ── 巴尔干 ──
    {"country": "塞尔维亚", "variants": ["塞尔维亚", "Serbia"], "lat": 44.7866, "lng": 20.4489, "capital": "贝尔格莱德"},
    {"country": "克罗地亚", "variants": ["克罗地亚", "Croatia"], "lat": 45.8150, "lng": 15.9819, "capital": "萨格勒布"},
    {"country": "斯洛文尼亚", "variants": ["斯洛文尼亚", "Slovenia"], "lat": 46.0569, "lng": 14.5058, "capital": "卢布尔雅那"},
    {"country": "波黑", "variants": ["波黑", "Bosnia", "Bosnia and Herzegovina"], "lat": 43.8563, "lng": 18.4131, "capital": "萨拉热窝"},
    {"country": "黑山", "variants": ["黑山", "Montenegro"], "lat": 42.4304, "lng": 19.2594, "capital": "波德戈里察"},
    {"country": "科索沃", "variants": ["科索沃", "Kosovo"], "lat": 42.6629, "lng": 21.1655, "capital": "普里什蒂纳"},
    {"country": "北马其顿", "variants": ["北马其顿", "North Macedonia", "Macedonia"], "lat": 41.9973, "lng": 21.4280, "capital": "斯科普里"},
    {"country": "阿尔巴尼亚", "variants": ["阿尔巴尼亚", "Albania"], "lat": 41.3275, "lng": 19.8187, "capital": "地拉那"},
    # ── 北非 ──
    {"country": "埃及", "variants": ["埃及", "Egypt"], "lat": 30.0444, "lng": 31.2357, "capital": "开罗"},
    {"country": "摩洛哥", "variants": ["摩洛哥", "Morocco"], "lat": 34.0209, "lng": -6.8416, "capital": "拉巴特"},
    {"country": "阿尔及利亚", "variants": ["阿尔及利亚", "Algeria"], "lat": 36.7538, "lng": 3.0588, "capital": "阿尔及尔"},
    {"country": "突尼斯", "variants": ["突尼斯", "Tunisia"], "lat": 36.8065, "lng": 10.1815, "capital": "突尼斯市"},
    {"country": "利比亚", "variants": ["利比亚", "Libya"], "lat": 32.8872, "lng": 13.1913, "capital": "的黎波里"},
    {"country": "苏丹", "variants": ["苏丹", "Sudan"], "lat": 15.5007, "lng": 32.5599, "capital": "喀土穆"},
    {"country": "南苏丹", "variants": ["南苏丹", "South Sudan"], "lat": 4.8594, "lng": 31.5713, "capital": "朱巴"},
    # ── 东非 ──
    {"country": "埃塞俄比亚", "variants": ["埃塞俄比亚", "Ethiopia"], "lat": 9.0320, "lng": 38.7469, "capital": "亚的斯亚贝巴"},
    {"country": "索马里", "variants": ["索马里", "Somalia"], "lat": 2.0469, "lng": 45.3182, "capital": "摩加迪沙"},
    {"country": "肯尼亚", "variants": ["肯尼亚", "Kenya"], "lat": -1.2921, "lng": 36.8219, "capital": "内罗毕"},
    {"country": "坦桑尼亚", "variants": ["坦桑尼亚", "Tanzania"], "lat": -6.1630, "lng": 35.7516, "capital": "多多马"},
    {"country": "乌干达", "variants": ["乌干达", "Uganda"], "lat": 0.3476, "lng": 32.5825, "capital": "坎帕拉"},
    {"country": "卢旺达", "variants": ["卢旺达", "Rwanda"], "lat": -1.9441, "lng": 30.0619, "capital": "基加利"},
    {"country": "厄立特里亚", "variants": ["厄立特里亚", "Eritrea"], "lat": 15.3229, "lng": 38.9251, "capital": "阿斯马拉"},
    {"country": "马达加斯加", "variants": ["马达加斯加", "Madagascar"], "lat": -18.8792, "lng": 47.5079, "capital": "塔那那利佛"},
    {"country": "毛里求斯", "variants": ["毛里求斯", "Mauritius"], "lat": -20.1609, "lng": 57.5012, "capital": "路易港"},
    # ── 西非 ──
    {"country": "尼日利亚", "variants": ["尼日利亚", "Nigeria"], "lat": 9.0765, "lng": 7.3986, "capital": "阿布贾"},
    {"country": "加纳", "variants": ["加纳", "Ghana"], "lat": 5.6037, "lng": -0.1870, "capital": "阿克拉"},
    {"country": "塞内加尔", "variants": ["塞内加尔", "Senegal"], "lat": 14.7167, "lng": -17.4677, "capital": "达喀尔"},
    {"country": "科特迪瓦", "variants": ["科特迪瓦", "Cote d'Ivoire", "Ivory Coast"], "lat": 6.8276, "lng": -5.2893, "capital": "亚穆苏克罗"},
    {"country": "喀麦隆", "variants": ["喀麦隆", "Cameroon"], "lat": 3.8480, "lng": 11.5021, "capital": "雅温得"},
    {"country": "塞拉利昂", "variants": ["塞拉利昂", "Sierra Leone"], "lat": 8.4844, "lng": -13.2344, "capital": "弗里敦"},
    {"country": "利比里亚", "variants": ["利比里亚", "Liberia"], "lat": 6.3004, "lng": -10.7960, "capital": "蒙罗维亚"},
    {"country": "马里", "variants": ["马里", "Mali"], "lat": 12.6392, "lng": -8.0029, "capital": "巴马科"},
    {"country": "布基纳法索", "variants": ["布基纳法索", "Burkina Faso"], "lat": 12.3714, "lng": -1.5197, "capital": "瓦加杜古"},
    {"country": "尼日尔", "variants": ["尼日尔", "Niger"], "lat": 13.5127, "lng": 2.1126, "capital": "尼亚美"},
    {"country": "几内亚", "variants": ["几内亚", "Guinea"], "lat": 9.6412, "lng": -13.5784, "capital": "科纳克里"},
    {"country": "毛里塔尼亚", "variants": ["毛里塔尼亚", "Mauritania"], "lat": 18.0735, "lng": -15.9582, "capital": "努瓦克肖特"},
    # ── 中非 ──
    {"country": "刚果", "variants": ["刚果金", "刚果民主共和国", "DRC", "Democratic Republic of the Congo"], "lat": -4.4419, "lng": 15.2663, "capital": "金沙萨"},
    {"country": "刚果布", "variants": ["刚果布", "刚果共和国", "Republic of the Congo", "Congo-Brazzaville"], "lat": -4.2634, "lng": 15.2429, "capital": "布拉柴维尔"},
    {"country": "乍得", "variants": ["乍得", "Chad"], "lat": 12.1128, "lng": 15.0493, "capital": "恩贾梅纳"},
    {"country": "中非", "variants": ["中非", "Central African Republic", "CAR"], "lat": 4.3947, "lng": 18.5582, "capital": "班吉"},
    {"country": "加蓬", "variants": ["加蓬", "Gabon"], "lat": 0.4162, "lng": 9.4673, "capital": "利伯维尔"},
    # ── 南部非洲 ──
    {"country": "南非", "variants": ["南非", "South Africa"], "lat": -25.7449, "lng": 28.1877, "capital": "比勒陀利亚"},
    {"country": "安哥拉", "variants": ["安哥拉", "Angola"], "lat": -8.8390, "lng": 13.2894, "capital": "罗安达"},
    {"country": "津巴布韦", "variants": ["津巴布韦", "Zimbabwe"], "lat": -17.8252, "lng": 31.0335, "capital": "哈拉雷"},
    {"country": "赞比亚", "variants": ["赞比亚", "Zambia"], "lat": -15.3875, "lng": 28.3228, "capital": "卢萨卡"},
    {"country": "博茨瓦纳", "variants": ["博茨瓦纳", "Botswana"], "lat": -24.6282, "lng": 25.9231, "capital": "哈博罗内"},
    {"country": "纳米比亚", "variants": ["纳米比亚", "Namibia"], "lat": -22.5609, "lng": 17.0658, "capital": "温得和克"},
    {"country": "莫桑比克", "variants": ["莫桑比克", "Mozambique"], "lat": -25.9692, "lng": 32.5732, "capital": "马普托"},
    {"country": "马拉维", "variants": ["马拉维", "Malawi"], "lat": -13.9626, "lng": 33.7741, "capital": "利隆圭"},
    # ── 拉丁美洲 (扩展) ──
    {"country": "墨西哥", "variants": ["墨西哥", "Mexico"], "lat": 19.4326, "lng": -99.1332, "capital": "墨西哥城"},
    {"country": "阿根廷", "variants": ["阿根廷", "Argentina"], "lat": -34.6037, "lng": -58.3816, "capital": "布宜诺斯艾利斯"},
    {"country": "智利", "variants": ["智利", "Chile"], "lat": -33.4489, "lng": -70.6693, "capital": "圣地亚哥"},
    {"country": "哥伦比亚", "variants": ["哥伦比亚", "Colombia"], "lat": 4.7110, "lng": -74.0721, "capital": "波哥大"},
    {"country": "秘鲁", "variants": ["秘鲁", "Peru"], "lat": -12.0464, "lng": -77.0428, "capital": "利马"},
    {"country": "古巴", "variants": ["古巴", "Cuba"], "lat": 23.1136, "lng": -82.3666, "capital": "哈瓦那"},
    {"country": "委内瑞拉", "variants": ["委内瑞拉", "Venezuela"], "lat": 10.4806, "lng": -66.9036, "capital": "加拉加斯"},
    {"country": "厄瓜多尔", "variants": ["厄瓜多尔", "Ecuador"], "lat": -0.1807, "lng": -78.4678, "capital": "基多"},
    {"country": "玻利维亚", "variants": ["玻利维亚", "Bolivia"], "lat": -16.5000, "lng": -68.1500, "capital": "拉巴斯"},
    {"country": "乌拉圭", "variants": ["乌拉圭", "Uruguay"], "lat": -34.9011, "lng": -56.1645, "capital": "蒙得维的亚"},
    {"country": "巴拉圭", "variants": ["巴拉圭", "Paraguay"], "lat": -25.2637, "lng": -57.5759, "capital": "亚松森"},
    # ── 中美洲 ──
    {"country": "巴拿马", "variants": ["巴拿马", "Panama"], "lat": 8.9824, "lng": -79.5199, "capital": "巴拿马城"},
    {"country": "哥斯达黎加", "variants": ["哥斯达黎加", "Costa Rica"], "lat": 9.9281, "lng": -84.0907, "capital": "圣何塞"},
    {"country": "洪都拉斯", "variants": ["洪都拉斯", "Honduras"], "lat": 14.0723, "lng": -87.1921, "capital": "特古西加尔巴"},
    {"country": "萨尔瓦多", "variants": ["萨尔瓦多", "El Salvador"], "lat": 13.6929, "lng": -89.2182, "capital": "圣萨尔瓦多"},
    {"country": "危地马拉", "variants": ["危地马拉", "Guatemala"], "lat": 14.6349, "lng": -90.5069, "capital": "危地马拉城"},
    {"country": "尼加拉瓜", "variants": ["尼加拉瓜", "Nicaragua"], "lat": 12.1140, "lng": -86.2362, "capital": "马那瓜"},
    # ── 加勒比 ──
    {"country": "多米尼加", "variants": ["多米尼加", "Dominican Republic"], "lat": 18.4861, "lng": -69.9312, "capital": "圣多明各"},
    {"country": "海地", "variants": ["海地", "Haiti"], "lat": 18.5944, "lng": -72.3074, "capital": "太子港"},
    {"country": "牙买加", "variants": ["牙买加", "Jamaica"], "lat": 17.9712, "lng": -76.7939, "capital": "金斯敦"},
    {"country": "巴哈马", "variants": ["巴哈马", "Bahamas"], "lat": 25.0343, "lng": -77.3963, "capital": "拿骚"},
    {"country": "特立尼达和多巴哥", "variants": ["特立尼达和多巴哥", "Trinidad and Tobago"], "lat": 10.6549, "lng": -61.5019, "capital": "西班牙港"},
    # ── 大洋洲 ──
    {"country": "新西兰", "variants": ["新西兰", "New Zealand"], "lat": -41.2865, "lng": 174.7762, "capital": "惠灵顿"},
    {"country": "斐济", "variants": ["斐济", "Fiji"], "lat": -18.1416, "lng": 178.4419, "capital": "苏瓦"},
    {"country": "巴布亚新几内亚", "variants": ["巴布亚新几内亚", "Papua New Guinea", "PNG"], "lat": -9.4438, "lng": 147.1803, "capital": "莫尔兹比港"},
    # ── 北极/其他 ──
    {"country": "格陵兰", "variants": ["格陵兰", "Greenland"], "lat": 64.1814, "lng": -51.6941, "capital": "努克"},
    # ── 微型国家/城邦 ──
    {"country": "梵蒂冈", "variants": ["梵蒂冈", "Vatican", "Vatican City", "Holy See", "教廷", "圣座"], "lat": 41.9029, "lng": 12.4534, "capital": "梵蒂冈城"},
    {"country": "摩纳哥", "variants": ["摩纳哥", "Monaco"], "lat": 43.7384, "lng": 7.4246, "capital": "摩纳哥"},
    {"country": "圣马力诺", "variants": ["圣马力诺", "San Marino"], "lat": 43.9424, "lng": 12.4578, "capital": "圣马力诺"},
    {"country": "列支敦士登", "variants": ["列支敦士登", "Liechtenstein"], "lat": 47.1410, "lng": 9.5215, "capital": "瓦杜兹"},
    {"country": "安道尔", "variants": ["安道尔", "Andorra"], "lat": 42.5063, "lng": 1.5218, "capital": "安道尔城"},
    # ── 印度洋/非洲小国 ──
    {"country": "塞舌尔", "variants": ["塞舌尔", "Seychelles"], "lat": -4.6191, "lng": 55.4513, "capital": "维多利亚"},
    {"country": "科摩罗", "variants": ["科摩罗", "Comoros"], "lat": -11.7172, "lng": 43.2473, "capital": "莫罗尼"},
    {"country": "圣多美和普林西比", "variants": ["圣多美和普林西比", "Sao Tome and Principe", "Sao Tome", "圣多美"], "lat": 0.3360, "lng": 6.7270, "capital": "圣多美"},
    {"country": "佛得角", "variants": ["佛得角", "Cape Verde", "Cabo Verde"], "lat": 14.9170, "lng": -23.5090, "capital": "普拉亚"},
    {"country": "吉布提", "variants": ["吉布提", "Djibouti"], "lat": 11.5806, "lng": 43.1480, "capital": "吉布提市"},
    {"country": "莱索托", "variants": ["莱索托", "Lesotho"], "lat": -29.3150, "lng": 27.4876, "capital": "马塞卢"},
    {"country": "斯威士兰", "variants": ["斯威士兰", "Eswatini", "Swaziland"], "lat": -26.3200, "lng": 31.1349, "capital": "姆巴巴内"},
    {"country": "布隆迪", "variants": ["布隆迪", "Burundi"], "lat": -3.3731, "lng": 29.9189, "capital": "布琼布拉"},
    {"country": "赤道几内亚", "variants": ["赤道几内亚", "Equatorial Guinea"], "lat": 3.7523, "lng": 8.7741, "capital": "马拉博"},
    {"country": "几内亚比绍", "variants": ["几内亚比绍", "Guinea-Bissau", "Guinea Bissau"], "lat": 11.8636, "lng": -15.5846, "capital": "比绍"},
    {"country": "冈比亚", "variants": ["冈比亚", "Gambia", "The Gambia"], "lat": 13.4531, "lng": -16.5775, "capital": "班珠尔"},
    {"country": "多哥", "variants": ["多哥", "Togo"], "lat": 6.1304, "lng": 1.2233, "capital": "洛美"},
    {"country": "贝宁", "variants": ["贝宁", "Benin"], "lat": 6.3703, "lng": 2.3912, "capital": "波多诺伏"},
    # ── 加勒比/中美洲小国 ──
    {"country": "伯利兹", "variants": ["伯利兹", "Belize"], "lat": 17.2510, "lng": -88.7590, "capital": "贝尔莫潘"},
    {"country": "苏里南", "variants": ["苏里南", "Suriname"], "lat": 5.8520, "lng": -55.2038, "capital": "帕拉马里博"},
    {"country": "圭亚那", "variants": ["圭亚那", "Guyana"], "lat": 6.8013, "lng": -58.1551, "capital": "乔治敦"},
    {"country": "巴巴多斯", "variants": ["巴巴多斯", "Barbados"], "lat": 13.0979, "lng": -59.6161, "capital": "布里奇敦"},
    {"country": "圣卢西亚", "variants": ["圣卢西亚", "Saint Lucia", "St Lucia", "St. Lucia"], "lat": 13.9957, "lng": -60.9952, "capital": "卡斯特里"},
    {"country": "格林纳达", "variants": ["格林纳达", "Grenada"], "lat": 12.0561, "lng": -61.7487, "capital": "圣乔治"},
    {"country": "圣文森特和格林纳丁斯", "variants": ["圣文森特和格林纳丁斯", "Saint Vincent and the Grenadines", "St Vincent", "St. Vincent"], "lat": 13.1597, "lng": -61.2254, "capital": "金斯敦"},
    {"country": "多米尼克", "variants": ["多米尼克", "Dominica"], "lat": 15.3010, "lng": -61.3870, "capital": "罗索"},
    {"country": "安提瓜和巴布达", "variants": ["安提瓜和巴布达", "Antigua and Barbuda", "Antigua", "安提瓜"], "lat": 17.1175, "lng": -61.8456, "capital": "圣约翰"},
    {"country": "圣基茨和尼维斯", "variants": ["圣基茨和尼维斯", "Saint Kitts and Nevis", "St Kitts", "St. Kitts"], "lat": 17.2957, "lng": -62.7270, "capital": "巴斯特尔"},
    # ── 太平洋岛国 ──
    {"country": "帕劳", "variants": ["帕劳", "Palau"], "lat": 7.5000, "lng": 134.6167, "capital": "梅莱凯奥克"},
    {"country": "马绍尔群岛", "variants": ["马绍尔群岛", "Marshall Islands"], "lat": 7.1315, "lng": 171.1840, "capital": "马朱罗"},
    {"country": "密克罗尼西亚", "variants": ["密克罗尼西亚", "Micronesia", "Federated States of Micronesia", "FSM"], "lat": 6.9167, "lng": 158.1500, "capital": "帕利基尔"},
    {"country": "基里巴斯", "variants": ["基里巴斯", "Kiribati"], "lat": 1.4518, "lng": 172.9724, "capital": "塔拉瓦"},
    {"country": "瑙鲁", "variants": ["瑙鲁", "Nauru"], "lat": -0.5477, "lng": 166.9209, "capital": "亚伦"},
    {"country": "图瓦卢", "variants": ["图瓦卢", "Tuvalu"], "lat": -8.5199, "lng": 179.1980, "capital": "富纳富提"},
    {"country": "萨摩亚", "variants": ["萨摩亚", "Samoa"], "lat": -13.8333, "lng": -171.7500, "capital": "阿皮亚"},
    {"country": "汤加", "variants": ["汤加", "Tonga"], "lat": -21.1343, "lng": -175.2083, "capital": "努库阿洛法"},
    {"country": "瓦努阿图", "variants": ["瓦努阿图", "Vanuatu"], "lat": -17.7333, "lng": 168.3167, "capital": "维拉港"},
    {"country": "所罗门群岛", "variants": ["所罗门群岛", "Solomon Islands"], "lat": -9.4333, "lng": 159.9500, "capital": "霍尼亚拉"},
    {"country": "南极", "variants": ["南极", "Antarctica", "South Pole", "南极洲"], "lat": -82.8628, "lng": 135.0000},
    {"country": "北极", "variants": ["北极", "Arctic", "North Pole"], "lat": 78.0000, "lng": 15.0000},
    {"country": "全球", "variants": ["全球", "Global", "World", "International", "Worldwide", "国际"], "lat": 20.0000, "lng": 0.0000},
]

_COUNTRY_VARIANT_MAP: list[tuple[str, dict]] = []
for c in _COUNTRIES:
    for v in c["variants"]:
        _COUNTRY_VARIANT_MAP.append((v.lower(), c))

# Province/state → major city mapping for granularity
_PROVINCE_CITY: dict[str, dict] = {
    # ── 中国省份 ──
    "河北": {"city": "石家庄", "lat": 38.0423, "lng": 114.5143},
    "河北省": {"city": "石家庄", "lat": 38.0423, "lng": 114.5143},
    "山西": {"city": "太原", "lat": 37.8706, "lng": 112.5489},
    "山西省": {"city": "太原", "lat": 37.8706, "lng": 112.5489},
    "内蒙古": {"city": "呼和浩特", "lat": 40.8414, "lng": 111.7519},
    "内蒙古自治区": {"city": "呼和浩特", "lat": 40.8414, "lng": 111.7519},
    "辽宁": {"city": "沈阳", "lat": 41.8045, "lng": 123.4315},
    "辽宁省": {"city": "沈阳", "lat": 41.8045, "lng": 123.4315},
    "吉林": {"city": "长春", "lat": 43.8868, "lng": 125.3245},
    "吉林省": {"city": "长春", "lat": 43.8868, "lng": 125.3245},
    "黑龙江": {"city": "哈尔滨", "lat": 45.8038, "lng": 126.5350},
    "黑龙江省": {"city": "哈尔滨", "lat": 45.8038, "lng": 126.5350},
    "江苏": {"city": "南京", "lat": 32.0603, "lng": 118.7969},
    "江苏省": {"city": "南京", "lat": 32.0603, "lng": 118.7969},
    "浙江": {"city": "杭州", "lat": 30.2741, "lng": 120.1551},
    "浙江省": {"city": "杭州", "lat": 30.2741, "lng": 120.1551},
    "安徽": {"city": "合肥", "lat": 31.8206, "lng": 117.2272},
    "安徽省": {"city": "合肥", "lat": 31.8206, "lng": 117.2272},
    "福建": {"city": "福州", "lat": 26.0745, "lng": 119.2965},
    "福建省": {"city": "福州", "lat": 26.0745, "lng": 119.2965},
    "江西": {"city": "南昌", "lat": 28.6765, "lng": 115.9101},
    "江西省": {"city": "南昌", "lat": 28.6765, "lng": 115.9101},
    "山东": {"city": "济南", "lat": 36.6512, "lng": 117.1201},
    "山东省": {"city": "济南", "lat": 36.6512, "lng": 117.1201},
    "河南": {"city": "郑州", "lat": 34.7466, "lng": 113.6254},
    "河南省": {"city": "郑州", "lat": 34.7466, "lng": 113.6254},
    "湖北": {"city": "武汉", "lat": 30.5928, "lng": 114.3055},
    "湖北省": {"city": "武汉", "lat": 30.5928, "lng": 114.3055},
    "湖南": {"city": "长沙", "lat": 28.2282, "lng": 112.9388},
    "湖南省": {"city": "长沙", "lat": 28.2282, "lng": 112.9388},
    "广东": {"city": "广州", "lat": 23.1291, "lng": 113.2644},
    "广东省": {"city": "广州", "lat": 23.1291, "lng": 113.2644},
    "广西": {"city": "南宁", "lat": 22.8154, "lng": 108.3275},
    "广西壮族自治区": {"city": "南宁", "lat": 22.8154, "lng": 108.3275},
    "海南": {"city": "海口", "lat": 20.0442, "lng": 110.1999},
    "海南省": {"city": "海口", "lat": 20.0442, "lng": 110.1999},
    "四川": {"city": "成都", "lat": 30.5728, "lng": 104.0668},
    "四川省": {"city": "成都", "lat": 30.5728, "lng": 104.0668},
    "贵州": {"city": "贵阳", "lat": 26.6470, "lng": 106.6302},
    "贵州省": {"city": "贵阳", "lat": 26.6470, "lng": 106.6302},
    "云南": {"city": "昆明", "lat": 25.0296, "lng": 102.7103},
    "云南省": {"city": "昆明", "lat": 25.0296, "lng": 102.7103},
    "西藏": {"city": "拉萨", "lat": 29.6517, "lng": 91.1727},
    "西藏自治区": {"city": "拉萨", "lat": 29.6517, "lng": 91.1727},
    "陕西": {"city": "西安", "lat": 34.3416, "lng": 108.9398},
    "陕西省": {"city": "西安", "lat": 34.3416, "lng": 108.9398},
    "甘肃": {"city": "兰州", "lat": 36.0617, "lng": 103.8343},
    "甘肃省": {"city": "兰州", "lat": 36.0617, "lng": 103.8343},
    "青海": {"city": "西宁", "lat": 36.6171, "lng": 101.7782},
    "青海省": {"city": "西宁", "lat": 36.6171, "lng": 101.7782},
    "宁夏": {"city": "银川", "lat": 38.4874, "lng": 106.2301},
    "宁夏回族自治区": {"city": "银川", "lat": 38.4874, "lng": 106.2301},
    "新疆": {"city": "乌鲁木齐", "lat": 43.8256, "lng": 87.6168},
    "新疆维吾尔自治区": {"city": "乌鲁木齐", "lat": 43.8256, "lng": 87.6168},
    "台湾": {"city": "台北", "lat": 25.0330, "lng": 121.5654},
    "台湾省": {"city": "台北", "lat": 25.0330, "lng": 121.5654},
    # ── 美国 ──
    "怀俄明": {"city": "夏延", "lat": 41.1400, "lng": -104.8202},
    "加利福尼亚": {"city": "洛杉矶", "lat": 34.0522, "lng": -118.2437},
    "德克萨斯": {"city": "奥斯汀", "lat": 30.2672, "lng": -97.7431},
    "佛罗里达": {"city": "迈阿密", "lat": 25.7617, "lng": -80.1918},
    "纽约州": {"city": "纽约", "lat": 40.7128, "lng": -74.0060},
    "马萨诸塞": {"city": "波士顿", "lat": 42.3601, "lng": -71.0589},
    "伊利诺伊": {"city": "芝加哥", "lat": 41.8781, "lng": -87.6298},
    "华盛顿州": {"city": "西雅图", "lat": 47.6062, "lng": -122.3321},
    "科罗拉多": {"city": "丹佛", "lat": 39.7392, "lng": -104.9903},
    "亚利桑那": {"city": "凤凰城", "lat": 33.4484, "lng": -112.0740},
    "宾夕法尼亚": {"city": "费城", "lat": 39.9526, "lng": -75.1652},
    "佐治亚": {"city": "亚特兰大", "lat": 33.7490, "lng": -84.3880},
    "密歇根": {"city": "底特律", "lat": 42.3314, "lng": -83.0458},
    "内华达": {"city": "拉斯维加斯", "lat": 36.1699, "lng": -115.1398},
    "俄亥俄": {"city": "哥伦布", "lat": 39.9612, "lng": -82.9988},
    "北卡罗来纳": {"city": "夏洛特", "lat": 35.2271, "lng": -80.8431},
    "田纳西": {"city": "纳什维尔", "lat": 36.1627, "lng": -86.7816},
    "路易斯安那": {"city": "新奥尔良", "lat": 29.9511, "lng": -90.0715},
    "俄勒冈": {"city": "波特兰", "lat": 45.5152, "lng": -122.6784},
    # ── 澳大利亚 ──
    "新南威尔士": {"city": "悉尼", "lat": -33.8688, "lng": 151.2093},
    "昆士兰": {"city": "布里斯班", "lat": -27.4698, "lng": 153.0251},
    "维多利亚州": {"city": "墨尔本", "lat": -37.8136, "lng": 144.9631},
    # ── 德国 ──
    "巴伐利亚": {"city": "慕尼黑", "lat": 48.1351, "lng": 11.5820},
    "黑森": {"city": "法兰克福", "lat": 50.1109, "lng": 8.6821},
    "北威": {"city": "科隆", "lat": 50.9375, "lng": 6.9603},
    "勃兰登堡": {"city": "柏林", "lat": 52.5200, "lng": 13.4050},
    # ── 西班牙 ──
    "安达卢西亚": {"city": "塞维利亚", "lat": 37.3891, "lng": -5.9845},
    "加泰罗尼亚": {"city": "巴塞罗那", "lat": 41.3874, "lng": 2.1686},
    # ── 印度 ──
    "马哈拉施特拉": {"city": "孟买", "lat": 19.0760, "lng": 72.8777},
    "卡纳塔克": {"city": "班加罗尔", "lat": 12.9716, "lng": 77.5946},
    "泰米尔纳德": {"city": "金奈", "lat": 13.0827, "lng": 80.2707},
    "北方邦": {"city": "勒克瑙", "lat": 26.8467, "lng": 80.9462},
    "安得拉": {"city": "海得拉巴", "lat": 17.3850, "lng": 78.4867},
}


# Context words that indicate an entity mention (company/organization/product)
# rather than a geographic location. When found near a location match,
# the location match is skipped.
_COMPANY_CONTEXT_CN = [
    "公司", "集团", "企业", "有限公司", "股票", "股价", "市值",
    "电商", "云计算", "云服务", "数据中心", "AWS", "Prime",
    "创始人", "CEO", "CTO", "财报", "营收", "净利", "上市",
    "购物", "会员", "平台", "应用商店", "App Store", "流媒体",
]
_COMPANY_CONTEXT_EN = [
    "inc.", "corp.", "corporation", "llc", "ltd.", "nasdaq",
    "e-commerce", "retailer", "online shopping", "prime video",
    "kindle", "echo dot", "fire tv", "aws", "bezos", "jeff bezos",
    "earnings", "revenue", "quarterly", "stock", "shares", "ipo",
    "subsidiary", "headquarters", "hq",
]

_CONTEXT_WINDOW = 60  # chars before/after match position


def _is_company_context(text: str, match_pos: int, variant: str) -> bool:
    """Check if a location match appears in a company/entity context.

    Examines a text window around the match position for company-related words.
    Returns True if the match is likely a false-positive (company mention, not location).
    """
    start = max(0, match_pos - _CONTEXT_WINDOW)
    end = min(len(text), match_pos + len(variant) + _CONTEXT_WINDOW)
    window = text[start:end]
    window_lower = window.lower()

    for word in _COMPANY_CONTEXT_CN:
        if word in window:
            return True
    for word in _COMPANY_CONTEXT_EN:
        if word in window_lower:
            return True
    return False


def get_stored_location(doc: Any) -> Optional[tuple[str, str, float, float]]:
    """Read LLM-extracted location from document horizon_metadata.

    Returns (country, city, lat, lng) or None if no stored location.
    """
    ext = getattr(doc, "extensions", {}) or {}
    if not isinstance(ext, dict):
        return None
    meta = ext.get("horizon_metadata", {})
    if not isinstance(meta, dict):
        return None
    country = meta.get("location_country", "")
    if not country:
        return None
    city = meta.get("location_city", "")
    return _geocode(country, city)


def _geocode(country: str, city: str) -> tuple[str, str, float, float]:
    """Look up coordinates for a country/city pair from our database.

    Tries city match first, then country fallback.
    Returns (country, city, lat, lng), using capital coords if only country matches.
    """
    # Normalize
    country = country.strip()
    city = city.strip()
    country_lower = country.lower()
    city_lower = city.lower()

    # Try city match in _CITIES (both by variant and by city name)
    if city:
        for c in _CITIES:
            if c["city"].lower() == city_lower:
                return (c["country"], city, c["lat"], c["lng"])
            for v in c["variants"]:
                if v.lower() == city_lower:
                    return (c["country"], city, c["lat"], c["lng"])

    # Country-level fallback from _COUNTRIES
    for entry in _COUNTRIES:
        for v in entry["variants"]:
            if v.lower() == country_lower:
                city_name = city if city else entry.get("capital", entry["country"])
                return (entry["country"], city_name, entry["lat"], entry["lng"])

    # Country not in our database — return as-is with zero coords
    return (country, city or country, 0.0, 0.0)


def extract_location(text: str) -> Optional[tuple[str, str, float, float]]:
    """
    Extract city-level location from text.

    Strategy (in order):
    1. Check province/state names → map to major city
    2. Check city names (Chinese & English) → precise coordinates
    3. Fall back to country name → country centroid
    4. Return None if nothing found (no dummy fallback)

    Returns (country, city, lat, lng)
    """
    if not text:
        return None

    lower = text.lower()
    results: list[tuple[int, int, str, str, float, float]] = []

    # Priority 1: province/state → city (score=0, fastest match)
    for prov, info in _PROVINCE_CITY.items():
        pos = _variant_pos(lower, prov.lower())
        if pos is not None and not _is_company_context(text, pos, prov):
            results.append((0, pos, prov, info["city"], info["lat"], info["lng"]))

    # Priority 2: city-level match (score=1)
    seen_variants: set[str] = set()
    for variant, city_entry in _VARIANT_MAP:
        if variant in seen_variants:
            continue
        pos = _variant_pos(lower, variant)
        if pos is not None:
            seen_variants.add(variant)
            if not _is_company_context(text, pos, variant):
                results.append((1, pos, city_entry["country"], city_entry["city"], city_entry["lat"], city_entry["lng"]))

    # Priority 3: country-level fallback (score=2)
    seen_countries: set[str] = set()
    for variant, country_entry in _COUNTRY_VARIANT_MAP:
        if variant in seen_countries:
            continue
        pos = _variant_pos(lower, variant)
        if pos is not None:
            seen_countries.add(variant)
            if not _is_company_context(text, pos, variant):
                city_name = country_entry.get("capital", country_entry["country"])
                results.append((2, pos, country_entry["country"], city_name, country_entry["lat"], country_entry["lng"]))

    if not results:
        return None

    # Sort by priority (0=fastest), then by position in text
    results.sort(key=lambda x: (x[0], x[1]))
    _, _, country, city, lat, lng = results[0]
    return (country, city, lat, lng)


def extract_location_with_fallback(text: str, source_system: str = "", doc: Any = None) -> tuple[str, str, float, float]:
    """Extract location with fallback chain. Always returns a location.

    Fallback priority:
    1. Stored LLM location from document horizon_metadata (if doc provided)
    2. Text-based extraction (with entity disambiguation)
    3. Source metadata lookup via osint_sources catalog
    4. Neutral global fallback

    Returns (country, city, lat, lng)
    """
    # Priority 1: LLM-extracted location stored in document
    if doc is not None:
        stored = get_stored_location(doc)
        if stored is not None:
            return stored
    # Priority 2: text-based keyword extraction
    result = extract_location(text)
    if result is not None:
        return result
    # Priority 3: source metadata lookup
    if source_system:
        from backend.osint_sources import lookup_source_country
        src_loc = lookup_source_country(source_system)
        if src_loc is not None:
            return src_loc
    # Priority 4: global fallback
    return ("全球", "未识别", 20.0, 0.0)
