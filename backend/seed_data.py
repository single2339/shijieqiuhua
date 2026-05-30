#!/usr/bin/env python3
"""Generate comprehensive OSINT test data from 90+ mainstream sources across 16 categories."""
import json, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

from backend.osint_sources import SOURCES, CATEGORIES

STORAGE = Path(__file__).resolve().parent.parent / "bronze_storage"


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


# ── Topic templates — all in Chinese ──
TOPICS = [
    # ── 自然 / 环境 ──
    dict(body="澳大利亚农业区正经历严重干旱，新南威尔士州和昆士兰州气温飙升至42°C以上。持续干旱使土壤湿度降至临界水平，威胁冬小麦收成。气候科学家警告，碳排放增加正在加剧极端天气事件的频率。", loc="Australia"),
    dict(body="巴西亚马逊地区的野火比去年增加了35%，卫星图像显示大面积森林砍伐区域。环保机构报告，森林火灾正向大气中释放大量碳。", loc="Brazil"),
    dict(body="西太平洋正形成一个风速超过180公里/小时的超强台风，威胁日本和菲律宾沿海地区。日本气象厅已对冲绳发布紧急预警。", loc="Japan"),
    dict(body="北极气温较季节平均值高出4°C，加速了格陵兰岛和斯瓦尔巴群岛的冰川融化。卫星数据显示，过去一年冰盖损失了3000亿吨质量，凸显了可再生能源转型的紧迫性。", loc="Global"),
    dict(body="美国地质调查局在怀俄明州黄石超级火山口附近检测到超过200次小地震群。虽然没有即将喷发的威胁，但地震活动已将监测级别提升至最高水平。", loc="United States"),
    dict(body="威尼斯正经历50多年来最严重的洪水，acqua alta水位高达187厘米。圣马可大教堂已被洪水淹没。专家将极端洪水事件频率增加与气候变化和海平面上升联系起来。", loc="EU"),
    dict(body="德国记录了140年来最炎热的夏季，多个州气温超过40°C。热浪对森林生态系统造成严重破坏，并引发了对高峰需求期间可再生能源电网稳定性的担忧。", loc="Germany"),
    dict(body="气旋弗雷迪重创了莫桑比克和马拉维的沿海社区，影响超过50万人。气候研究人员将这场风暴异常的持久性和强度与印度洋海洋温度升高联系起来。", loc="South Africa"),
    dict(body="中国在COP峰会前宣布了新的碳排放目标，承诺在2025年前实现碳达峰，2060年前实现碳中和。该计划包括对西部省份太阳能和风能基础设施的大规模投资。", loc="China"),
    dict(body="太平洋海洋酸化水平已达到临界阈值，威胁大堡礁和南太平洋群岛的珊瑚礁生物多样性。海洋生物学家报告了大规模珊瑚白化事件。", loc="Australia"),
    dict(body="国际能源署报告称，全球可再生能源容量在过去一年增长了50%，主要来自中国的太阳能装置、欧洲的风电场和非洲的水电项目。然而，化石燃料排放仍在上升。", loc="Global"),

    # ── 商业 / 贸易 ──
    dict(body="中国电动汽车制造商比亚迪在匈牙利开设了一座新超级工厂，这是该公司在中国以外最大的制造设施。该工厂将年产20万辆汽车供欧洲市场，创造6000个就业岗位。", loc="EU"),
    dict(body="印度正成为全球半导体供应链的主要参与者，政府批准了150亿美元的新芯片制造厂项目。塔塔集团和富士康等公司正在投资建设生产设施。", loc="India"),
    dict(body="沙特阿拉伯宣布开放NEOM第一期工程，这是一个耗资5000亿美元的红海沿岸跨境巨型项目。该项目是王国2030愿景计划的核心，旨在实现经济多元化。", loc="Saudi Arabia"),
    dict(body="特斯拉以20亿欧元收购了一家德国机器人初创公司，这是该公司在欧洲最大的一笔收购。该交易增强了特斯拉在柏林超级工厂的供应链能力和工厂自动化技术。", loc="Germany"),
    dict(body="尼日利亚科技创业生态系统筹集了创纪录的40亿美元风险投资，巩固了拉各斯作为非洲领先创新中心的地位。金融科技公司占总投资的60%。", loc="Nigeria"),
    dict(body="美国对价值180亿美元的中国制成品征收新关税，目标是半导体元件和电动汽车电池。中国商务部已誓言采取反制措施。", loc="United States"),
    dict(body="韩国三星电子报告季度利润创纪录，受AI芯片需求和存储半导体出口推动。该公司的代工业务正满负荷运转，订单来自全球科技公司。", loc="South Korea"),
    dict(body="越南已成为消费电子产品的关键制造中心，苹果供应商正在胡志明市附近扩建生产设施。该国出口部门同比增长15%。", loc="China"),
    dict(body="欧盟对中国钢铁进口发起反倾销调查，指控国家补贴使中国制造商能够以低于市场价的价格销售。该调查可能导致新关税。", loc="EU"),
    dict(body="墨西哥已超越中国成为美国最大贸易伙伴，受近岸外包趋势和USMCA贸易协定利益推动。跨境物流和制造业产出大幅增长。", loc="Mexico"),
    dict(body="日本制造业产出连续第三个月收缩，因全球对汽车和工业机械的需求减弱。丰田宣布削减国内工厂产量。", loc="Japan"),

    # ── 金融 / 经济 ──
    dict(body="美联储将基准利率维持在4.5%，表明在通胀持续的情况下采取谨慎的货币政策立场。美联储主席鲍威尔表示，在通胀趋势向2%靠拢之前不太可能降息。", loc="United States"),
    dict(body="欧元区通胀率降至2.1%，为三年来最低，增强了欧洲央行暂停加息周期的预期。欧洲债券收益率全面下跌。", loc="EU"),
    dict(body="黄金价格突破每盎司2800美元，创历史新高，投资者纷纷涌入避险资产。此轮上涨由地缘政治紧张局势和央行黄金购买推动。", loc="Global"),
    dict(body="日元兑美元汇率跌至155，为32年来最弱水平。日本央行面临干预外汇市场的压力，扩大的利率差对日元构成压力。", loc="Japan"),
    dict(body="英国政府债券收益率飙升至4.8%，投资者担忧英国不断增长的财政赤字。英镑兑美元下跌1.5%。", loc="United Kingdom"),
    dict(body="沙特阿拉伯以三年来最大幅度下调了面向亚洲买家的原油官方售价，表明需求疲软。布伦特原油期货已跌破每桶75美元。", loc="Saudi Arabia"),
    dict(body="比特币已突破80,000美元，随着多项现货ETF产品获批，机构采用加速推进。加密货币市值已达3.2万亿美元。", loc="Global"),
    dict(body="国际货币基金组织将全球经济增长预测下调至2.8%，理由是持续的通胀、地缘政治紧张局势以及中国经济复苏慢于预期。发展中经济体面临资本外流压力。", loc="Global"),
    dict(body="俄罗斯央行将关键利率提高至18%以对抗通胀，卢布兑主要货币持续走弱。经济制裁继续影响贸易和投资。", loc="Russia"),
    dict(body="印度股市创历史新高，Nifty 50指数首次突破25,000点。强劲的经济增长和企业盈利推动外资投资组合流入激增。", loc="India"),
    dict(body="经合组织报告称，全球债务水平已达到GDP的330%，新兴市场因利息支付上升和美元汇率贬值面临特殊压力。", loc="Global"),

    # ── 人文 / 政治 / 地缘 ──
    dict(body="印度开始了历史上规模最大的民主选举，近9.7亿登记选民。选举分七个阶段进行，为期六周，覆盖全部28个邦和8个联邦属地。", loc="India"),
    dict(body="联合国对加沙日益恶化的人道主义危机发出警告，已有超过150万人流离失所。国际援助机构呼吁立即停火以确保人道主义准入。", loc="Palestine"),
    dict(body="法国通过了全面的养老金改革法案，将退休年龄从62岁提高到64岁，引发全国大规模抗议。超过120万人走上巴黎街头。", loc="France"),
    dict(body="南非正与破坏公共卫生努力的广泛疫苗错误信息作斗争。疫苗接种率已降至55%，远低于80%的群体免疫阈值。", loc="South Africa"),
    dict(body="联合国难民署报告，自冲突爆发以来已有超过800万乌克兰人在国外流离失所。波兰和德国收容的难民数量最多。移民政策是欧洲选举的核心议题。", loc="Ukraine"),
    dict(body="墨西哥最高法院将娱乐用大麻合法化。该裁决遵循了人权组织和公共卫生专家多年的倡导。", loc="Mexico"),
    dict(body="埃及发起了一项新的外交倡议，旨在斡旋以色列与真主党之间的停火。拟议的条约包括双方撤军和国际监督机制。", loc="Egypt"),
    dict(body="伊朗全国各地爆发反政府抗议活动，此前里亚尔崩溃和基本商品普遍短缺。政府已向主要城市部署安全部队。", loc="Iran"),
    dict(body="加拿大宣布每年新增50万永久居民的新移民目标，理由是劳动力短缺和人口老龄化。该政策引发了关于住房可负担性和基础设施能力的辩论。", loc="Canada"),
    dict(body="世界卫生组织宣布结束猴痘全球卫生紧急状态，但警告该病毒仍在流行地区传播，必须持续开展疫苗接种工作。", loc="Global"),
    dict(body="缅甸军政府将紧急状态延长六个月，推迟选举。少数民族武装团体在边境地区取得领土进展，使和平谈判复杂化。", loc="China"),
    dict(body="欧盟就移民政策改革达成里程碑式协议，为成员国设立了强制性难民配额，并加快了被拒绝庇护者的遣返程序。", loc="EU"),
    dict(body="巴西总统公布了一项新的亚马逊保护计划，结合了原住民领土保护与可持续发展倡议。该计划旨在三年内将森林砍伐减少50%。", loc="Brazil"),
    dict(body="土耳其和希腊恢复了关于东地中海海洋边界的探索性会谈，为长期争端的外交解决带来了希望。北约对此表示欢迎。", loc="Turkey"),

    # ── 科技 / 网络安全 ──
    dict(body="一次重大勒索软件攻击已扰乱欧洲关键基础设施，目标针对能源电网和医疗系统。网络安全专家将此次攻击归因于国家支持的黑客组织。", loc="EU"),
    dict(body="OpenAI发布了GPT-5，声称在推理能力和多模态理解方面取得重大进展。该模型在复杂的数学和科学任务上表现出更好的性能。", loc="United States"),
    dict(body="据日本宇宙航空研究开发机构和韩国军方官员报告，朝鲜发射了另一颗间谍卫星。联合国安理会谴责此次发射违反制裁。", loc="South Korea"),
    dict(body="华为发布了其最新AI芯片，声称尽管面临美国出口限制，但性能可与英伟达的旗舰处理器媲美。该芯片采用中国晶圆厂的先进封装技术制造。", loc="China"),
    dict(body="Bellingcat的调查追踪到乌克兰冲突中使用的俄罗斯军事装备源自朝鲜军火运输，揭示了一个复杂的中介网络和伪造的运输文件。", loc="Global"),

    # ── 军事 / 国防 ──
    dict(body="北约宣布在东欧增派快速反应部队，部署包括坦克、装甲车和防空系统在内的重型装备。此次部署是冷战以来北约最大规模的兵力调整，旨在加强东部边境的防御能力。", loc="EU"),
    dict(body="五角大楼公布了2026财年国防预算提案，总额达8950亿美元，重点投资高超音速武器、人工智能指挥系统和太空军事能力。", loc="United States"),
    dict(body="印度成功试射了射程超过5000公里的烈火-6洲际弹道导弹，标志着印度成为具备洲际打击能力的国家。该导弹可携带多枚分导式核弹头。", loc="India"),
    dict(body="以色列国防军展示了新型激光防御系统'铁束'的实战能力，成功拦截了多枚火箭弹和迫击炮弹。该系统成本仅为'铁穹'拦截弹的十分之一。", loc="Israel"),
    dict(body="日本正式成立'统合作战司令部'，整合陆海空自卫队的指挥体系。此举被视为应对地区安全挑战的重要举措，也是日美军事合作深化的体现。", loc="Japan"),
    dict(body="瑞典斯德哥尔摩国际和平研究所报告显示，全球军火贸易额连续第三年增长，美国稳居最大武器出口国，印度为最大武器进口国。", loc="Global"),

    # ── 航空 / 航天 ──
    dict(body="中国商飞C919客机获得欧洲航空安全局的型号认证审查，标志着国产大飞机进入国际市场迈出关键一步。目前C919已累计获得超过1200架订单。", loc="China"),
    dict(body="波音公司宣布新一代中型客机项目正式启动，计划2030年前投入运营。新机型将采用先进的复合材料机翼和新一代高效发动机，燃油效率提升25%。", loc="United States"),
    dict(body="空客A321XLR超远程窄体客机完成首次商业飞行，执飞连接欧洲与北美的跨大西洋航线。该机型航程可达8700公里，开启了点对点远程航线的新时代。", loc="EU"),
    dict(body="NASA与SpaceX合作的阿尔忒弥斯登月计划取得重大进展，星舰飞船成功完成无人绕月飞行测试。人类自1972年以来首次重返月球的计划正在推进中。", loc="United States"),
    dict(body="全球航空客运量恢复至疫情前水平的108%，国际航空运输协会预计全年客运量将达到52亿人次。亚太地区增长最为强劲。", loc="Global"),

    # ── 物流 / 供应链 ──
    dict(body="红海航道危机持续冲击全球供应链，集装箱运费较去年同期上涨300%。马士基等航运巨头被迫绕行好望角，导致运输时间延长10至14天。", loc="Global"),
    dict(body="巴拿马运河管理局宣布新的通行费调整方案，以应对持续干旱导致的水位下降问题。新规定鼓励船运公司减少订舱量以缓解运河拥堵。", loc="Global"),
    dict(body="中国中欧班列年开行量突破2万列，连接欧洲25个国家的200多个城市。中欧陆路运输通道成为海运和空运之外的重要替代方案。", loc="China"),
    dict(body="亚马逊宣布在全球范围内建设无人机配送中心网络，计划实现30分钟内包裹送达。联邦快递和UPS也在加速推进自动化分拣和无人配送技术。", loc="United States"),
    dict(body="全球最大集装箱航运公司地中海航运收购德国博洛莱物流公司，交易金额达30亿欧元。行业整合趋势加速，前十大船公司控制全球85%以上运力。", loc="EU"),

    # ── 进出口 / 国际贸易 ──
    dict(body="世界贸易组织发布全球贸易展望报告，预计2026年全球商品贸易量增长3.5%。亚洲发展中经济体将继续引领贸易增长，但地缘政治风险仍是主要下行因素。", loc="Global"),
    dict(body="美国与欧盟就钢铝关税争端达成新的贸易安排，欧盟同意加强对中国钢铁转口的监管，美方则恢复部分欧盟钢铝产品的免税配额。", loc="EU"),
    dict(body="区域全面经济伙伴关系协定实施三年来，成员国间贸易额增长超过12%。该协定覆盖全球30%的人口和GDP，成为最大的自由贸易区。", loc="China"),
    dict(body="非洲大陆自由贸易区正式启动泛非支付结算系统，旨在促进非洲内部贸易使用本币结算。目前已有42个成员国批准该协定。", loc="South Africa"),
    dict(body="全球半导体贸易格局加速重组，美国和盟友推动芯片供应链多元化。英特尔在德国、日本、马来西亚的新晶圆厂项目获得各国政府补贴支持。", loc="Global"),

    # ── 社交网络KOL分析评论 ──
    dict(body="通过卫星图像和开源情报分析，俄罗斯在乌克兰北部边境集结了新的装甲集群，包括T-90M主战坦克和2S19自行火炮。基辅方面表示前线分析显示俄军可能在春季发动新一轮攻势。", loc="Ukraine"),
    dict(body="对最新商业卫星图像的分析显示，朝鲜宁边核设施出现新活动迹象——平壤轻水反应堆附近的热信号增强，可能正在进行燃料再处理。首尔方面确认这与IAEA此前的报告相吻合。", loc="South Korea"),
    dict(body="综合多个开源情报来源，解放军福建舰的第四次海试可能推迟至夏季。上海造船厂的卫星图像显示舰岛安装了新的雷达系统，电磁弹射器的调试仍在进行中。", loc="China"),
    dict(body="根据俄罗斯军事博主的最新分析，俄军正在哈尔科夫方向部署新的电子战系统。这些R-330Zh居民系统能够压制GPS信号和无人机通信。开源情报社区已通过频谱分析确认。", loc="Ukraine"),
    dict(body="深入分析中东地区近期冲突趋势：亲伊朗民兵组织正在使用新型自杀式无人机，其航程和精度较以往型号有显著提升。利雅得方面评估也门胡塞武装据信已获得部分生产技术。", loc="Saudi Arabia"),
    dict(body="从卫星图像和船舶自动识别系统数据分析，红海地区的商业航运量已恢复至危机前水平的60%。但开罗的苏伊士运河通行量仍比去年同期低35%，绕行好望角的航线成本上升明显。", loc="Egypt"),
    dict(body="美国太空部队最新追踪数据：俄罗斯试验的反卫星武器释放了大量空间碎片，对华盛顿的ISS和低轨卫星星座构成威胁。目前的监测显示至少有1500个可追踪碎片在轨道上。", loc="United States"),
    dict(body="开源调查分析：缅甸军政府正通过泰国中转进口武器部件。曼谷的贸易数据分析和航运记录显示相关物资经拉廊港转运至缅甸边境地区。联合国专家已呼吁进行调查。", loc="Thailand"),
    dict(body="综合多方开源情报，叙利亚沙漠地区伊斯兰国潜伏小组的袭击频率在过去三个月增加了40%。开罗方面的情报分析显示其利用地形复杂区域躲避叙利亚和俄罗斯军队的巡逻。", loc="Egypt"),
    dict(body="解放军近期在南海组织了大规模海空联合演习，出动了山东舰航母战斗群和轰-6K轰炸机。广州的开源分析人士通过ADS-B数据和卫星图像追踪了演习的规模和范围。", loc="China"),
]

