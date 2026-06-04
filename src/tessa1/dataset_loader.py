"""
Dataset ingestion for Tessa1.

This module is the "pull layer" for Part 1:
- read a local snapshot of a public dataset
- normalize raw records
- map them into Tessa1's internal feed post model
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .models import FeedPost


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_NEWS_DATASET_PATH = PROJECT_ROOT / "data" / "raw" / "uci_news" / "News_Final.csv"


@dataclass
class FeedPostRecord:
    """Normalized feed-style post record derived from the public dataset."""

    post_id: str
    title: str
    headline: str
    source: str
    topic: str
    published_at: Optional[datetime]
    linkedin_popularity: float
    facebook_popularity: float
    googleplus_popularity: float
    popularity_bucket: str
    recency_bucket: str


def load_uci_news_dataframe(csv_path: Optional[Path] = None) -> pd.DataFrame:
    """Load the local UCI news popularity snapshot as a normalized dataframe."""
    dataset_path = csv_path or LOCAL_NEWS_DATASET_PATH
    if not dataset_path.exists():
        raise FileNotFoundError(f"Local dataset snapshot not found: {dataset_path}")

    frame = pd.read_csv(dataset_path)
    if frame.empty:
        raise ValueError("Local dataset snapshot contains no rows.")
    return frame.copy()


def build_feed_post_records(max_rows: int = 200) -> list[FeedPostRecord]:
    """Map raw UCI rows into normalized feed-style records."""
    frame = load_uci_news_dataframe()
    frame = frame.head(max_rows).copy()

    posts: list[FeedPostRecord] = []
    now = datetime.now(timezone.utc)

    for _, row in frame.iterrows():
        published_at = _parse_datetime(row.get("PublishDate"))
        linkedin_popularity = _to_float(row.get("LinkedIn"))
        facebook_popularity = _to_float(row.get("Facebook"))
        googleplus_popularity = _to_float(row.get("GooglePlus"))

        posts.append(
            FeedPostRecord(
                post_id=str(row.get("IDLink", "")),
                title=_to_text(row.get("Title")),
                headline=_to_text(row.get("Headline")),
                source=_to_text(row.get("Source")),
                topic=_to_text(row.get("Topic")),
                published_at=published_at,
                linkedin_popularity=linkedin_popularity,
                facebook_popularity=facebook_popularity,
                googleplus_popularity=googleplus_popularity,
                popularity_bucket=_popularity_bucket(linkedin_popularity),
                recency_bucket=_recency_bucket(published_at, now),
            )
        )

    return posts


def build_feed_posts(max_rows: int = 200) -> list[FeedPost]:
    """Map UCI rows into Tessa1's internal FeedPost model."""
    return [record_to_feed_post(record) for record in build_feed_post_records(max_rows=max_rows)]


def record_to_feed_post(record: FeedPostRecord) -> FeedPost:
    """Convert a normalized dataset record into the shared FeedPost model."""
    author = record.source or "Unknown source"
    body = record.headline or record.title
    topics = [record.topic] if record.topic else []

    return FeedPost(
        post_id=record.post_id,
        author=author,
        title=record.title,
        body=body,
        topics=topics,
        popularity_bucket=record.popularity_bucket,
        recency_bucket=record.recency_bucket,
        source=record.source,
        published_at=record.published_at,
        headline=record.headline,
        linkedin_popularity=record.linkedin_popularity,
        facebook_popularity=record.facebook_popularity,
        googleplus_popularity=record.googleplus_popularity,
        metadata={
            "dataset": "uci_news_popularity",
        },
    )


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _to_float(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = _to_text(value)
    if not text:
        return None

    parsed = pd.to_datetime(text, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _popularity_bucket(linkedin_popularity: float) -> str:
    if linkedin_popularity >= 500:
        return "high"
    if linkedin_popularity >= 100:
        return "medium"
    return "low"


def _recency_bucket(published_at: Optional[datetime], now: datetime) -> str:
    if published_at is None:
        return "unknown"

    age_days = (now - published_at).total_seconds() / 86400.0
    if age_days <= 3:
        return "recent"
    if age_days <= 14:
        return "warm"
    return "stale"
