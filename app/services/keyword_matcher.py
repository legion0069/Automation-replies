import re
from typing import List, Optional, Tuple
from app.schemas.config import AutomationConfig


class KeywordMatcher:
    """Detects configurable keywords or regex patterns in comment text."""

    def __init__(self, config: Optional[AutomationConfig] = None):
        self.config = config

    def match(self, text: str, config: Optional[AutomationConfig] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if text contains any configured keywords.
        Returns (is_matched, matched_keyword_or_pattern).
        """
        active_config = config or self.config
        if not active_config or not active_config.keywords:
            return False, None

        if not text:
            return False, None

        mode = active_config.match_mode
        case_sensitive = active_config.case_sensitive
        flags = 0 if case_sensitive else re.IGNORECASE

        for keyword in active_config.keywords:
            keyword = keyword.strip()
            if not keyword:
                continue

            if mode == "regex":
                try:
                    pattern = re.compile(keyword, flags)
                    if pattern.search(text):
                        return True, keyword
                except re.error:
                    # Invalid regex pattern; fallback to literal search
                    if (keyword in text) if case_sensitive else (keyword.lower() in text.lower()):
                        return True, keyword

            elif mode == "exact":
                # Matches whole word boundary, e.g. "link" matches "send link" but not "blink"
                pattern = re.compile(rf"\b{re.escape(keyword)}\b", flags)
                if pattern.search(text):
                    return True, keyword

            else:  # "partial" mode (default)
                # Matches if keyword exists anywhere in text or as substring
                search_text = text if case_sensitive else text.lower()
                target_kw = keyword if case_sensitive else keyword.lower()
                if target_kw in search_text:
                    return True, keyword

        return False, None

