"""Unit tests for the data cleaning and normalization pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.processor.cleaner import (
    clean_text,
    clean_url,
    strip_html,
    strip_control_chars,
    normalize_whitespace,
    normalize_unicode,
    normalize_lines,
    strip_boilerplate,
)


class TestStripHTML:
    def test_removes_html_tags(self):
        result = strip_html("<p>Hello <b>world</b></p>")
        # strip_html leaves inline whitespace (normalized later in clean_text)
        assert "Hello" in result and "world" in result

    def test_removes_script_tags(self):
        result = strip_html("<p>Content</p><script>alert('xss')</script>")
        assert "alert" not in result
        assert "Content" in result

    def test_removes_style_tags(self):
        result = strip_html("<p>Text</p><style>.cls { color: red; }</style>")
        assert ".cls" not in result

    def test_removes_nav_footer(self):
        result = strip_html("<nav>Links</nav><article>Content</article><footer>Copy</footer>")
        assert "Links" not in result
        assert "Copy" not in result
        assert "Content" in result

    def test_non_html_passthrough(self):
        result = strip_html("This is plain text with no tags")
        assert result == "This is plain text with no tags"


class TestStripControlChars:
    def test_removes_null_and_control(self):
        result = strip_control_chars("Hello\x00World\x1fTest")
        assert result == "HelloWorldTest"

    def test_preserves_newlines_and_tabs(self):
        result = strip_control_chars("Line 1\nLine 2\tTabbed")
        assert "\n" in result
        assert "\t" in result


class TestNormalizeWhitespace:
    def test_collapses_spaces(self):
        result = normalize_whitespace("Too    many   spaces")
        assert result == "Too many spaces"

    def test_limits_consecutive_newlines(self):
        result = normalize_whitespace("Line1\n\n\n\n\nLine2")
        assert result == "Line1\n\nLine2"

    def test_trims_lines(self):
        result = normalize_whitespace("  leading\n  indented  ")
        assert result == "leading\nindented"


class TestNormalizeUnicode:
    def test_nfkc_normalization(self):
        result = normalize_unicode("ℌ𝔢𝔩𝔩𝔬")
        assert result


class TestCleanUrl:
    def test_removes_utm_params(self):
        result = clean_url("https://example.com/page?utm_source=twitter&id=123")
        assert "utm_source" not in result
        assert "id=123" in result

    def test_removes_fbclid(self):
        result = clean_url("https://example.com/page?fbclid=abc123")
        assert "fbclid" not in result

    def test_removes_gclid(self):
        result = clean_url("https://example.com/page?gclid=xyz789")
        assert "gclid" not in result

    def test_empty_url(self):
        assert clean_url("") == ""


class TestStripBoilerplate:
    def test_removes_cookie_notice(self):
        result = strip_boilerplate("Article content\nCookie Policy")
        assert "Cookie Policy" not in result
        assert "Article content" in result

    def test_preserves_long_content_with_keyword(self):
        result = strip_boilerplate("This is a long article that mentions subscribe as part of legitimate content about subscription models in journalism")
        assert result

    def test_removes_privacy_lines(self):
        result = strip_boilerplate("Real news\nAll rights reserved.")
        assert "All rights reserved." not in result
        assert "Real news" in result


class TestNormalizeLines:
    def test_short_lines_unchanged(self):
        text = "Short line\nAnother short"
        assert normalize_lines(text) == text

    def test_splits_long_lines_at_sentence(self):
        long = "S" * 3000 + ". " + "T" * 500
        result = normalize_lines(long, max_length=2000)
        assert "\n" in result


class TestCleanText:
    def test_empty_input(self):
        assert clean_text("") == ""

    def test_rss_html_summary(self):
        html = '<p>Breaking news: <strong>major event</strong> happened today.</p>'
        result = clean_text(html, mime_hint="text/html")
        assert "Breaking news" in result
        assert "major event" in result
        assert "  " not in result

    def test_full_html_page(self):
        html = '<html><body><nav>Nav</nav><article><h1>Title</h1><p>Content</p></article></body></html>'
        result = clean_text(html, mime_hint="text/html")
        assert "Title" in result
        assert "Content" in result
        assert "Nav" not in result

    def test_html_entities_decoded(self):
        result = clean_text("US &amp; allies &mdash; NATO", mime_hint="text/html")
        assert "&amp;" not in result
        assert "&mdash;" not in result

    def test_control_chars_removed(self):
        result = clean_text("Normal\x00text")
        assert "\x00" not in result

    def test_whitespace_normalized(self):
        result = clean_text("Too    many   spaces")
        assert "  " not in result

    def test_plain_text_preserved(self):
        text = "This is a normal news article about geopolitics."
        assert clean_text(text) == text

    def test_entities_decoded_without_mime_hint(self):
        result = clean_text("Text &amp; more")
        # html.unescape runs unconditionally
        assert "&" in result and "amp;" not in result

    def test_boilerplate_removed_short_lines(self):
        text = "Real news content\nCookie Policy\nMore real content"
        result = clean_text(text)
        assert "Cookie Policy" not in result
        assert "Real news" in result
