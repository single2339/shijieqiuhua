from backend.models import ReportRequest


def test_report_request_accepts_selected_brief_materials():
    req = ReportRequest(
        topic="能源态势",
        item_ids=["item-1"],
        event_ids=["EVT-1"],
        warning_ids=["WARN-1"],
        source_materials=[
            {
                "id": "item-1",
                "type": "item",
                "title": "港口能源供应异常",
                "summary": "多源报道显示供应链受阻",
                "source": "bbc",
                "sources": ["bbc"],
                "date": "2026-06-01",
                "layer": "energy",
                "country": "中国",
            }
        ],
    )

    assert req.item_ids == ["item-1"]
    assert req.event_ids == ["EVT-1"]
    assert req.warning_ids == ["WARN-1"]
    assert req.source_materials[0].type == "item"
    assert req.source_materials[0].title == "港口能源供应异常"
