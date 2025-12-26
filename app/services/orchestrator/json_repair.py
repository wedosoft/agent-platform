"""
JSON Repair Utility

Handles malformed JSON from LLM responses by attempting common fixes:
- Removing markdown code blocks
- Stripping leading/trailing text
- Fixing trailing commas
- Balancing brackets
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class JSONRepairError(Exception):
    """Raised when JSON cannot be repaired."""

    def __init__(self, message: str, original_text: str):
        super().__init__(message)
        self.original_text = original_text


def repair_json(text: str, max_attempts: int = 1) -> str:
    """
    Attempt to repair malformed JSON from LLM output.

    Common issues handled:
    - Markdown code blocks (```json ... ```)
    - Leading/trailing explanatory text
    - Trailing commas before } or ]
    - Unbalanced brackets (simple cases)

    Args:
        text: Raw LLM output that should contain JSON
        max_attempts: Maximum repair attempts (default 1 as per spec)

    Returns:
        Repaired JSON string

    Raises:
        JSONRepairError: If JSON cannot be repaired after max_attempts
    """
    if not text or not text.strip():
        raise JSONRepairError("Empty input", text or "")

    original = text
    attempt = 0

    while attempt < max_attempts:
        attempt += 1

        # Try parsing as-is first
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # Step 1: Remove markdown code blocks
        text = _remove_markdown_blocks(text)

        # Step 2: Extract JSON object/array from surrounding text
        text = _extract_json(text)

        # Step 3: Fix common syntax issues
        text = _fix_syntax(text)

        # Step 4: Balance brackets if needed
        text = _balance_brackets(text)

        # Try parsing again
        try:
            json.loads(text)
            logger.info(f"JSON repair succeeded on attempt {attempt}")
            return text
        except json.JSONDecodeError as e:
            logger.warning(f"JSON repair attempt {attempt} failed: {e}")

    raise JSONRepairError(
        f"Failed to repair JSON after {max_attempts} attempts",
        original
    )


def try_parse_json(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Try to parse JSON with automatic repair.

    Args:
        text: Raw text that should contain JSON

    Returns:
        Tuple of (parsed_dict, error_message)
        - If successful: (dict, None)
        - If failed: (None, error_message)
    """
    try:
        repaired = repair_json(text)
        parsed = json.loads(repaired)
        if not isinstance(parsed, dict):
            return None, "JSON must be an object, not array or primitive"
        return parsed, None
    except JSONRepairError as e:
        return None, str(e)
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"


def _remove_markdown_blocks(text: str) -> str:
    """Remove markdown code block wrappers."""
    # Remove ```json and ``` blocks
    text = re.sub(r"```json\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def _extract_json(text: str) -> str:
    """Extract JSON object from surrounding text."""
    # Find the first { and last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")

    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace:last_brace + 1]

    # Try array
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")

    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        return text[first_bracket:last_bracket + 1]

    return text


def _fix_syntax(text: str) -> str:
    """Fix common JSON syntax issues."""
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Fix unquoted keys (simple cases)
    # This is risky, so we only do it for obvious patterns
    # text = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)

    return text


def _balance_brackets(text: str) -> str:
    """Add missing closing brackets."""
    open_braces = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")

    if open_braces > 0:
        text += "}" * open_braces
    if open_brackets > 0:
        text += "]" * open_brackets

    return text
