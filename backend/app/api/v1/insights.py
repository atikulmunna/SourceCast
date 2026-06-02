import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DBDep
from app.schemas.insights import SavedInsightCreate, SavedInsightOut
from app.services.insight_service import InsightService

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=list[SavedInsightOut])
async def list_insights(space_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    return await InsightService(db).list_insights(current_user.id, space_id)


@router.post("", response_model=SavedInsightOut, status_code=status.HTTP_201_CREATED)
async def create_insight(data: SavedInsightCreate, current_user: CurrentUser, db: DBDep):
    return await InsightService(db).create_insight(current_user.id, data)


@router.delete("/{insight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_insight(insight_id: uuid.UUID, current_user: CurrentUser, db: DBDep) -> None:
    await InsightService(db).delete_insight(current_user.id, insight_id)
