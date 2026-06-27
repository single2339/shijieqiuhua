#!/usr/bin/env python3
"""文案审计 — 扫描源码中的禁词（PRD §4.6 / AC-04-6 / DoD-7）。

用法:
  python3 scripts/audit_text.py          # 发现禁词退出码 1
  python3 scripts/audit_text.py --list   # 列出禁词规则

CI:  pytest tests/test_text_audit.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# PRD §4.6 禁词表 — 仅限预测结论中的主动正面使用；否定语境豁免（见下）
FORBIDDEN = [
    "必胜", "稳赢", "保赢", "稳红",
    "推荐", "推单", "跟单", "内部消息",
    "大胆", "稳胆", "稳串", "专家", "爆料",
    "投注", "押注", "买注", "单关", "串关", "过关",
]

_PATTERN = re.compile("|".join(re.escape(w) for w in FORBIDDEN))

# 扫描范围
_SCAN_GLOBS = ["backend/**/*.py", "frontend/src/**/*.ts", "frontend/src/**/*.tsx"]

# 跳过路径（原始数据或与足球产品无关的子模块）
_SKIP_PATH_PARTS = {"agents", "seed_data.py"}

# 跳过文件（本身是禁词定义）
_SKIP_FILES = {Path(__file__).resolve()}

# 行级豁免：若行内出现以下任一前缀，则该词在此语境合规
# - "不" / "非" / "无" 后紧跟禁词 → 否定/免责声明
# - "你是" → LLM 角色定义（内部 system prompt）
_EXEMPT_PATTERNS = re.compile(r"(不|非|无|你是).{0,12}$")


def _is_exempt(line: str, match_start: int) -> bool:
    # Check if any exemption pattern ends just before or at the match position
    prefix = line[:match_start]
    return bool(_EXEMPT_PATTERNS.search(prefix))


def _skip_path(rel: Path) -> bool:
    return bool(set(rel.parts) & _SKIP_PATH_PARTS) or rel.name in _SKIP_PATH_PARTS


def audit(root: Path) -> list[tuple[Path, int, str, str]]:
    hits: list[tuple[Path, int, str, str]] = []
    for glob in _SCAN_GLOBS:
        for path in sorted(root.glob(glob)):
            if path.resolve() in _SKIP_FILES:
                continue
            rel = path.relative_to(root)
            if _skip_path(rel):
                continue
            try:
                for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    m = _PATTERN.search(line)
                    if m and not _is_exempt(line, m.start()):
                        hits.append((rel, i, m.group(), line.strip()))
            except OSError:
                continue
    return hits


def main() -> int:
    if "--list" in sys.argv:
        print("禁词清单:", ", ".join(FORBIDDEN))
        return 0

    root = Path(__file__).resolve().parent.parent
    hits = audit(root)
    if not hits:
        print("文案审计通过：未发现禁词")
        return 0

    print(f"文案审计失败：发现 {len(hits)} 处禁词")
    for path, lineno, word, line in hits:
        print(f"  {path}:{lineno}  [{word}]  {line[:120]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
