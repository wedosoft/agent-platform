"""
JSON Schema Validation Utilities

Provides schema validation for ticket analysis API input/output.
Uses JSON Schema Draft-07 for validation.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError
except ImportError:
    jsonschema = None  # type: ignore
    Draft7Validator = None  # type: ignore
    ValidationError = Exception  # type: ignore

logger = logging.getLogger(__name__)

# Schema directory path
SCHEMA_DIR = Path(__file__).parent.parent / "schemas"


class SchemaValidationError(Exception):
    """Custom exception for schema validation failures."""

    def __init__(self, message: str, errors: List[str]):
        super().__init__(message)
        self.message = message
        self.errors = errors


@lru_cache(maxsize=20)
def _load_schema(schema_name: str) -> Dict[str, Any]:
    """
    Load and cache JSON schema by name.

    Args:
        schema_name: Name of the schema file (without .json extension)

    Returns:
        Parsed JSON schema as dictionary

    Raises:
        FileNotFoundError: If schema file doesn't exist
    """
    schema_path = SCHEMA_DIR / f"{schema_name}.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_name} at {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_or_raise(schema_name: str, obj: Dict[str, Any]) -> None:
    """
    Validate object against named JSON schema.

    Raises HTTPException 400 with INVALID_INPUT_SCHEMA on validation failure.

    Args:
        schema_name: Name of the schema to validate against
        obj: Dictionary object to validate

    Raises:
        HTTPException: 400 if validation fails, 500 if schema loading fails
    """
    if jsonschema is None:
        logger.warning("jsonschema not installed, skipping validation")
        return

    try:
        schema = _load_schema(schema_name)
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(obj))

        if errors:
            # Format error messages (limit to first 5)
            error_messages = []
            for e in errors[:5]:
                path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "$"
                error_messages.append(f"{path}: {e.message}")

            logger.warning(f"Schema validation failed for {schema_name}: {error_messages}")

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_INPUT_SCHEMA",
                    "message": f"Input validation failed against {schema_name}",
                    "errors": error_messages
                }
            )

    except FileNotFoundError as e:
        logger.error(f"Schema loading error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "SCHEMA_NOT_FOUND",
                "message": str(e)
            }
        )
    except json.JSONDecodeError as e:
        logger.error(f"Schema parse error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "SCHEMA_PARSE_ERROR",
                "message": f"Failed to parse schema: {schema_name}"
            }
        )


def validate_output(schema_name: str, obj: Dict[str, Any]) -> bool:
    """
    Validate output object against schema.

    Non-throwing version for output validation before response.

    Args:
        schema_name: Name of the schema to validate against
        obj: Dictionary object to validate

    Returns:
        True if valid, False otherwise
    """
    if jsonschema is None:
        logger.warning("jsonschema not installed, assuming valid")
        return True

    try:
        schema = _load_schema(schema_name)
        jsonschema.validate(obj, schema)
        return True
    except (ValidationError, FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Output validation failed for {schema_name}: {e}")
        return False


def get_schema(schema_name: str) -> Optional[Dict[str, Any]]:
    """
    Get schema by name without caching side effects.

    Args:
        schema_name: Name of the schema

    Returns:
        Schema dictionary or None if not found
    """
    try:
        return _load_schema(schema_name)
    except FileNotFoundError:
        return None


def clear_schema_cache() -> None:
    """Clear the schema cache. Useful for testing."""
    _load_schema.cache_clear()
