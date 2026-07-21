from __future__ import annotations

import backend.processors.location as location_module


def test_latin_location_variants_do_not_recompile_regex_on_each_document(monkeypatch):
    searches = 0
    original_search = location_module.re.search

    def count_search(*args, **kwargs):
        nonlocal searches
        searches += 1
        return original_search(*args, **kwargs)

    monkeypatch.setattr(location_module.re, "search", count_search)

    assert location_module._variant_pos("beijing port update", "beijing") == 0
    assert location_module._variant_pos("beijing market update", "beijing") == 0

    assert searches <= 1
