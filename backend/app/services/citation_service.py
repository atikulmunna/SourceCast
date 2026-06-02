from __future__ import annotations

from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


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
