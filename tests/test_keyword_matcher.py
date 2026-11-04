import pytest
from app.schemas.config import AutomationConfig
from app.services.keyword_matcher import KeywordMatcher


def test_keyword_matcher_partial_case_insensitive():
    config = AutomationConfig(
        match_mode="partial",
        case_sensitive=False,
        keywords=["link", "roadmap", "pdf"],
    )
    matcher = KeywordMatcher(config)

    # Substrings and case variations
    matched, kw = matcher.match("Please send me the LINK!")
    assert matched is True
    assert kw == "link"

    matched, kw = matcher.match("I want the RoAdMaP for 2025")
    assert matched is True
    assert kw == "roadmap"

    matched, kw = matcher.match("This is an unrelated comment about coffee.")
    assert matched is False
    assert kw is None


def test_keyword_matcher_case_sensitive():
    config = AutomationConfig(
        match_mode="partial",
        case_sensitive=True,
        keywords=["Guide"],
    )
    matcher = KeywordMatcher(config)

    matched, kw = matcher.match("Please send guide")
    assert matched is False

    matched, kw = matcher.match("Please send Guide")
    assert matched is True
    assert kw == "Guide"


def test_keyword_matcher_exact_mode():
    config = AutomationConfig(
        match_mode="exact",
        case_sensitive=False,
        keywords=["link"],
    )
    matcher = KeywordMatcher(config)

    # Word boundary match
    matched, kw = matcher.match("send the link please")
    assert matched is True

    # Substring of another word should not match in exact mode
    matched, kw = matcher.match("don't blink or you miss it")
    assert matched is False


def test_keyword_matcher_regex_mode():
    config = AutomationConfig(
        match_mode="regex",
        case_sensitive=False,
        keywords=[r"batch\s*[0-9]{4}", r"placement.*info"],
    )
    matcher = KeywordMatcher(config)

    matched, kw = matcher.match("I am from batch 2025")
    assert matched is True

    matched, kw = matcher.match("Can I get placement test info?")
    assert matched is True

    matched, kw = matcher.match("Hello there")
    assert matched is False


def test_keyword_matcher_empty_inputs():
    config = AutomationConfig(keywords=[])
    matcher = KeywordMatcher(config)
    matched, kw = matcher.match("any comment")
    assert matched is False

    config_with_kws = AutomationConfig(keywords=["help"])
    matcher = KeywordMatcher(config_with_kws)
    matched, kw = matcher.match("")
    assert matched is False

