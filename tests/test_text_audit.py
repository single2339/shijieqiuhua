"""AC-04-6 / DoD-7: 文案禁词 CI 守卫。"""
from pathlib import Path
from scripts.audit_text import audit


def test_no_forbidden_words_in_source():
    root = Path(__file__).resolve().parent.parent
    hits = audit(root)
    assert hits == [], (
        f"发现 {len(hits)} 处禁词，CI 拒绝：\n"
        + "\n".join(f"  {p}:{n}  [{w}]  {line}" for p, n, w, line in hits)
    )
