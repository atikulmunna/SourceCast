from __future__ import annotations

from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source


def build_timestamp_url(
    source_url: str | None,
    source_type: str | None,
    start_time_sec: Decimal | float | int,
) -> str | None:
    if not source_url:
        return None

    if source_type != "youtube":
        return source_url

    parts = urlsplit(source_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["t"] = str(max(0, int(start_time_sec)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


async def add_navigation_urls(
    db: AsyncSession,
    user_id,
    evidence_items: list,
) -> list:
    source_ids = {item.source_id for item in evidence_items if item.source_id}
    if not source_ids:
        return evidence_items

    result = await db.execute(
        select(Source).where(Source.id.in_(source_ids), Source.user_id == user_id)
    )
    sources = {source.id: source for source in result.scalars().all()}
    for item in evidence_items:
        source = sources.get(item.source_id)
        if source:
            item.navigation_url = build_timestamp_url(
                source.canonical_url or source.source_url,
                source.source_type,
                item.start_time_sec,
            )
    return evidence_items