# ── Assign topics to sources to ensure coverage ──
# Each category gets topics matching its focus
TOPIC_ASSIGNMENT = [
    # News agencies get broad coverage
    (["reuters", "ap-news", "afp", "upi"], 0),  # drought Australia
    (["reuters", "bbc", "upi"], 1),               # Amazon wildfires
    (["kyodo-news", "ap-news", "upi"], 2),         # typhoon Japan
    (["reuters", "guardian", "bbc"], 3),           # Arctic melt
    (["usgs", "ap-news", "upi"], 4),               # Yellowstone
    (["ansa", "euronews", "upi"], 5),              # Venice flood
    (["dpa", "euronews", "upi"], 6),               # Germany heatwave
    (["afp", "bbc", "africa-confidential"], 7),    # Cyclone Mozambique
    (["xinhua", "scmp", "upi"], 8),               # China carbon targets
    (["afp", "guardian", "abc-au"], 9),            # Great Barrier Reef
    (["iea", "carbon-brief", "bbc"], 10),          # IEA renewable report

    # Commerce topics to business/regional sources
    (["reuters", "ft", "bloomberg"], 11),           # BYD Hungary
    (["nikkei-asia", "times-of-india", "bloomberg"], 12),  # India semiconductors
    (["arab-news", "bloomberg", "ft"], 13),                  # NEOM
    (["reuters", "dpa", "ft"], 14),                          # Tesla Germany
    (["techcrunch", "premium-times", "bbc"], 15),             # Nigeria startups
    (["cnbc", "bloomberg", "washington-post"], 16),           # US tariffs China
    (["korea-herald", "nikkei-asia", "reuters"], 17),         # Samsung
    (["nikkei-asia", "scmp", "reuters"], 18),                 # Vietnam manufacturing
    (["politico-eu", "euobserver", "ft"], 19),                # EU steel dumping
    (["el-universal", "reforma", "cnbc"], 20),                # Mexico trade
    (["nikkei-asia", "japan-times", "reuters"], 21),          # Japan manufacturing

    # Finance topics to finance sources
    (["bloomberg", "cnbc", "wsj"], 22),                    # Fed rate
    (["ft", "economist", "bloomberg"], 23),                 # Eurozone inflation
    (["reuters", "marketwatch", "investing-com"], 24),      # Gold price
    (["nikkei-asia", "kyodo-news", "bloomberg"], 25),       # Yen low
    (["ft", "guardian", "economist"], 26),                  # UK bonds
    (["cnbc", "bloomberg", "arab-news"], 27),              # Saudi oil
    (["bloomberg", "cnbc", "investing-com"], 28),           # Bitcoin
    (["imf", "world-bank", "ft"], 29),                      # IMF growth forecast
    (["tass", "bloomberg", "economist"], 30),               # Russia rate hike
    (["times-of-india", "bloomberg", "ft"], 31),            # India stock market
    (["oecd", "economist", "bloomberg"], 32),               # OECD debt report

    # People/politics topics to diverse regional sources
    (["bbc", "times-of-india", "hindu"], 33),               # India election
    (["al-jazeera", "bbc", "un-news"], 34),                  # Gaza crisis
    (["le-monde", "afp", "bbc"], 35),                        # France pension
    (["sabc", "bbc", "all-africa"], 36),                     # SA vaccine
    (["unhcr", "bbc", "guardian"], 37),                      # Ukraine refugees
    (["reforma", "bbc", "washington-post"], 38),             # Mexico cannabis
    (["al-monitor", "middle-east-eye", "bbc"], 39),          # Egypt ceasefire
    (["tehran-times", "bbc", "guardian"], 40),               # Iran protests
    (["globe-mail", "bbc", "reuters"], 41),                  # Canada immigration
    (["who", "bbc", "reuters"], 42),                         # WHO mpox
    (["nk-news", "reuters", "bbc"], 43),                     # Myanmar junta
    (["politico-eu", "euobserver", "bbc"], 44),              # EU migration
    (["globonews", "bbc", "guardian"], 45),                  # Brazil Amazon plan
    (["daily-sabah", "anadolu", "bbc"], 46),                 # Turkey Greece talks

    # Tech/cyber topics to specialized sources
    (["theregister", "darkreading", "bleeping-computer"], 47),   # Ransomware
    (["techcrunch", "wired", "arstechnica"], 48),                # GPT-5
    (["jaxa", "nk-news", "reuters"], 49),                        # NK satellite
    (["scmp", "nikkei-asia", "reuters"], 50),                    # Huawei chip
    (["bellingcat", "recorded-future", "bbc"], 51),              # NK arms to Russia

    # Military topics
    (["nato", "janes", "janes-defense"], 52),                     # NATO deployment
    (["defense-news", "breaking-defense", "csis"], 53),           # Pentagon budget
    (["times-of-india", "iiss", "janes"], 54),                   # India ICBM
    (["janes-defense", "warzone", "breaking-defense"], 55),       # Israel laser
    (["kyodo-news", "japan-times", "janes"], 56),                # Japan command
    (["iiss", "sipri", "csis"], 57),                              # Global arms trade

    # Aviation topics
    (["scmp", "nikkei-asia", "flightglobal"], 58),               # C919 certification
    (["aviation-week", "flightglobal", "reuters"], 59),           # Boeing new jet
    (["flightglobal", "aviation-week", "euronews"], 60),          # A321XLR
    (["techcrunch", "arstechnica", "air-current"], 61),           # Artemis moon
    (["simple-flying", "flightradar24", "air-current"], 62),      # Passenger recovery

    # Logistics topics
    (["reuters", "freightwaves", "the-loadstar"], 63),            # Red Sea crisis
    (["joc", "freightwaves", "cnbc"], 64),                        # Panama Canal
    (["xinhua", "scmp", "joc"], 65),                              # China rail
    (["techcrunch", "supply-chain-dive", "wired"], 66),           # Amazon drone
    (["freightwaves", "the-loadstar", "logistics-mgmt"], 67),     # MSC Bollore

    # Trade topics
    (["wto", "economist", "reuters"], 68),                        # WTO trade outlook
    (["politico-eu", "ft", "bloomberg"], 69),                     # US EU steel
    (["nikkei-asia", "scmp", "reuters"], 70),                    # RCEP trade
    (["all-africa", "wto", "reuters"], 71),                      # Africa free trade
    (["wto", "global-trade", "container-trade"], 72),             # Semiconductor trade

    # KOL source assignments
    (["oryx", "war-mapper", "ralee85"], 73),                      # Russia armor buildup
    (["redspotted-nro", "suriyak-maps", "geoconfirmed"], 74),     # North Korea nuke facility
    (["casual-scholar", "marksian", "guancha-kol"], 75),          # Fujian carrier delay
    (["rybar", "ukraine-frontline", "osinttechnical"], 76),       # Russian EW deployment
    (["middle-east-monitor", "suriyak-maps", "southfront"], 77),  # Iran drone tech
    (["trent-telenko", "southfront", "biggers-geopolitics"], 78), # Red Sea shipping
    (["redspotted-nro", "osinttechnical", "defmon3"], 79),        # Russia ASAT debris
    (["geoconfirmed", "visual-politik", "boston-roundface"], 80), # Myanmar arms smuggling
    (["suriyak-maps", "middle-east-monitor", "covert-cabal"], 81),# ISIS resurgence Syria
    (["casual-scholar", "marksian", "shapan-war"], 82),           # South China Sea drills
]

