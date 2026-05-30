"""Comprehensive OSINT source catalog — all mainstream open-source intelligence sources."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SourceConfig:
    name: str
    display_name: str
    category: str
    credibility: float
    region: str
    country_focus: list[str] = field(default_factory=list)
    rss_url: Optional[str] = None
    layer_bias: Optional[str] = None
    notes: str = ""


SOURCES: list[SourceConfig] = [
    # ═══════════════════════════════════════════════
    # 1 — Global News Agencies
    # ═══════════════════════════════════════════════
    SourceConfig("reuters",          "Reuters",              "news_agency",       0.92, "global"),
    SourceConfig("ap-news",          "Associated Press",     "news_agency",       0.91, "global"),
    SourceConfig("afp",              "Agence France-Presse", "news_agency",       0.89, "global"),
    SourceConfig("bloomberg",        "Bloomberg News",       "news_agency",       0.90, "global",  layer_bias="finance"),
    SourceConfig("kyodo-news",       "Kyodo News",           "news_agency",       0.85, "asia",    country_focus=["Japan"]),
    SourceConfig("xinhua",           "Xinhua News Agency",   "news_agency",       0.72, "asia",    country_focus=["China"]),
    SourceConfig("tass",             "TASS",                 "news_agency",       0.68, "eurasia", country_focus=["Russia"]),
    SourceConfig("anadolu",          "Anadolu Agency",       "news_agency",       0.75, "middle_east", country_focus=["Turkey"]),
    SourceConfig("ansa",             "ANSA",                 "news_agency",       0.82, "europe",  country_focus=["Italy"]),
    SourceConfig("dpa",              "Deutsche Presse-Agentur","news_agency",      0.86, "europe",  country_focus=["Germany"]),
    SourceConfig("efe",              "EFE News Agency",      "news_agency",       0.78, "latin_america", country_focus=["Spain"]),
    SourceConfig("upi",              "United Press Intl",    "news_agency",       0.77, "global"),

    # ═══════════════════════════════════════════════
    # 2 — Major International Media
    # ═══════════════════════════════════════════════
    SourceConfig("bbc",              "BBC News",             "international",     0.88, "global"),
    SourceConfig("cnn",              "CNN",                  "international",     0.83, "global"),
    SourceConfig("al-jazeera",       "Al Jazeera",           "international",     0.84, "middle_east"),
    SourceConfig("guardian",         "The Guardian",         "international",     0.87, "global"),
    SourceConfig("nytimes",          "The New York Times",   "international",     0.86, "global"),
    SourceConfig("washington-post",  "The Washington Post",  "international",     0.85, "global"),
    SourceConfig("wsj",              "Wall Street Journal",  "international",     0.88, "global",  layer_bias="finance"),
    SourceConfig("ft",               "Financial Times",      "international",     0.89, "global",  layer_bias="finance"),
    SourceConfig("economist",        "The Economist",        "international",     0.87, "global"),
    SourceConfig("npr",              "NPR",                  "international",     0.82, "global"),

    # ═══════════════════════════════════════════════
    # 3 — Regional Media — Asia Pacific
    # ═══════════════════════════════════════════════
    SourceConfig("scmp",             "South China Morning Post","regional_asia",   0.80, "asia",    country_focus=["China", "Hong Kong"]),
    SourceConfig("nikkei-asia",      "Nikkei Asia",          "regional_asia",     0.83, "asia",    country_focus=["Japan"]),
    SourceConfig("japan-times",      "The Japan Times",      "regional_asia",     0.79, "asia",    country_focus=["Japan"]),
    SourceConfig("times-of-india",   "Times of India",       "regional_asia",     0.76, "asia",    country_focus=["India"]),
    SourceConfig("hindu",            "The Hindu",            "regional_asia",     0.78, "asia",    country_focus=["India"]),
    SourceConfig("korea-herald",     "The Korea Herald",     "regional_asia",     0.73, "asia",    country_focus=["South Korea"]),
    SourceConfig("nk-news",          "NK News",              "regional_asia",     0.80, "asia",    country_focus=["North Korea", "South Korea"]),
    SourceConfig("abc-au",           "ABC Australia",        "regional_asia",     0.84, "oceania", country_focus=["Australia"]),

    # ═══════════════════════════════════════════════
    # 4 — Regional Media — Europe
    # ═══════════════════════════════════════════════
    SourceConfig("le-monde",         "Le Monde",             "regional_europe",   0.84, "europe",  country_focus=["France"]),
    SourceConfig("der-spiegel",      "Der Spiegel",          "regional_europe",   0.83, "europe",  country_focus=["Germany"]),
    SourceConfig("el-pais",          "El País",              "regional_europe",   0.81, "europe",  country_focus=["Spain"]),
    SourceConfig("repubblica",       "La Repubblica",        "regional_europe",   0.79, "europe",  country_focus=["Italy"]),
    SourceConfig("politico-eu",      "Politico Europe",      "regional_europe",   0.82, "europe",  country_focus=["EU"]),
    SourceConfig("euobserver",       "EUobserver",           "regional_europe",   0.80, "europe",  country_focus=["EU"]),
    SourceConfig("euronews",         "Euronews",             "regional_europe",   0.78, "europe"),
    SourceConfig("meduza",           "Meduza",               "regional_europe",   0.74, "eurasia", country_focus=["Russia"]),
    SourceConfig("kiev-independent", "Kyiv Independent",     "regional_europe",   0.82, "europe",  country_focus=["Ukraine"]),

    # ═══════════════════════════════════════════════
    # 5 — Regional Media — Middle East & Africa
    # ═══════════════════════════════════════════════
    SourceConfig("arab-news",        "Arab News",            "regional_me",       0.77, "middle_east", country_focus=["Saudi Arabia"]),
    SourceConfig("middle-east-eye",  "Middle East Eye",      "regional_me",       0.78, "middle_east"),
    SourceConfig("tehran-times",     "Tehran Times",         "regional_me",       0.65, "middle_east", country_focus=["Iran"]),
    SourceConfig("haaretz",          "Haaretz",              "regional_me",       0.79, "middle_east", country_focus=["Israel"]),
    SourceConfig("al-monitor",       "Al-Monitor",           "regional_me",       0.80, "middle_east"),
    SourceConfig("daily-sabah",      "Daily Sabah",          "regional_me",       0.74, "middle_east", country_focus=["Turkey"]),
    SourceConfig("all-africa",       "AllAfrica",            "regional_africa",    0.75, "africa"),
    SourceConfig("africa-confidential","Africa Confidential","regional_africa",   0.79, "africa"),
    SourceConfig("sabc",             "SABC News",            "regional_africa",   0.74, "africa",   country_focus=["South Africa"]),
    SourceConfig("nation-africa",    "Nation Africa",        "regional_africa",   0.73, "africa",   country_focus=["Kenya"]),
    SourceConfig("premium-times",    "Premium Times",        "regional_africa",   0.76, "africa",   country_focus=["Nigeria"]),

    # ═══════════════════════════════════════════════
    # 6 — Regional Media — Americas
    # ═══════════════════════════════════════════════
    SourceConfig("globe-mail",       "The Globe and Mail",   "regional_americas", 0.82, "north_america", country_focus=["Canada"]),
    SourceConfig("globonews",        "GloboNews",            "regional_americas", 0.76, "latin_america", country_focus=["Brazil"]),
    SourceConfig("el-universal",     "El Universal",         "regional_americas", 0.74, "latin_america", country_focus=["Mexico"]),
    SourceConfig("clarin",           "Clarín",               "regional_americas", 0.73, "latin_america", country_focus=["Argentina"]),
    SourceConfig("reforma",          "Reforma",              "regional_americas", 0.76, "latin_america", country_focus=["Mexico"]),

    # ═══════════════════════════════════════════════
    # 7 — Government & Official Sources
    # ═══════════════════════════════════════════════
    SourceConfig("cia-factbook",     "CIA World Factbook",   "government",        0.90, "global"),
    SourceConfig("nato",             "NATO",                 "government",        0.88, "global"),
    SourceConfig("state-department", "US State Dept",        "government",        0.83, "global"),
    SourceConfig("usgs",             "US Geological Survey", "government",        0.91, "global",  layer_bias="nature"),
    SourceConfig("noaa",             "NOAA",                 "government",        0.90, "global",  layer_bias="nature"),
    SourceConfig("esa",              "European Space Agency", "government",       0.88, "europe"),
    SourceConfig("jaxa",             "JAXA",                 "government",        0.86, "asia",    country_focus=["Japan"]),
    SourceConfig("china-mfa",        "China MFA",            "government",        0.65, "asia",    country_focus=["China"]),

    # ═══════════════════════════════════════════════
    # 8 — International Organizations
    # ═══════════════════════════════════════════════
    SourceConfig("un-news",          "UN News",              "intl_org",          0.88, "global"),
    SourceConfig("unhcr",            "UNHCR",                "intl_org",          0.90, "global",  layer_bias="politics"),
    SourceConfig("who",              "World Health Org",     "intl_org",          0.89, "global"),
    SourceConfig("wfp",              "World Food Programme", "intl_org",          0.89, "global"),
    SourceConfig("world-bank",       "World Bank",           "intl_org",          0.86, "global",  layer_bias="finance"),
    SourceConfig("imf",              "IMF",                  "intl_org",          0.87, "global",  layer_bias="finance"),
    SourceConfig("oecd",             "OECD",                 "intl_org",          0.86, "global",  layer_bias="finance"),
    SourceConfig("icrc",             "ICRC",                 "intl_org",          0.90, "global"),

    # ═══════════════════════════════════════════════
    # 9 — Think Tanks & Research
    # ═══════════════════════════════════════════════
    SourceConfig("sipri",            "SIPRI",                "think_tank",        0.88, "global"),
    SourceConfig("chatham-house",    "Chatham House",        "think_tank",        0.86, "global"),
    SourceConfig("csis",             "CSIS",                 "think_tank",        0.84, "global"),
    SourceConfig("rand",             "RAND Corporation",     "think_tank",        0.85, "global"),
    SourceConfig("brookings",        "Brookings Institution","think_tank",        0.84, "global"),
    SourceConfig("wilson-center",    "Wilson Center",        "think_tank",        0.81, "global"),
    SourceConfig("carnegie",         "Carnegie Endowment",   "think_tank",        0.83, "global"),
    SourceConfig("hrw",              "Human Rights Watch",   "think_tank",        0.85, "global",  layer_bias="politics"),
    SourceConfig("ictj",             "ICTJ",                 "think_tank",        0.82, "global"),
    SourceConfig("iea",              "IEA",                  "think_tank",        0.85, "global",  layer_bias="nature"),

    # ═══════════════════════════════════════════════
    # 10 — Finance & Economic Intelligence
    # ═══════════════════════════════════════════════
    SourceConfig("cnbc",             "CNBC",                 "financial",         0.84, "global"),
    SourceConfig("marketwatch",      "MarketWatch",          "financial",         0.82, "global"),
    SourceConfig("investing-com",    "Investing.com",        "financial",         0.79, "global"),
    SourceConfig("zerohedge",        "ZeroHedge",            "financial",         0.65, "global"),
    SourceConfig("fxstreet",         "FXStreet",             "financial",         0.78, "global"),

    # ═══════════════════════════════════════════════
    # 11 — Technology & Cybersecurity
    # ═══════════════════════════════════════════════
    SourceConfig("techcrunch",       "TechCrunch",           "technology",        0.80, "global"),
    SourceConfig("theregister",      "The Register",         "technology",        0.82, "global"),
    SourceConfig("arstechnica",      "Ars Technica",         "technology",        0.83, "global"),
    SourceConfig("wired",            "Wired",                "technology",        0.82, "global"),
    SourceConfig("bleeping-computer","BleepingComputer",     "cybersecurity",     0.81, "global"),
    SourceConfig("recorded-future",  "Recorded Future",      "cybersecurity",     0.85, "global"),
    SourceConfig("darkreading",      "Dark Reading",         "cybersecurity",     0.83, "global"),

    # ═══════════════════════════════════════════════
    # 12 — Specialized OSINT & Investigation
    # ═══════════════════════════════════════════════
    SourceConfig("bellingcat",       "Bellingcat",           "osint",             0.88, "global"),
    SourceConfig("osinttechniques",  "OSINT Techniques",     "osint",             0.82, "global"),
    SourceConfig("grey-dynamics",    "Grey Dynamics",        "osint",             0.80, "global"),
    SourceConfig("inteltechniques",  "IntelTechniques",      "osint",             0.83, "global"),
    SourceConfig("janes",            "Janes",                "defense",           0.87, "global"),
    SourceConfig("warzone",          "The War Zone",         "defense",           0.80, "global"),

    # ═══════════════════════════════════════════════
    # 13 — Energy & Environment Specialists
    # ═══════════════════════════════════════════════
    SourceConfig("carbon-brief",     "Carbon Brief",         "environment",       0.86, "global",  layer_bias="nature"),
    SourceConfig("inside-climate",   "Inside Climate News",  "environment",       0.83, "global",  layer_bias="nature"),
    SourceConfig("climate-home",     "Climate Home News",    "environment",       0.82, "global",  layer_bias="nature"),
    SourceConfig("mongabay",         "Mongabay",             "environment",       0.84, "global",  layer_bias="nature"),

    # ═══════════════════════════════════════════════
    # 14 — Military & Defense
    # ═══════════════════════════════════════════════
    SourceConfig("defense-news",     "Defense News",         "military",          0.86, "global",  layer_bias="military"),
    SourceConfig("breaking-defense", "Breaking Defense",     "military",          0.84, "global",  layer_bias="military"),
    SourceConfig("iiss",             "IISS",                 "military",          0.89, "global",  layer_bias="military"),
    SourceConfig("rusi",             "RUSI",                 "military",          0.86, "europe",  layer_bias="military"),
    SourceConfig("military-com",     "Military.com",         "military",          0.78, "global",  layer_bias="military"),
    SourceConfig("janes-defense",    "Janes Defence Weekly", "military",          0.87, "global",  layer_bias="military"),

    # ═══════════════════════════════════════════════
    # 15 — Aviation & Aerospace
    # ═══════════════════════════════════════════════
    SourceConfig("flightglobal",     "FlightGlobal",         "aviation",          0.85, "global",  layer_bias="aviation"),
    SourceConfig("aviation-week",    "Aviation Week",        "aviation",          0.87, "global",  layer_bias="aviation"),
    SourceConfig("simple-flying",    "Simple Flying",        "aviation",          0.76, "global",  layer_bias="aviation"),
    SourceConfig("flightradar24",    "FlightRadar24 Blog",   "aviation",          0.80, "global",  layer_bias="aviation"),
    SourceConfig("air-current",      "The Air Current",      "aviation",          0.82, "global",  layer_bias="aviation"),

    # ═══════════════════════════════════════════════
    # 16 — Logistics & Supply Chain
    # ═══════════════════════════════════════════════
    SourceConfig("freightwaves",     "FreightWaves",         "logistics",         0.82, "global",  layer_bias="economy"),
    SourceConfig("joc",              "Journal of Commerce",  "logistics",         0.84, "global",  layer_bias="economy"),
    SourceConfig("logistics-mgmt",   "Logistics Management", "logistics",         0.79, "global",  layer_bias="economy"),
    SourceConfig("supply-chain-dive","Supply Chain Dive",    "logistics",         0.81, "global",  layer_bias="economy"),
    SourceConfig("the-loadstar",     "The Loadstar",         "logistics",         0.80, "global",  layer_bias="economy"),

    # ═══════════════════════════════════════════════
    # 17 — Trade & Import/Export Intelligence
    # ═══════════════════════════════════════════════
    SourceConfig("wto",              "WTO",                  "trade",             0.88, "global",  layer_bias="politics"),
    SourceConfig("global-trade",     "Global Trade Magazine", "trade",            0.79, "global",  layer_bias="politics"),
    SourceConfig("trade-finance",    "Trade Finance Global", "trade",              0.81, "global",  layer_bias="politics"),
    SourceConfig("export-gov",       "Export.gov",           "trade",             0.85, "global",  layer_bias="politics"),
    SourceConfig("container-trade",  "Container Trade Stats","trade",             0.83, "global",  layer_bias="politics"),

    # ═══════════════════════════════════════════════
    # 18 — Social Media News KOLs
    # ═══════════════════════════════════════════════
    SourceConfig("oryx",              "Oryx (Jakub Janovsky)",            "social_kol", 0.82, "global",             layer_bias="military", notes="Equipment tracking analyst"),
    SourceConfig("perun",             "Perun",                           "social_kol", 0.80, "global",             layer_bias="military", notes="Defense economics analysis"),
    SourceConfig("redspotted-nro",    "Red Spotted Newt",                "social_kol", 0.78, "global",             notes="Satellite/space tracking"),
    SourceConfig("suriyak-maps",      "Suriyak Maps",                    "social_kol", 0.78, "middle_east",        country_focus=["Syria"], layer_bias="military", notes="Syria/ME conflict mapping"),
    SourceConfig("ralee85",           "Rob Lee",                         "social_kol", 0.78, "eurasia",            country_focus=["Russia", "Ukraine"], layer_bias="military", notes="Russia-Ukraine military analyst"),
    SourceConfig("casual-scholar",    "The Casual Scholar",              "social_kol", 0.78, "global",             country_focus=["China", "US"], notes="China/geopolitical analysis"),
    SourceConfig("geoconfirmed",      "GeoConfirmed",                    "social_kol", 0.76, "global",             layer_bias="military", notes="Geolocation verification collective"),
    SourceConfig("osinttechnical",    "OSINTtechnical",                  "social_kol", 0.76, "global",             notes="OSINT investigations"),
    SourceConfig("southfront",        "SouthFront",                      "social_kol", 0.76, "global",             layer_bias="military", notes="Defense & security analysis"),
    SourceConfig("visual-politik",    "VisualPolitik",                   "social_kol", 0.76, "global",             notes="Geopolitical analysis"),
    SourceConfig("biggers-geopolitics","Biggers Geopolitics",            "social_kol", 0.75, "global",             notes="Geopolitical commentary"),
    SourceConfig("war-mapper",        "War Mapper",                      "social_kol", 0.74, "eurasia",            country_focus=["Russia", "Ukraine"], layer_bias="military", notes="Conflict mapping"),
    SourceConfig("middle-east-monitor","Middle East Monitor",            "social_kol", 0.74, "middle_east",        notes="ME news monitoring"),
    SourceConfig("rybar",             "Rybar",                           "social_kol", 0.74, "eurasia",            country_focus=["Russia", "Ukraine"], layer_bias="military", notes="Russian military analysis Telegram"),
    SourceConfig("ukikaski",          "Uki Kaski",                       "social_kol", 0.74, "eurasia",            country_focus=["Russia", "Ukraine"], layer_bias="military", notes="Finland-based Russia analyst"),
    SourceConfig("defmon3",           "Defense Monitor",                 "social_kol", 0.73, "global",             layer_bias="military", notes="Defense & aerospace monitoring"),
    SourceConfig("ukraine-frontline", "Ukraine Frontline",               "social_kol", 0.73, "eurasia",            country_focus=["Ukraine"], layer_bias="military", notes="Ukraine war tracking"),
    SourceConfig("marksian",          "Markus (SEALIN)",                 "social_kol", 0.72, "asia",               country_focus=["China", "Taiwan", "Japan"], notes="Asia-Pacific security analyst"),
    SourceConfig("covert-cabal",      "Covert Cabal",                    "social_kol", 0.72, "global",             layer_bias="military", notes="Military equipment analysis"),
    SourceConfig("trent-telenko",     "Trent Telenko",                   "social_kol", 0.72, "eurasia",            country_focus=["Russia", "Ukraine"], layer_bias="economy", notes="Military logistics analyst"),
    SourceConfig("boston-roundface",  "Boston Roundface (波士顿圆脸)",    "social_kol", 0.70, "asia",               country_focus=["China"], notes="Chinese international news commentator"),
    SourceConfig("shapan-war",        "沙盘上的战争",                     "social_kol", 0.68, "asia",               country_focus=["China"], layer_bias="military", notes="Chinese military history analyst"),
    SourceConfig("guancha-kol",       "观察者网 KOL",                     "social_kol", 0.66, "asia",               country_focus=["China"], notes="Chinese news commentary KOL"),

    # Additional social media KOLs
    SourceConfig("intel-crab",         "Intel Crab",                      "social_kol", 0.76, "global",             layer_bias="military", notes="OSINT geolocation intelligence"),
    SourceConfig("mt-anderson",        "MT Anderson",                     "social_kol", 0.75, "global",             layer_bias="aviation", notes="Military aviation OSINT analyst"),
    SourceConfig("eliot-higgins",      "Eliot Higgins",                   "social_kol", 0.80, "global",             notes="Bellingcat founder, OSINT pioneer"),
    SourceConfig("christo-grozev",     "Christo Grozev",                  "social_kol", 0.78, "global",             notes="Bellingcat lead investigator"),
    SourceConfig("hi-sutton",          "H I Sutton",                      "social_kol", 0.77, "global",             layer_bias="military", notes="Naval OSINT analysis"),
    SourceConfig("simplicius-thinker", "Simplicius the Thinker",          "social_kol", 0.74, "eurasia",            country_focus=["Russia", "Ukraine"], layer_bias="military", notes="Military analysis Substack"),
    SourceConfig("andrew-perpetua",    "Andrew Perpetua",                 "social_kol", 0.75, "eurasia",            country_focus=["Ukraine"], notes="Ukraine conflict tracking"),
    SourceConfig("tatarigami-ua",      "Tatarigami_UA",                   "social_kol", 0.76, "eurasia",            country_focus=["Ukraine"], layer_bias="military", notes="Ukraine front analysis"),
    SourceConfig("jeffrey-lewis",      "Jeffrey Lewis",                   "social_kol", 0.79, "global",             notes="Arms control/nonproliferation expert (Arms Control Wonk)"),
    SourceConfig("phillips-obrien",    "Phillips O'Brien",                "social_kol", 0.77, "eurasia",            notes="Military/strategic analysis professor"),
    SourceConfig("mick-ryan",          "Mick Ryan",                       "social_kol", 0.76, "global",             notes="Military strategy analyst"),
    SourceConfig("franz-gady",         "Franz-Stefan Gady",               "social_kol", 0.76, "eurasia",            layer_bias="military", notes="Military analyst, Russia-Ukraine"),
    SourceConfig("alex-mercouris",     "Alexander Mercouris",             "social_kol", 0.70, "eurasia",            notes="Geopolitical/legal analyst (The Duran)"),
    SourceConfig("brian-berletic",     "Brian Berletic",                  "social_kol", 0.72, "asia",               country_focus=["China", "Thailand"], notes="Geopolitical commentator (The New Atlas)"),
    SourceConfig("michael-kofman",     "Michael Kofman",                  "social_kol", 0.80, "eurasia",            country_focus=["Russia", "Ukraine"], layer_bias="military", notes="Russia military analyst (Carnegie)"),

    # ═══════════════════════════════════════════════
    # 19 — AI for Science (AI4S)
    # ═══════════════════════════════════════════════
    SourceConfig("aihub-news",        "AIHub News (Science)",     "ai4s",          0.78, "global",  layer_bias="technology",
                 rss_url="https://aihub.org/category/news/feed/",
                 notes="Filter articles with 'science' keyword"),
    SourceConfig("aihub-articles",    "AIHub Articles (Science)", "ai4s",          0.78, "global",  layer_bias="technology",
                 rss_url="https://aihub.org/category/articles/feed/",
                 notes="Filter articles with 'science' keyword"),
    SourceConfig("sciencenews-ai",    "Science News AI",          "ai4s",          0.85, "global",  layer_bias="technology",
                 rss_url="https://www.sciencenews.org/feed",
                 notes="Topic: artificial-intelligence"),
    SourceConfig("google-news-ai4s",  "Google News AI4S",         "ai4s",          0.75, "global",  layer_bias="technology",
                 rss_url="https://news.google.com/rss/search?q=ai%20for%20science&hl=en-US&gl=US&ceid=US:en",
                 notes="Google News RSS for 'ai for science'"),
    SourceConfig("sciencenet-info",   "科学网信息化",              "ai4s",          0.76, "asia",    country_focus=["China"], layer_bias="technology",
                 rss_url="https://news.sciencenet.cn/fieldlist.aspx?id=9",
                 notes="Chinese science informatization news"),

    # ═══════════════════════════════════════════════
    # 20 — AI Hot (AI 热点)
    # ═══════════════════════════════════════════════
    SourceConfig("aihot-daily",       "AI HOT 精选",              "ai_hot",        0.77, "global",  layer_bias="technology",
                 rss_url="https://aihot.virxact.com/rss",
                 notes="Daily curated AI industry news"),

    # ═══════════════════════════════════════════════
    # 21 — China Domestic Social & News (via RSSHub)
    # ═══════════════════════════════════════════════
    SourceConfig("weibo-hot",         "微博热搜",                "social_media_china", 0.72, "asia",
                 country_focus=["China"], layer_bias="politics",
                 rss_url="http://127.0.0.1:1200/weibo/search/hot",
                 notes="Weibo real-time hot search — public opinion and breaking news"),
    SourceConfig("cls-telegraph",     "财联社电报",              "financial_china",    0.78, "asia",
                 country_focus=["China"], layer_bias="finance",
                 rss_url="http://127.0.0.1:1200/cls/telegraph",
                 notes="Cailianpress financial telegraph — real-time market and policy news"),
    SourceConfig("zaobao-china",      "联合早报·中国",           "regional_china",     0.80, "asia",
                 country_focus=["China", "Singapore"], layer_bias="politics",
                 rss_url="http://127.0.0.1:1200/zaobao/realtime/china",
                 notes="Lianhe Zaobao China section — Singapore-based Chinese-language news"),
]

_SOURCE_MAP = {s.name: s for s in SOURCES}

# Region → fallback (country, city, lat, lng) — used when country_focus is empty
_REGION_FALLBACK: dict[str, tuple[str, str, float, float]] = {
    "global":        ("全球", "国际空域", 20.0, 0.0),
    "asia":          ("中国", "北京", 39.9042, 116.4074),
    "europe":        ("欧盟", "布鲁塞尔", 50.8503, 4.3517),
    "middle_east":   ("阿联酋", "迪拜", 25.2048, 55.2708),
    "africa":        ("南非", "约翰内斯堡", -26.2041, 28.0473),
    "latin_america": ("巴西", "巴西利亚", -15.7934, -47.8822),
    "eurasia":       ("俄罗斯", "莫斯科", 55.7558, 37.6173),
    "oceania":       ("澳大利亚", "悉尼", -33.8688, 151.2093),
}

# Country name → (country, city, lat, lng)
_COUNTRY_COORDS: dict[str, tuple[str, str, float, float]] = {
    "中国":       ("中国", "北京", 39.9042, 116.4074),
    "美国":       ("美国", "华盛顿", 38.9072, -77.0369),
    "俄罗斯":     ("俄罗斯", "莫斯科", 55.7558, 37.6173),
    "英国":       ("英国", "伦敦", 51.5074, -0.1278),
    "德国":       ("德国", "柏林", 52.5200, 13.4050),
    "法国":       ("法国", "巴黎", 48.8566, 2.3522),
    "日本":       ("日本", "东京", 35.6762, 139.6503),
    "印度":       ("印度", "新德里", 28.6139, 77.2090),
    "巴西":       ("巴西", "巴西利亚", -15.7934, -47.8822),
    "澳大利亚":   ("澳大利亚", "堪培拉", -35.2809, 149.1300),
    "加拿大":     ("加拿大", "渥太华", 45.4215, -75.6972),
    "韩国":       ("韩国", "首尔", 37.5665, 126.9780),
    "意大利":     ("意大利", "罗马", 41.9028, 12.4964),
    "西班牙":     ("西班牙", "马德里", 40.4168, -3.7038),
    "荷兰":       ("荷兰", "阿姆斯特丹", 52.3676, 4.9041),
    "瑞士":       ("瑞士", "伯尔尼", 46.9480, 7.4474),
    "瑞典":       ("瑞典", "斯德哥尔摩", 59.3293, 18.0686),
    "挪威":       ("挪威", "奥斯陆", 59.9139, 10.7522),
    "丹麦":       ("丹麦", "哥本哈根", 55.6761, 12.5683),
    "芬兰":       ("芬兰", "赫尔辛基", 60.1699, 24.9384),
    "波兰":       ("波兰", "华沙", 52.2297, 21.0122),
    "奥地利":     ("奥地利", "维也纳", 48.2082, 16.3738),
    "新加坡":     ("新加坡", "新加坡", 1.3521, 103.8198),
    "越南":       ("越南", "河内", 21.0278, 105.8342),
    "泰国":       ("泰国", "曼谷", 13.7563, 100.5018),
    "印尼":       ("印尼", "雅加达", -6.2088, 106.8456),
    "菲律宾":     ("菲律宾", "马尼拉", 14.5995, 120.9842),
    "马来西亚":   ("马来西亚", "吉隆坡", 3.1390, 101.6869),
    "沙特阿拉伯": ("沙特阿拉伯", "利雅得", 24.7136, 46.6753),
    "阿联酋":     ("阿联酋", "迪拜", 25.2048, 55.2708),
    "伊朗":       ("伊朗", "德黑兰", 35.6892, 51.3890),
    "以色列":     ("以色列", "特拉维夫", 32.0853, 34.7818),
    "土耳其":     ("土耳其", "安卡拉", 39.9334, 32.8597),
    "南非":       ("南非", "约翰内斯堡", -26.2041, 28.0473),
    "尼日利亚":   ("尼日利亚", "拉各斯", 6.5244, 3.3792),
    "埃及":       ("埃及", "开罗", 30.0444, 31.2357),
    "肯尼亚":     ("肯尼亚", "内罗毕", -1.2921, 36.8219),
    "墨西哥":     ("墨西哥", "墨西哥城", 19.4326, -99.1332),
    "阿根廷":     ("阿根廷", "布宜诺斯艾利斯", -34.6037, -58.3816),
    "智利":       ("智利", "圣地亚哥", -33.4489, -70.6693),
    "新西兰":     ("新西兰", "惠灵顿", -41.2865, 174.7762),
    "台湾":       ("台湾", "台北", 25.0330, 121.5654),
    "香港":       ("香港", "香港", 22.3193, 114.1694),
    "澳门":       ("澳门", "澳门", 22.1987, 113.5439),
    "乌克兰":     ("乌克兰", "基辅", 50.4501, 30.5234),
    "缅甸":       ("缅甸", "仰光", 16.8403, 96.1735),
    "巴基斯坦":   ("巴基斯坦", "伊斯兰堡", 33.6844, 73.0479),
    "孟加拉国":   ("孟加拉国", "达卡", 23.8103, 90.4125),
    "伊拉克":     ("伊拉克", "巴格达", 33.3152, 44.3661),
    "叙利亚":     ("叙利亚", "大马士革", 33.5138, 36.2765),
    "阿富汗":     ("阿富汗", "喀布尔", 34.5553, 69.2075),
    "朝鲜":       ("朝鲜", "平壤", 39.0392, 125.7625),
}


def _build_source_country_map() -> dict[str, tuple[str, str, float, float]]:
    """Pre-build O(1) mapping: source name → (country, city, lat, lng)."""
    result: dict[str, tuple[str, str, float, float]] = {}
    for s in SOURCES:
        if s.country_focus:
            country = s.country_focus[0]
            if country in _COUNTRY_COORDS:
                result[s.name] = _COUNTRY_COORDS[country]
                continue
        if s.region in _REGION_FALLBACK:
            result[s.name] = _REGION_FALLBACK[s.region]
            continue
        result[s.name] = ("全球", "未知", 20.0, 0.0)
    return result


SOURCE_COUNTRY_MAP: dict[str, tuple[str, str, float, float]] = _build_source_country_map()


def lookup_source_country(source_system: str) -> tuple[str, str, float, float] | None:
    """Look up (country, city, lat, lng) from a source_system string.

    Tries exact match first, then partial match against known source names.
    Returns None if nothing matches.
    """
    if not source_system:
        return None
    if source_system in SOURCE_COUNTRY_MAP:
        return SOURCE_COUNTRY_MAP[source_system]
    lower = source_system.lower()
    for name, coords in SOURCE_COUNTRY_MAP.items():
        if name.lower() in lower:
            return coords
    return None

CATEGORIES = {
    "news_agency":      "Global News Agencies",
    "international":    "Major International Media",
    "regional_asia":    "Asia Pacific Media",
    "regional_europe":  "European Media",
    "regional_me":      "Middle East Media",
    "regional_africa":  "African Media",
    "regional_americas":"Americas Media",
    "government":       "Government & Official Sources",
    "intl_org":         "International Organizations",
    "think_tank":       "Think Tanks & Research",
    "financial":        "Finance & Economic Intelligence",
    "technology":       "Technology Media",
    "cybersecurity":    "Cybersecurity",
    "osint":            "OSINT & Investigation",
    "defense":          "Defense & Military",
    "environment":      "Environment & Climate",
    "military":         "Military & Defense Intelligence",
    "aviation":         "Aviation & Aerospace",
    "logistics":        "Logistics & Supply Chain",
    "trade":            "Trade & Import/Export Intelligence",
    "social_kol":       "Social Media News KOLs",
    "ai4s":             "AI for Science",
    "ai_hot":           "AI Hot",
}

def get_source(name: str) -> SourceConfig | None:
    return _SOURCE_MAP.get(name)

def by_category(cat: str) -> list[SourceConfig]:
    return [s for s in SOURCES if s.category == cat]

def by_region(region: str) -> list[SourceConfig]:
    return [s for s in SOURCES if s.region == region]

def by_layer_bias(layer: str) -> list[SourceConfig]:
    return [s for s in SOURCES if s.layer_bias == layer]


if __name__ == "__main__":
    print(f"Total OSINT sources cataloged: {len(SOURCES)} across {len(CATEGORIES)} categories")
    for cat_key, cat_label in CATEGORIES.items():
        items = by_category(cat_key)
        if items:
            print(f"\n{cat_label} ({len(items)}):")
            for s in items:
                bias = f" [{s.layer_bias}]" if s.layer_bias else ""
                print(f"  {s.name:25s} cred={s.credibility:.2f}{bias}")
