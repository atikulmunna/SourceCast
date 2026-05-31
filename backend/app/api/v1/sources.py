import logging
import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

from app.api.deps import CurrentUser, DBDep
from app.models.source import Source
from app.schemas.sources import (
    SourceCreateRequest,
    SourceIngestResponse,
    SourceOut,
    SourcePreviewRequest,
    SourcePreviewResponse,
)
from app.services.ingestion_service import create_source_and_enqueue
from app.services.source_preview_service import preview_source

router = APIRouter(prefix="/sources", tags=["sources"])


# ── Preview ────────────────────────────────────────────────────────────────────


@router.post("/preview", response_model=SourcePreviewResponse)
async def preview_source_url(
    data: SourcePreviewRequest,
    current_user: CurrentUser,
    db: DBDep,
) -> SourcePreviewResponse:
    """
    Preview metadata for a source URL before ingestion.
    Returns title, creator, duration, thumbnail, and estimated processing time.
    """
    return await preview_source(data.url, data.whisper_model)


# ── Create / Ingest ────────────────────────────────────────────────────────────


@router.post("", response_model=SourceIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_source(
    data: SourceCreateRequest,
    current_user: CurrentUser,
    db: DBDep,
) -> SourceIngestResponse:
    """
    Create a source and kick off the ingestion pipeline.
    Returns immediately with the source and job IDs — subscribe to
    GET /jobs/{job_id}/stream for real-time progress.
    """
    source, job = await create_source_and_enqueue(
        db=db,
        user_id=current_user.id,
        url=data.url,
        space_id=data.space_id,
        whisper_model=data.whisper_model,
        language=data.language,
        audio_storage_policy=data.audio_storage_policy,
    )
    return SourceIngestResponse(
        source=SourceOut.model_validate(source),
        job_id=job.id,
        job_status=job.status,
    )


# ── List ───────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[SourceOut])
async def list_sources(
    current_user: CurrentUser,
    db: DBDep,
    space_id: uuid.UUID | None = None,
) -> list[SourceOut]:
    """
    List all sources owned by the current user.
    Optionally filter by space_id.
    """
    if space_id:
        from app.models.source_space import SourceSpace

        result = await db.execute(
            select(Source)
            .join(SourceSpace, SourceSpace.source_id == Source.id)
            .where(
                Source.user_id == current_user.id,
                SourceSpace.space_id == space_id,
            )
            .order_by(Source.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Source)
            .where(Source.user_id == current_user.id)
            .order_by(Source.created_at.desc())
        )
    sources = result.scalars().all()
    return [SourceOut.model_validate(s) for s in sources]


# ── Get single ─────────────────────────────────────────────────────────────────


@router.get("/{source_id}", response_model=SourceOut)
async def get_source(
    source_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> SourceOut:
    source = await _get_owned_source(db, source_id, current_user.id)
    return SourceOut.model_validate(source)


# ── Delete ─────────────────────────────────────────────────────────────────────


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> None:
    """
    Delete a source and all associated data (segments, chunks, audio).
    Vector cleanup will be added in Phase 3.
    """
    from pathlib import Path

    from app.services.audio_service import delete_audio

    source = await _get_owned_source(db, source_id, current_user.id)

    # Best-effort audio cleanup before row deletion
    if source.audio_file_url:
        try:
            await delete_audio(Path(source.audio_file_url))
        except Exception:
            pass  # Don't block deletion on cleanup failure

    # Delete Qdrant vectors for this source (best-effort)
    try:
        from app.core.config import settings
        from app.services import qdrant_service

        await qdrant_service.delete_by_source(settings.DEFAULT_QDRANT_COLLECTION, source.id)
    except Exception as exc:
        logger.warning("Qdrant cleanup failed for source %s: %s", source_id, exc)

    await db.delete(source)  # cascades to segments, chunks, jobs, source_spaces
    await db.commit()


# ── Transcript viewer ───────────────────────────────────────────────────


@router.get("/{source_id}/transcript", response_model=None)
async def get_transcript(
    source_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=200),
) -> dict:
    """
    Paginated transcript viewer.
    Optional `search` does a case-insensitive substring match on segment text.
    """
    from app.models.transcript_segment import TranscriptSegment
    from app.schemas.transcript import TranscriptPageResponse, TranscriptSegmentOut

    await _get_owned_source(db, source_id, current_user.id)

    base_q = select(TranscriptSegment).where(TranscriptSegment.source_id == source_id)
    if search:
        base_q = base_q.where(TranscriptSegment.text.ilike(f"%{search}%"))

    total_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = total_result.scalar_one()

    offset = (page - 1) * limit
    segs_result = await db.execute(
        base_q.order_by(TranscriptSegment.segment_index).offset(offset).limit(limit)
    )
    segs = segs_result.scalars().all()

    return TranscriptPageResponse(
        segments=[TranscriptSegmentOut.model_validate(s) for s in segs],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(segs)) < total,
    ).model_dump()


@router.get("/{source_id}/transcript/range", response_model=None)
async def get_transcript_range(
    source_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
    start_time_sec: float = Query(..., ge=0),
    end_time_sec: float = Query(..., ge=0),
) -> dict:
    """Return all transcript segments within a timestamp range."""
    from app.models.transcript_segment import TranscriptSegment
    from app.schemas.transcript import TranscriptSegmentOut

    await _get_owned_source(db, source_id, current_user.id)

    result = await db.execute(
        select(TranscriptSegment)
        .where(
            TranscriptSegment.source_id == source_id,
            TranscriptSegment.start_time_sec >= start_time_sec,
            TranscriptSegment.end_time_sec <= end_time_sec,
        )
        .order_by(TranscriptSegment.segment_index)
    )
    segs = result.scalars().all()
    return {"segments": [TranscriptSegmentOut.model_validate(s).model_dump() for s in segs]}


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _get_owned_source(
    db,
    source_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Source:
    from app.core.exceptions import ForbiddenException, NotFoundException

    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise NotFoundException("Source not found")
    if source.user_id != user_id:
        raise ForbiddenException("You do not own this source")
    return source
