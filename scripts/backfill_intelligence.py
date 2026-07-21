#!/usr/bin/env python3
"""从不可变的原始证据层回填标准证据层和情报产品层数据。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.intelligence.backfill import backfill_intelligence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=PROJECT_ROOT / "bronze_storage")
    parser.add_argument("--limit", type=int, default=0, help="Maximum documents to scan; 0 means all")
    args = parser.parse_args()
    print(json.dumps(
        backfill_intelligence(args.storage, limit=max(args.limit, 0)),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
