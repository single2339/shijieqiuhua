"""Keyword-based intelligence layer classifier (fallback).

Used when LLM classifier is unavailable. Scores text against 12 keyword groups.
"""

from __future__ import annotations

from backend.models import IntelLayer

_LAYER_RULES: list[tuple[IntelLayer, list[str]]] = [
    (IntelLayer.NATURE, [
        "climate", "weather", "flood", "drought", "earthquake", "wildfire",
        "hurricane", "typhoon", "tsunami", "volcano", "storm", "temperature",
        "emission", "carbon", "renewable energy climate", "natural disaster",
        "forest", "ocean", "arctic", "glacier", "biodiversity", "pollution",
        "air quality", "water quality", "deforestation", "desertification",
        "climate change", "greenhouse", "sea level", "coral bleaching",
        "landslide", "avalanche", "heatwave", "cold wave",
        # Chinese
        "气候", "天气", "干旱", "洪水", "地震", "野火", "森林火灾",
        "飓风", "台风", "海啸", "火山", "风暴", "温度", "排放",
        "碳", "太阳能", "风能", "森林", "海洋",
        "北极", "冰川", "生物多样性", "污染", "酸雨",
        "热浪", "气旋", "温室", "冰盖", "珊瑚", "生态系统",
        "环保", "环境", "海洋酸化", "白化", "空气污染",
        "水质", "森林砍伐", "荒漠化", "气候变化",
    ]),
    (IntelLayer.ECONOMY, [
        "company", "corporation", "merger", "acquisition", "startup", "ipo",
        "factory", "manufacturing", "supply chain", "logistics", "shipping",
        "retail", "inventory", "production", "output", "industry", "business",
        "enterprise", "freight", "warehouse", "cargo", "container", "port",
        "transportation", "delivery", "fleet", "rail", "trucking", "distribution",
        "semiconductor manufacturing", "chip fabrication", "ev production",
        "steel production", "cement production", "industrial output",
        # Chinese
        "公司", "企业", "收购", "初创", "上市", "供应链",
        "工厂", "制造", "物流", "零售", "生产", "产业", "商业",
        "制造商", "供应商", "创业", "货运", "集装箱", "仓库",
        "运输", "航运", "海运", "陆运", "铁路", "配送", "快递",
        "运费", "运力", "船公司", "分拣", "产能", "电动汽车",
        "芯片制造", "半导体产业", "工业产出", "制造业",
    ]),
    (IntelLayer.FINANCE, [
        "price", "currency", "exchange rate", "inflation", "gdp", "interest rate",
        "stock", "bond", "treasury", "central bank", "monetary policy",
        "fiscal", "deficit", "debt", "recession", "growth", "economy", "economic",
        "investment", "capital", "fund", "asset", "commodity price",
        "gold price", "oil price", "copper price", "lithium price",
        "crypto", "bitcoin", "equity", "yield", "liquidity",
        "forex", "usd", "cny", "euro", "rate cut", "rate hike", "stock market",
        # Chinese
        "价格", "货币", "汇率", "通胀", "通货膨胀", "GDP", "利率",
        "股票", "债券", "央行", "中央银行", "货币政策", "财政",
        "赤字", "债务", "衰退", "经济增长", "经济", "投资",
        "资本", "基金", "资产", "大宗商品", "油价", "原油",
        "黄金", "比特币", "加密货币", "收益率", "流动性",
        "外汇", "美元", "欧元", "英镑", "日元",
        "降息", "加息", "联邦储备", "美联储", "基准利率",
        "股市", "金融", "期货", "股指", "纳斯达克",
    ]),
    (IntelLayer.POLITICS, [
        "election", "vote", "policy", "law", "regulation", "legislation",
        "democracy", "government", "president", "congress", "parliament",
        "diplomatic", "diplomacy", "treaty", "alliance",
        "trade war", "tariff policy", "customs regulation", "sanctions policy",
        "trade agreement", "fta", "free trade", "wto",
        "united nations", "nato", "eu commission", "g20", "g7", "brics",
        "foreign ministry", "state visit", "summit",
        # Chinese
        "选举", "投票", "政策", "法律", "法规", "立法",
        "民主", "政府", "总统", "议会", "国会",
        "外交", "条约", "联盟", "国际关系",
        "贸易战", "关税政策", "制裁", "贸易协定",
        "自由贸易", "联合国", "北约", "欧盟", "G20",
        "外交部", "国事访问", "峰会", "谈判",
        "政治", "治理", "执政", "地缘政治",
    ]),
    (IntelLayer.MILITARY, [
        "military", "defense", "army", "navy", "air force", "weapon",
        "missile", "nuclear", "warship", "fighter jet", "combat drone",
        "artillery", "tank", "ammunition", "intelligence military",
        "pentagon", "deployment", "military exercise", "ceasefire",
        "ballistic missile", "hypersonic", "warhead", "air defense",
        # Chinese
        "军事", "国防", "军队", "海军", "空军", "陆军", "武器",
        "导弹", "核弹头", "军舰", "战斗机", "军用无人机",
        "火炮", "坦克", "弹药", "军火", "军备", "防御",
        "五角大楼", "北约", "国防部", "军事演习", "部署",
        "弹道导弹", "高超音速", "核武器", "防空系统",
        "作战", "司令部", "军售", "军费", "战时", "停火",
    ]),
    (IntelLayer.AVIATION, [
        "aviation", "airline", "aircraft", "airport", "flight",
        "airplane", "helicopter", "runway", "boeing", "airbus",
        "comac", "c919", "narrow-body", "wide-body", "air route",
        "aviation safety", "aviation manufacturing", "air travel",
        # Chinese
        "航空", "客机", "飞机", "机场", "航班", "飞行",
        "航空公司", "波音", "空客", "商飞", "C919",
        "窄体", "宽体", "航程", "航线", "航空发动机",
        "民航", "试飞", "航空安全", "机票",
    ]),
    (IntelLayer.TECHNOLOGY, [
        "artificial intelligence", "machine learning", "deep learning",
        "large language model", "llm", "chatgpt", "gpt-4", "gpt-5",
        "claude", "gemini", "openai", "anthropic", "deepseek",
        "generative ai", "transformer", "diffusion model",
        "ai agent", "agi", "multimodal", "neural network",
        "computer vision", "nlp", "ai chip", "gpu", "nvidia",
        "ai regulation", "ai safety", "alignment",
        "ai for science", "ai4s", "drug discovery ai", "protein folding",
        "alphafold", "materials science ai", "climate modeling ai",
        "space", "satellite", "rocket", "spacecraft", "nasa", "spacex",
        "lunar", "mars mission", "orbital", "space station",
        "semiconductor", "quantum computing", "biotechnology",
        "robotics", "autonomous driving", "self-driving",
        # Chinese
        "人工智能", "机器学习", "深度学习", "大语言模型", "大模型",
        "生成式AI", "生成式人工智能", "AI大模型", "智能体",
        "多模态", "AI芯片", "算力",
        "AI安全", "AI对齐", "AI监管", "AI应用", "AI创业",
        "AIGC", "AI绘画", "AI写作", "AI编程",
        "智能驾驶", "自动驾驶", "具身智能", "人形机器人",
        "AI科学", "科学智能", "药物发现", "蛋白质折叠",
        "分子动力学", "科学计算", "AI制药", "AI医疗",
        "航天", "宇航", "太空", "火箭", "飞船", "卫星",
        "月球", "火星", "轨道", "空间站", "星链",
        "半导体", "芯片", "量子计算", "生物技术",
    ]),
    (IntelLayer.SOCIETY, [
        "protest", "demonstration", "social movement", "strike",
        "education", "school", "university", "student",
        "culture", "sport", "olympic", "world cup",
        "migration", "immigrant", "refugee", "asylum",
        "demographics", "population", "census", "urbanization",
        "public opinion", "poll", "survey", "sentiment",
        "labor rights", "wage", "employment", "unemployment",
        "human rights", "ngo", "civil society",
        # Chinese
        "抗议", "示威", "罢工", "社会运动",
        "教育", "学校", "大学", "学生", "高考",
        "文化", "体育", "奥运", "世界杯",
        "移民", "难民", "庇护", "人口", "城镇化",
        "舆情", "民意", "民意调查",
        "劳动", "工资", "就业", "失业",
        "人权", "非政府组织", "公民社会",
        "宗教", "民族", "性别", "妇女",
    ]),
    (IntelLayer.ENERGY, [
        "oil", "crude oil", "natural gas", "lng", "petroleum",
        "opec", "oil production", "oil refinery", "oil pipeline",
        "gas field", "shale gas", "offshore drilling",
        "renewable energy", "solar power", "wind power", "wind farm",
        "hydropower", "nuclear power", "nuclear reactor",
        "energy security", "energy transition", "energy crisis",
        "critical minerals", "lithium mining", "rare earth",
        "cobalt", "nickel", "copper mine",
        "electricity grid", "power plant", "power generation",
        "coal mining", "coal power", "carbon neutral",
        # Chinese
        "石油", "原油", "天然气", "液化天然气", "LNG",
        "欧佩克", "OPEC", "油田", "炼油", "输油管道",
        "气田", "页岩气", "海上钻井",
        "新能源", "太阳能", "光伏", "风电", "风电场",
        "水电", "核电", "核反应堆",
        "能源安全", "能源转型", "能源危机",
        "关键矿产", "锂矿", "稀土", "钴", "镍",
        "电网", "电站", "发电", "煤炭", "碳中和",
        "储能", "电池", "氢能",
    ]),
    (IntelLayer.AGRICULTURE, [
        "food security", "grain", "wheat", "corn", "rice", "soybean",
        "crop", "harvest", "yield", "farming", "agriculture",
        "fertilizer", "pesticide", "irrigation", "arable land",
        "livestock", "poultry", "pork", "beef", "dairy", "aquaculture",
        "fishery", "fishing", "fish stock",
        "food price", "food safety", "food supply",
        "fao", "usda", "world food",
        # Chinese
        "粮食安全", "粮食", "谷物", "小麦", "玉米", "水稻", "大豆",
        "作物", "收成", "产量", "农业", "种植",
        "化肥", "农药", "灌溉", "耕地",
        "畜牧", "家禽", "猪肉", "牛肉", "乳制品", "水产养殖",
        "渔业", "捕捞", "渔获",
        "食品价格", "食品安全", "食品供应",
        "联合国粮农组织", "农业部",
    ]),
    (IntelLayer.HEALTH, [
        "pandemic", "epidemic", "outbreak", "covid", "coronavirus",
        "vaccine", "vaccination", "immunization",
        "who", "world health organization", "public health",
        "disease", "infection", "virus", "bacteria",
        "healthcare", "hospital", "medical system",
        "drug approval", "fda", "clinical trial", "pharmaceutical",
        "mental health", "chronic disease",
        # Chinese
        "疫情", "流行病", "爆发", "新冠", "冠状病毒",
        "疫苗", "接种", "免疫",
        "世界卫生组织", "公共卫生",
        "疾病", "感染", "病毒", "细菌",
        "医疗", "医院", "卫生系统",
        "药品审批", "临床试验", "制药",
        "心理健康", "慢性病", "传染病",
    ]),
    (IntelLayer.CYBER, [
        "cyber attack", "cyber security", "cyber warfare",
        "data breach", "data leak", "hack", "hacker", "ransomware",
        "malware", "phishing", "ddos", "zero-day",
        "digital sovereignty", "information warfare", "disinformation",
        "internet governance", "data privacy", "gdpr",
        "critical infrastructure cyber", "cyber espionage",
        # Chinese
        "网络攻击", "网络安全", "网络战",
        "数据泄露", "数据泄漏", "黑客", "勒索软件",
        "恶意软件", "钓鱼", "拒绝服务",
        "数字主权", "信息战", "虚假信息",
        "互联网治理", "数据隐私", "个人信息保护",
        "关键基础设施", "网络间谍", "APT攻击",
    ]),
]


def classify(text: str) -> IntelLayer:
    lower = text.lower()
    scores: dict[IntelLayer, int] = {layer: 0 for layer in IntelLayer}
    for layer, keywords in _LAYER_RULES:
        for kw in keywords:
            if kw.lower() in lower:
                scores[layer] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else IntelLayer.UNCLASSIFIED
