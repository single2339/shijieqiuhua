from __future__ import annotations

import re
from typing import Optional, Any

_LATIN_RE = re.compile(r"[a-zA-Z]")


def _variant_pos(text: str, variant: str) -> int | None:
    """Position of variant in text, or None.

    Word-boundary matching for Latin-script variants avoids false
    matches like "Iran" inside "transiranian".  Substring matching
    for CJK variants since \\b doesn't work with Chinese characters.
    """
    if _LATIN_RE.search(variant):
        m = re.search(r"\b" + re.escape(variant) + r"\b", text)
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
    {"country": "欧盟", "variants": ["欧盟", "European Union", "EU", "Europe", "欧洲", "Eurozone"], "lat": 50.8503, "lng": 4.3517, "capital": "布鲁塞尔"},
    {"country": "全球", "variants": ["全球", "Global", "World", "International", "Worldwide", "国际"], "lat": 20.0000, "lng": 0.0000},
]

_COUNTRY_VARIANT_MAP: list[tuple[str, dict]] = []
for c in _COUNTRIES:
    for v in c["variants"]:
        _COUNTRY_VARIANT_MAP.append((v.lower(), c))

# Province/state → major city mapping for granularity
_PROVINCE_CITY: dict[str, dict] = {
    "新南威尔士": {"city": "悉尼", "lat": -33.8688, "lng": 151.2093},
    "昆士兰": {"city": "布里斯班", "lat": -27.4698, "lng": 153.0251},
    "维多利亚州": {"city": "墨尔本", "lat": -37.8136, "lng": 144.9631},
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
    "巴伐利亚": {"city": "慕尼黑", "lat": 48.1351, "lng": 11.5820},
    "黑森": {"city": "法兰克福", "lat": 50.1109, "lng": 8.6821},
    "北威": {"city": "科隆", "lat": 50.9375, "lng": 6.9603},
    "勃兰登堡": {"city": "柏林", "lat": 52.5200, "lng": 13.4050},
    "安达卢西亚": {"city": "塞维利亚", "lat": 37.3891, "lng": -5.9845},
    "加泰罗尼亚": {"city": "巴塞罗那", "lat": 41.3874, "lng": 2.1686},
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
