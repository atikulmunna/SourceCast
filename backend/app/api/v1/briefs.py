import uuid

from fastapi import APIRouter, status
from fastapi.responses import Response

from app.api.deps import CurrentUser, DBDep
from app.schemas.briefs import ResearchBriefCreate, ResearchBriefOut
from app.services.brief_service import BriefService

router = APIRouter(prefix="/briefs", tags=["briefs"])


@router.get("", response_model=list[ResearchBriefOut])
async def list_briefs(space_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    return await BriefService(db).list_briefs(current_user.id, space_id)


@router.post("", response_model=ResearchBriefOut, status_code=status.HTTP_201_CREATED)
async def create_brief(data: ResearchBriefCreate, current_user: CurrentUser, db: DBDep):
    return await BriefService(db).create_brief(current_user.id, data)


@router.get("/{brief_id}", response_model=ResearchBriefOut)
async def get_brief(brief_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    return await BriefService(db).get_brief(current_user.id, brief_id)


@router.get("/{brief_id}/export/markdown")
async def export_brief_markdown(brief_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    filename, markdown = await BriefService(db).export_markdown(current_user.id, brief_id)
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{brief_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brief(brief_id: uuid.UUID, current_user: CurrentUser, db: DBDep) -> None:
    await BriefService(db).delete_brief(current_user.id, brief_id)