# Additional specialty topics for niche sources
SPECIALTY_TOPICS = [
    dict(body="北约宣布了自冷战以来欧洲最大规模的军事演习，来自全部31个成员国的9万名士兵参加。此次演习旨在测试东翼的快速部署能力。", src=["nato", "janes"], loc="EU", layer_override="politics"),
    dict(body="斯德哥尔摩国际和平研究所报告称，全球军费支出已达2.4万亿美元，为冷战以来最高水平。受乌克兰冲突和北约承诺推动，欧洲增幅最大。", src=["sipri", "rand", "csis"], loc="Global", layer_override="politics"),
    dict(body="战略与国际研究中心发布了一份关于中国海军扩张的新分析，发现北京目前拥有全球规模最大的海军（按舰艇数量计算）。报告强调了印太安全联盟的影响。", src=["csis", "rand", "chatham-house"], loc="China"),
    dict(body="Carbon Brief的分析显示，全球化石燃料二氧化碳排放在2025年趋于平稳，电力部门引领下降，可再生能源新增装机容量创下纪录。", src=["carbon-brief", "inside-climate", "iea"], loc="Global"),
    dict(body="Mongabay报道，亚马逊原住民管理的森林森林砍伐率比邻近地区低50%，凸显了原住民土地权在生物多样性保护中的关键作用。", src=["mongabay", "climate-home", "inside-climate"], loc="Brazil"),
    dict(body="查塔姆研究所研究人员警告，中东地区水资源短缺可能在未来十年内引发跨境冲突，气候变化正在减少底格里斯-幼发拉底河流域的河流流量。", src=["chatham-house", "carnegie", "wilson-center"], loc="Iran"),
    dict(body="布鲁金斯学会分析发现，AI驱动的自动化可能在未来五年内取代发达经济体高达30%的现有工作岗位，同时创造技术监管和人机协作方面的新角色。", src=["brookings", "rand", "carnegie"], loc="Global"),
    dict(body="人权观察记录了海湾国家移民工人遭受的系统性虐待，呼吁进行劳动法改革并建立独立监督机制。", src=["hrw", "ictj", "al-monitor"], loc="Saudi Arabia"),
    dict(body="Grey Dynamics对乌克兰部署的俄罗斯电子战系统进行分析，发现GPS欺骗和通信干扰的模式严重削弱了乌克兰无人机作战能力。", src=["grey-dynamics", "janes", "warzone"], loc="Ukraine"),
    dict(body="Recorded Future威胁情报报告，针对欧洲能源公司的钓鱼攻击增加了300%，归因于亲俄黑客组织。", src=["recorded-future", "darkreading", "bleeping-computer"], loc="EU"),
    dict(body="CIA世界概况手册更新了对朝鲜弹道导弹能力的评估，估计该国目前拥有50枚以上核弹头和洲际弹道导弹。", src=["cia-factbook", "state-department", "nk-news"], loc="South Korea"),
    dict(body="美国国家海洋和大气管理局的年度气候报告确认，2025年是有记录以来最温暖的一年，全球平均气温比工业化前水平高出1.45°C。", src=["noaa", "usgs", "esa"], loc="Global"),
    dict(body="欧洲航天局哥白尼计划发布的新卫星图像显示，喜马拉雅山脉冰川快速消融，威胁超过20亿人的水资源供应。", src=["esa", "jaxa", "noaa"], loc="China"),
    dict(body="中国外交部谴责美国最新对台军售，警告将产生严重后果。", src=["china-mfa", "xinhua", "scmp"], loc="China"),
    dict(body="红十字国际委员会报告，其团队今年在乌克兰冲突中促成了超过2000名战俘的交换。", src=["icrc", "un-news", "unhcr"], loc="Ukraine"),
    dict(body="世界粮食计划署警告，37个国家的4500万人面临紧急水平的饥饿，其中苏丹、加沙和阿富汗受影响最为严重。", src=["wfp", "un-news", "icrc"], loc="Global"),

    # ── KOL specialty analysis pieces ──
    dict(body="通过开源情报对基辅周边战场装备损失进行详细统计：俄罗斯已确认损失超过3000辆坦克、5000辆装甲车和500套火炮系统。分析显示俄军正在加速启用老旧T-62和T-54坦克补充损失。", src=["oryx", "perun", "covert-cabal"], loc="Ukraine", layer_override="military"),
    dict(body="澳大利亚堪培拉的国防经济学家对全球军费开支的深入分析发现，北约欧洲成员国军费占GDP比例已从2014年的1.4%升至2025年的2.3%。但实际采购效率因通胀和供应链问题下降了约15%。", src=["perun", "ralee85", "iiss"], loc="Global", layer_override="military"),
    dict(body="乌克兰战场开源情报综合分析：俄军正在利用滑翔炸弹对哈尔科夫前线阵地进行持续轰炸。KAB-500和FAB-1500滑翔炸弹的使用量比去年同期增加了300%，对防御工事构成严峻威胁。", src=["ukikaski", "war-mapper", "osinttechnical"], loc="Ukraine", layer_override="military"),
    dict(body="通过华盛顿空间态势感知数据分析，星链卫星在乌克兰战场上的应用显著提升了乌克兰无人机部队的作战效能。低轨卫星星座正从根本上改变现代战场通信和侦察模式。", src=["redspotted-nro", "defmon3", "biggers-geopolitics"], loc="Global"),
    dict(body="综合开源地理空间情报分析，俄罗斯北极地区的军事基地群正在扩建，包括新地岛和法兰士约瑟夫地群岛的设施升级。卫星图像显示跑道延长和新的雷达站建设。", src=["intel-crab", "hi-sutton", "simplicius-thinker"], loc="Russia", layer_override="military"),
    dict(body="开源情报对缅甸内战的最新追踪：少数民族武装联盟已控制中缅边境多个关键贸易口岸。卫星图像和社交媒体视频验证了果敢同盟军控制了老街地区的行政中心。", src=["mt-anderson", "eliot-higgins", "christo-grozev"], loc="China", layer_override="military"),
    dict(body="通过对伊朗核设施附近商业卫星图像的深入分析，纳坦兹铀浓缩厂出现新的地下设施建设活动。Jeffrey Lewis的评估指出这可能是新型IR-9离心机的安装准备。", src=["jeffrey-lewis", "redspotted-nro", "intel-crab"], loc="Iran"),
    dict(body="Phillips O'Brien对乌克兰战争战略层面的深度分析：双方正在进入消耗战的新阶段，工业产能和人员储备成为决定因素。欧洲国防工业基础正在调整生产线以适应长期冲突。", src=["phillips-obrien", "mick-ryan", "michael-kofman"], loc="Ukraine", layer_override="military"),
    dict(body="开源情报调查追踪到朝鲜正通过罗津港向俄罗斯远东地区运输弹药。卫星图像和AIS船舶跟踪数据显示多艘货轮频繁往返于罗津和俄远东港口之间。", src=["tatarigami-ua", "andrew-perpetua", "franz-gady"], loc="South Korea", layer_override="military"),
    dict(body="Alexander Mercouris对俄乌和平谈判进展的分析指出，双方在克里米亚地位和中立国条款上仍存在根本分歧。Brian Berletic补充了亚洲国家在此问题上的立场分析。", src=["alex-mercouris", "brian-berletic", "simplicius-thinker"], loc="Ukraine"),
]


