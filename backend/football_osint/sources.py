from __future__ import annotations

from dataclasses import dataclass
from string import Template


DEFAULT_MATCH_LEVEL = 2


@dataclass(frozen=True)
class FootballSourceTemplate:
    adapter: str
    label: str
    source_type: str
    url_template: str
    topic: str
    description: str
    requires_match_id: bool = False
    default_enabled: bool = True

    def render_url(self, *, match_level: int = DEFAULT_MATCH_LEVEL, match_id: str = "", comp_id: str = "", flesh: str = "0") -> str:
        template = Template(self.url_template)
        return template.safe_substitute(
            matchLevel=str(match_level),
            matchId=match_id,
            scheid=match_id,
            flesh=flesh,
        )


DONGQIUDI_SOURCE_TEMPLATES = (
    FootballSourceTemplate(
        adapter="dongqiudi_schedule",
        label="懂球帝赛程",
        source_type="fixture",
        url_template="https://api.dongqiudi.com/data/tab/new/soccer",
        topic="fixture.dongqiudi.schedule",
        description="抓取近三日赛程、联赛和比分字段。默认开启。",
    ),
    FootballSourceTemplate(
        adapter="dongqiudi_analysis",
        label="懂球帝赛前分析",
        source_type="fundamental",
        url_template="https://m.dongqiudi.com/matchDetail/${matchId}/analysis",
        topic="fundamental.dongqiudi.analysis",
        description="历史交锋、近期战绩、积分榜、伤停信息。matchId 通过赛程按球队名匹配解析。",
        requires_match_id=True,
    ),
)

SEARCH_SOURCE_TEMPLATES = (
    FootballSourceTemplate(
        adapter="ddg_search",
        label="网页搜索",
        source_type="search",
        url_template="https://www.sogou.com/web?query={query}",
        topic="search.ddg.preview",
        description='搜索赛前分析报道，query 为 "{home} vs {away} preview"。搜狗优先，DDG 兜底。',
    ),
)

REFERENCE_SOURCE_TEMPLATES = (
    FootballSourceTemplate(
        adapter="sofascore_event",
        label="SofaScore 赛事",
        source_type="stats",
        url_template="https://www.sofascore.com/event/{matchId}",
        topic="stats.sofascore.event",
        description="实时统计：射门、控球、角球、阵容。需 SofaScore eventId。",
        requires_match_id=False,
        default_enabled=False,
    ),
    FootballSourceTemplate(
        adapter="fbref_squad",
        label="FBref 进阶数据",
        source_type="stats",
        url_template="https://fbref.com/en/squads/{teamId}/",
        topic="stats.fbref.squad",
        description="进阶数据：xG、射门转化率、传球网络、防守数据。需 teamId。",
        requires_match_id=False,
        default_enabled=False,
    ),
    FootballSourceTemplate(
        adapter="transfermarkt_squad",
        label="Transfermarkt 阵容",
        source_type="squad",
        url_template="https://www.transfermarkt.com/{club}/startseite/verein/{clubId}",
        topic="squad.transfermarkt.value",
        description="阵容身价、伤病、停赛、国家队征调。需 club 名和 clubId。",
        requires_match_id=False,
        default_enabled=False,
    ),
)

# ── RSS feeds (no match ID, background collection) ──

RSS_FEED_TEMPLATES = (
    FootballSourceTemplate(
        adapter="rss_rsshub_football",
        label="RSSHub 足球聚合",
        source_type="news",
        url_template="https://rsshub.app/telegram/channel/football",
        topic="news.rss.rsshub.football",
        description="RSSHub 足球相关频道聚合。可通过 FOOTBALL_OSINT_RSS_URLS 环境变量覆盖。",
    ),
    FootballSourceTemplate(
        adapter="rss_bbc_football",
        label="BBC Sport 足球",
        source_type="news",
        url_template="http://feeds.bbci.co.uk/sport/football/rss.xml",
        topic="news.rss.bbc.football",
        description="BBC Sport 足球新闻聚合。",
    ),
    FootballSourceTemplate(
        adapter="rss_espn_soccer",
        label="ESPN Soccer",
        source_type="news",
        url_template="https://www.espn.com/espn/rss/soccer/news",
        topic="news.rss.espn.soccer",
        description="ESPN 足球新闻聚合。",
    ),
    FootballSourceTemplate(
        adapter="rss_skysports_football",
        label="Sky Sports 足球",
        source_type="news",
        url_template="https://www.skysports.com/rss/12040",
        topic="news.rss.skysports.football",
        description="Sky Sports 足球新闻聚合。",
    ),
)


