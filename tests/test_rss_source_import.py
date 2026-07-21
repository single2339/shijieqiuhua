from backend.collectors.horizon_bridge import (
    _BESTBLOGS_OPML_PATH,
    _BESTBLOGS_RSS_FEEDS,
    _DEFAULT_RSS_FEEDS,
)


def test_bestblogs_opml_is_imported() -> None:
    assert _BESTBLOGS_OPML_PATH.name == "BestBlogs_RSS_ALL.opml"
    assert _BESTBLOGS_OPML_PATH.parent.name == "config"
    assert _BESTBLOGS_OPML_PATH.exists()
    assert len(_BESTBLOGS_RSS_FEEDS) == 400
    assert all(feed.category == "bestblogs" for feed in _BESTBLOGS_RSS_FEEDS)
    assert len({feed.name for feed in _BESTBLOGS_RSS_FEEDS}) == 400


def test_default_rss_feeds_exclude_bestblogs_without_duplicate_urls() -> None:
    urls = [str(feed.url).rstrip("/") for feed in _DEFAULT_RSS_FEEDS]
    assert len(urls) == len(set(urls))
    assert "https://feeds.bbci.co.uk/news/world/rss.xml" in urls
    assert all(feed.category != "bestblogs" for feed in _DEFAULT_RSS_FEEDS)


def test_bestblogs_can_be_enabled_as_an_explicit_knowledge_feed() -> None:
    from backend.collectors.horizon_bridge import build_default_rss_feeds

    urls = [
        str(feed.url).rstrip("/")
        for feed in build_default_rss_feeds(include_knowledge=True)
    ]

    assert "https://www.qbitai.com/feed" in urls
    assert "https://blog.langchain.dev/rss" in urls