def build_documents(seed: str = "") -> list[dict]:
    docs: list[dict] = []

    def add_doc(body: str, source: str, location_hint: str, layer_override: str | None = None) -> None:
        docs.append(dict(body=body, source=source, loc=location_hint, layer=layer_override))

    import random as _random
    _rng = _random.Random(seed or md5(str(datetime.now(timezone.utc).timestamp())))

    # Shuffle TOPIC_ASSIGNMENT order so different sources win the body-dedup race each cycle
    shuffled_assignments = list(TOPIC_ASSIGNMENT)
    _rng.shuffle(shuffled_assignments)
    for source_names, topic_idx in shuffled_assignments:
        topic = TOPICS[topic_idx]
        srcs = list(source_names)
        _rng.shuffle(srcs)
        for src in srcs:
            add_doc(topic["body"], src, topic["loc"], topic.get("layer"))

    # Specialty topics (shuffle as well)
    shuffled_specialty = list(SPECIALTY_TOPICS)
    _rng.shuffle(shuffled_specialty)
    for topic in shuffled_specialty:
        srcs = list(topic.get("src", []))
        _rng.shuffle(srcs)
        for src in srcs:
            add_doc(topic["body"], src, topic.get("loc", "Global"), topic.get("layer_override"))

    # Assign remaining sources
    assigned_sources = set()
    for source_names, _ in TOPIC_ASSIGNMENT:
        for s in source_names:
            assigned_sources.add(s)
    for topic in SPECIALTY_TOPICS:
        for s in topic.get("src", []):
            assigned_sources.add(s)

    unassigned = [s for s in SOURCES if s.name not in assigned_sources]
    _rng.shuffle(unassigned)

    for source in unassigned:
        candidates = list(TOPICS)
        if source.layer_bias:
            candidates = [t for t in TOPICS if t.get("layer") == source.layer_bias] or TOPICS
        region_topics = [t for t in TOPICS if t["loc"] in (source.country_focus or [])]
        if region_topics:
            topic = region_topics[_rng.randint(0, len(region_topics) - 1)]
        else:
            topic = candidates[_rng.randint(0, len(candidates) - 1)]
        add_doc(topic["body"], source.name, topic["loc"], source.layer_bias)

    return docs


