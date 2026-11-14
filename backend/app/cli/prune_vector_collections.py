"""List or delete Qdrant collections left over from earlier embedding models.

    python -m app.cli.prune_vector_collections          # dry run: list only
    python -m app.cli.prune_vector_collections --apply  # delete them

Only `source_chunks_*` collections other than the active one (named by
embedding_service.collection_name) are touched. Deleting a collection cannot be
undone; sources that should stay searchable must be re-ingested afterwards.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from app.services import embedding_service, qdrant_service

PREFIX = "source_chunks_"


@dataclass(frozen=True)
class Stale:
    name: str
    points: int


async def stale_collections(client) -> list[Stale]:
    active = embedding_service.collection_name()
    response = await client.get_collections()
    names = sorted(c.name for c in response.collections)
    stale = []
    for name in names:
        if name.startswith(PREFIX) and name != active:
            count = await client.count(collection_name=name, exact=True)
            stale.append(Stale(name, count.count))
    return stale


async def prune(client, *, apply: bool) -> list[Stale]:
    stale = await stale_collections(client)
    for item in stale:
        if apply:
            await client.delete_collection(collection_name=item.name)
    return stale


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="delete instead of listing")
    args = parser.parse_args()

    client = qdrant_service.get_client()
    print(f"Active collection: {embedding_service.collection_name()}")
    stale = await prune(client, apply=args.apply)
    if not stale:
        print("No stale collections.")
    for item in stale:
        verb = "Deleted" if args.apply else "Would delete"
        print(f"{verb} {item.name} ({item.points} points)")
    if stale and not args.apply:
        print("Dry run. Re-run with --apply to delete.")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
