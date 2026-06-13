from __future__ import annotations

from dataclasses import dataclass
from string import Template


WIN007_BASE_URL = "http://m.win007.com/"

DEFAULT_MATCH_LEVEL = 2


@dataclass(frozen=True)
class FootballSourceTemplate:
    adapter: str
    label: str
    source_type: str
    url_template: str
    topic: str
    description: str
    requires_win007_match_id: bool = False
    default_enabled: bool = True

    def render_url(self, *, match_level: int = DEFAULT_MATCH_LEVEL, match_id: str = "", comp_id: str = "", flesh: str = "0") -> str:
        template = Template(self.url_template)
        return template.safe_substitute(
            matchLevel=str(match_level),
            matchId=match_id,
            scheid=match_id,
            flesh=flesh,
        )


WIN007_SOURCE_TEMPLATES = (
    FootballSourceTemplate(
        adapter="win007_schedule",
        label="Win007/球探赛程",
        source_type="fixture",
        url_template="http://m.win007.com/phone/Schedule_0_${matchLevel}.txt",
        topic="fixture.win007.schedule",
        description="对应 farich/foot MatchLastProcesser，按 match_level 抓取赛程、联赛和比分字段。",
    ),
    FootballSourceTemplate(
        adapter="win007_baseface",
        label="Win007/球探基本面",
        source_type="fundamental",
        url_template="http://m.win007.com/analy/Analysis/${matchId}.htm",
        topic="fundamental.win007.analysis",
        description="对应 BaseFaceProcesser，覆盖积分排名、历史交锋、近期战绩和未来三场。",
        requires_win007_match_id=True,
    ),
    FootballSourceTemplate(
        adapter="win007_history_fixture",
        label="Win007/球探历史赛程",
        source_type="history",
        url_template="http://m.win007.com/info/Fixture/${season}/${leagueId}_${subId}_${round}.htm",
        topic="history.win007.fixture",
        description="对应 WIN007_MATCH_HIS_PATTERN，需联赛、赛季、阶段和轮次后才能抓取。",
        requires_win007_match_id=False,
        default_enabled=False,
    ),
)


def win007_match_id_from_text(text: str) -> str:
    marker = "win007:"
    lowered = text.lower()
    if marker not in lowered:
        return ""
    tail = lowered.split(marker, 1)[1]
    digits = []
    for char in tail:
        if char.isdigit():
            digits.append(char)
        elif digits:
            break
    return "".join(digits)