# Allow operator override via env
import os as _os
_custom = _os.getenv("FOOTBALL_OSINT_RSS_URLS", "")
if _custom.strip():
    _extra = []
    for _i, _u in enumerate(_custom.strip().split(",")):
        _u = _u.strip()
        if _u:
            _extra.append(
                FootballSourceTemplate(
                    adapter=f"rss_custom_{_i}",
                    label=f"自定义 RSS #{_i+1}",
                    source_type="news",
                    url_template=_u,
                    topic="news.rss.custom",
                    description=f"自定义 RSS 源: {_u}",
                )
            )
    RSS_FEED_TEMPLATES = RSS_FEED_TEMPLATES + tuple(_extra)

# ── Weibo KOL feeds (via local RSSHub) ──
# See FOOTBALL_OSINT_WEIBO_UIDS and FOOTBALL_OSINT_RSSHUB_BASE env vars for configuration.
_RSSHUB_BASE = _os.getenv("FOOTBALL_OSINT_RSSHUB_BASE", "http://127.0.0.1:1200")
_weibo_uids_raw = _os.getenv("FOOTBALL_OSINT_WEIBO_UIDS", "")
if _weibo_uids_raw.strip():
    _weibo_pairs = []
    for _item in _weibo_uids_raw.strip().split(","):
        _item = _item.strip()
        if ":" in _item:
            _label, _uid = _item.split(":", 1)
            _weibo_pairs.append((_label.strip(), _uid.strip()))
        elif _item:
            _weibo_pairs.append((f"UID:{_item}", _item))
else:
    # Default football KOL accounts (UID verified via public weibo.com/u/ URLs).
    _weibo_pairs = [
        ("微博足球", "3082733222"),          # 微博赛事足球官方账号
        ("体坛周报", "5350271203"),          # 国内最权威体育媒体之一
        ("足球报", "1716376363"),            # 足球专业媒体
        ("董路", "1189615035"),              # 足球评论员、解说
        ("黄健翔", "1362607654"),            # 资深足球解说
        ("新浪体育", "1638781994"),          # 新浪体育官方
        ("足球周刊", "1913412967"),          # 足球杂志官方账号
    ]

_weibo_templates: list[FootballSourceTemplate] = []
for _label, _uid in _weibo_pairs:
    _weibo_templates.append(
        FootballSourceTemplate(
            adapter=f"rss_weibo_{_uid}",
            label=f"微博 {_label}",
            source_type="news",
            url_template=f"{_RSSHUB_BASE}/weibo/user/{_uid}",
            topic="news.rss.weibo.kol",
            description=f"微博足球大V「{_label}」动态，通过 RSSHub。需 WEIBO_COOKIES 配置。",
        )
    )

RSS_FEED_TEMPLATES = RSS_FEED_TEMPLATES + tuple(_weibo_templates)

# ── Chinese sports media via RSSHub ──
# Routes confirmed against RSSHub master (2026-06).
# These complement the en-only BBC/ESPN/Sky feeds with Chinese-language coverage.
_CN_SPORTS_RSS_TEMPLATES = (
    FootballSourceTemplate(
        adapter="rss_hupu_soccer",
        label="虎扑足球",
        source_type="news",
        url_template=f"{_RSSHUB_BASE}/hupu/soccer",
        topic="news.rss.hupu.soccer",
        description="虎扑足球新闻聚合，覆盖五大联赛+中超。通过 RSSHub。",
    ),
    FootballSourceTemplate(
        adapter="rss_dongqiudi_daily",
        label="懂球帝早报",
        source_type="news",
        url_template=f"{_RSSHUB_BASE}/dongqiudi/daily",
        topic="news.rss.dongqiudi.daily",
        description="懂球帝每日早报，聚合当日足球资讯。",
    ),
    FootballSourceTemplate(
        adapter="rss_dongqiudi_intl",
        label="懂球帝国际足球",
        source_type="news",
        url_template=f"{_RSSHUB_BASE}/dongqiudi/top_news/120",
        topic="news.rss.dongqiudi.international",
        description="懂球帝国际足球新闻（含英超/西甲/意甲/德甲）。",
    ),
    FootballSourceTemplate(
        adapter="rss_dongqiudi_special",
        label="懂球帝新闻大爆炸",
        source_type="news",
        url_template=f"{_RSSHUB_BASE}/dongqiudi/special/41",
        topic="news.rss.dongqiudi.special",
        description="懂球帝新闻大爆炸专题，深度足球分析与趣闻。",
    ),
)

RSS_FEED_TEMPLATES = RSS_FEED_TEMPLATES + _CN_SPORTS_RSS_TEMPLATES
