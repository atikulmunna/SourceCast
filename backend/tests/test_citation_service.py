from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from app.services.citation_service import add_navigation_urls, build_timestamp_url


def test_youtube_timestamp_url_preserves_existing_query_parameters() -> None:
    assert build_timestamp_url(
        "https://www.youtube.com/watch?v=abc123&list=research",
        "youtube",
        Decimal("83.900"),
    ) == "https://www.youtube.com/watch?v=abc123&list=research&t=83"


def test_youtube_short_url_gains_timestamp_parameter() -> None:
    assert build_timestamp_url("https://youtu.be/abc123", "youtube", 42) == (
        "https://youtu.be/abc123?t=42"
    )


def test_youtube_timestamp_replaces_existing_offset_and_clamps_negative_values() -> None:
    assert build_timestamp_url("https://youtu.be/abc123?t=80", "youtube", -2) == (
        "https://youtu.be/abc123?t=0"
    )


def test_non_youtube_url_is_preserved() -> None:
    url = "https://example.com/episode.mp3?download=1"
    assert build_timestamp_url(url, "audio", 42) == url


def test_missing_source_url_has_no_navigation_target() -> None:
    assert build_timestamp_url(None, "youtube", 42) is None


class Result:
    def __init__(self, sources):
        self.sources = sources

    def scalars(self):
        return self

    def all(self):
        return self.sources


class DB:
    def __init__(self, sources):
        self.sources = sources

    async def execute(self, statement):
        return Result(self.sources)


@pytest.mark.asyncio
async def test_add_navigation_urls_enriches_known_owned_sources() -> None:
    source_id = uuid.uuid4()
    evidence = SimpleNamespace(
        source_id=source_id,
        start_time_sec=Decimal("75.2"),
        navigation_url=None,
    )
    source = SimpleNamespace(
        id=source_id,
        source_type="youtube",
        source_url="https://youtu.be/abc123",
        canonical_url=None,
    )

    assert await add_navigation_urls(DB([source]), uuid.uuid4(), [evidence]) == [evidence]
    assert evidence.navigation_url == "https://youtu.be/abc123?t=75"


@pytest.mark.asyncio
async def test_add_navigation_urls_skips_lookup_without_source_ids() -> None:
    evidence = SimpleNamespace(source_id=None, navigation_url=None)

    assert await add_navigation_urls(None, uuid.uuid4(), [evidence]) == [evidence]
    assert evidence.navigation_url is None
