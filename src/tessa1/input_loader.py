"""
Harness-side input loader for Tessa1.

This module is responsible for deterministic input acquisition:
- read synthetic user profiles from JSON
- read deterministic scoring config from JSON
- load candidate posts from the dataset adapter

It is intentionally not an agent. The orchestrator calls this loader first,
then passes structured objects to the agent layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .dataset_loader import build_feed_posts
from .models import FeedInputs, ScoringConfig, UserProfile


class FeedInputLoader:
    """Load all feed inputs needed by the orchestrator."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        max_posts: int = 200,
    ):
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.max_posts = max_posts
        self.users_path = self.project_root / "data" / "users.json"
        self.scoring_path = self.project_root / "config" / "scoring.json"

    def load_inputs(self) -> FeedInputs:
        """Load all structured feed inputs for a ranking request."""
        return FeedInputs(
            users=self.load_user_profiles(),
            posts=build_feed_posts(max_rows=self.max_posts),
            scoring_config=self.load_scoring_config(),
        )

    def load_user_profiles(self) -> list[UserProfile]:
        """Load synthetic user profiles from JSON."""
        payload = self._read_json(self.users_path)
        if not isinstance(payload, list):
            raise ValueError("users.json must contain a top-level list.")

        return [self._parse_user_profile(item, index) for index, item in enumerate(payload, start=1)]

    def load_scoring_config(self) -> ScoringConfig:
        """Load deterministic ranking policy from JSON."""
        payload = self._read_json(self.scoring_path)
        if not isinstance(payload, dict):
            raise ValueError("scoring.json must contain a top-level object.")

        top_k = payload.get("top_k", 5)
        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError("scoring.json top_k must be a positive integer.")

        weights = self._parse_float_mapping(payload.get("weights"), field_name="weights")
        bucket_bonuses = self._parse_bucket_bonuses(payload.get("bucket_bonuses"))
        feature_definitions = self._parse_string_mapping(
            payload.get("feature_definitions"),
            field_name="feature_definitions",
        )
        notes = self._coerce_string_list(payload.get("notes", []), field_name="notes")

        return ScoringConfig(
            top_k=top_k,
            weights=weights,
            bucket_bonuses=bucket_bonuses,
            feature_definitions=feature_definitions,
            notes=notes,
        )

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")

        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _parse_user_profile(self, payload: Any, index: int) -> UserProfile:
        if not isinstance(payload, dict):
            raise ValueError(f"User profile #{index} must be an object.")

        return UserProfile(
            user_id=self._require_text(payload, "user_id", index),
            name=self._require_text(payload, "name", index),
            headline=self._require_text(payload, "headline", index),
            skills=self._coerce_string_list(payload.get("skills", []), field_name="skills"),
            interests=self._coerce_string_list(payload.get("interests", []), field_name="interests"),
            recent_engagement_topics=self._coerce_string_list(
                payload.get("recent_engagement_topics", []),
                field_name="recent_engagement_topics",
            ),
            preferred_sources=self._coerce_string_list(
                payload.get("preferred_sources", []),
                field_name="preferred_sources",
            ),
            metadata={"notes": payload.get("notes", "")} if payload.get("notes") else {},
        )

    def _require_text(self, payload: dict[str, Any], field_name: str, index: int) -> str:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"User profile #{index} field '{field_name}' must be a non-empty string.")
        return value.strip()

    def _coerce_string_list(self, value: Any, field_name: str) -> list[str]:
        if not isinstance(value, list):
            raise ValueError(f"Field '{field_name}' must be a list of strings.")

        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Field '{field_name}' must contain only non-empty strings.")
            normalized.append(item.strip())

        return normalized

    def _parse_float_mapping(self, value: Any, field_name: str) -> dict[str, float]:
        if not isinstance(value, dict):
            raise ValueError(f"Field '{field_name}' must be an object of numeric values.")

        parsed: dict[str, float] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"Field '{field_name}' contains an invalid key.")
            if not isinstance(item, (int, float)):
                raise ValueError(f"Field '{field_name}.{key}' must be numeric.")
            parsed[key] = float(item)

        return parsed

    def _parse_string_mapping(self, value: Any, field_name: str) -> dict[str, str]:
        if not isinstance(value, dict):
            raise ValueError(f"Field '{field_name}' must be an object of string values.")

        parsed: dict[str, str] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"Field '{field_name}' contains an invalid key.")
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Field '{field_name}.{key}' must be a non-empty string.")
            parsed[key] = item.strip()

        return parsed

    def _parse_bucket_bonuses(self, value: Any) -> dict[str, dict[str, float]]:
        if not isinstance(value, dict):
            raise ValueError("Field 'bucket_bonuses' must be an object of nested numeric values.")

        parsed: dict[str, dict[str, float]] = {}
        for category, mapping in value.items():
            if not isinstance(category, str) or not category.strip():
                raise ValueError("Field 'bucket_bonuses' contains an invalid category key.")
            parsed[category] = self._parse_float_mapping(
                mapping,
                field_name=f"bucket_bonuses.{category}",
            )

        return parsed