def clear_storage() -> None:
    """Remove all existing bronze storage files and empty directories."""
    if STORAGE.exists():
        import shutil
        shutil.rmtree(STORAGE)
        STORAGE.mkdir(parents=True, exist_ok=True)


def main(clear: bool = False, seed: str = "") -> None:
    if clear:
        clear_storage()
    all_docs = build_documents(seed=seed)
    source_counts: dict[str, int] = {}

    # Dedup by body hash — same body can serve multiple sources
    seen_hashes: set[str] = set()
    docs_out: list[dict] = []

    for doc in all_docs:
        body = doc["body"]
        body_hash = md5(body)
        if body_hash in seen_hashes:
            continue
        seen_hashes.add(body_hash)
        docs_out.append(doc)

    # Now write documents — one per (source, topic) combination
    written = 0
    source_counts = {}

    for idx, doc in enumerate(all_docs):
        body = doc["body"]
        src = doc["source"]
        loc = doc["loc"]

        doc_id = md5(f"{src}:{body}")
        date = (datetime.now(timezone.utc) - timedelta(hours=48 - idx % 48)).isoformat()

        payload = {
            "$schema": "https://osint-network.local/schemas/raw-document.schema.json",
            "raw_document_id": doc_id,
            "job_id": f"seed-job-{idx}",
            "channel": "web",
            "mime_type": "text/html",
            "encoding": "utf-8",
            "body_ref": None,
            "body_inline": body,
            "headers_summary": {"user-agent": "OSINT-Seed-Script/2.0"},
            "captured_at": date,
            "collector_id": "web-collector",
            "collector_version": "2.0",
            "source_url": f"https://{src.replace('_', '-')}.com/{date[:10]}/{loc.lower().replace(' ', '-')}",
            "source_system": src,
            "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "classification": None,
            "extensions": None,
            "tenant_id": None,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        day = date[:10]
        dest_dir = STORAGE / day / src
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{doc_id}.json"
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        written += 1
        source_counts[src] = source_counts.get(src, 0) + 1

    # Show coverage by category
    print(f"Seeded {written} documents across {len(source_counts)} sources.\n")
    cat_counts: dict[str, int] = {}
    for s in SOURCES:
        if s.name in source_counts:
            cat_counts[s.category] = cat_counts.get(s.category, 0) + source_counts[s.name]
    for cat_key, cat_label in CATEGORIES.items():
        cnt = cat_counts.get(cat_key, 0)
        if cnt:
            srcs_in_cat = len([s for s in SOURCES if s.category == cat_key])
            print(f"  {cat_label:40s} {cnt:3d} docs from {srcs_in_cat:2d} sources")
    print(f"\n  {'TOTAL':40s} {written:3d} docs")


if __name__ == "__main__":
    import sys
    main(clear="--clear" in sys.argv)
