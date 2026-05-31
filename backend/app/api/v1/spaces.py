import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DBDep
from app.schemas.spaces import SpaceCreate, SpaceOut, SpaceUpdate
from app.services.space_service import SpaceService

router = APIRouter(prefix="/spaces", tags=["spaces"])


@router.get("", response_model=list[SpaceOut])
async def list_spaces(current_user: CurrentUser, db: DBDep) -> list[SpaceOut]:
    """List all knowledge spaces owned by the current user."""
    service = SpaceService(db)
    return await service.list_spaces(current_user.id)


@router.post("", response_model=SpaceOut, status_code=status.HTTP_201_CREATED)
async def create_space(
    data: SpaceCreate, current_user: CurrentUser, db: DBDep
) -> SpaceOut:
    """Create a new knowledge space."""
    service = SpaceService(db)
    return await service.create_space(current_user.id, data)


@router.get("/{space_id}", response_model=SpaceOut)
async def get_space(
    space_id: uuid.UUID, current_user: CurrentUser, db: DBDep
) -> SpaceOut:
    """Get details of a specific knowledge space."""
    service = SpaceService(db)
    return await service.get_space(current_user.id, space_id)


@router.patch("/{space_id}", response_model=SpaceOut)
async def update_space(
    space_id: uuid.UUID, data: SpaceUpdate, current_user: CurrentUser, db: DBDep
) -> SpaceOut:
    """Update a knowledge space's name or description."""
    service = SpaceService(db)
    return await service.update_space(current_user.id, space_id, data)


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space(
    space_id: uuid.UUID, current_user: CurrentUser, db: DBDep
) -> None:
    """Delete a knowledge space and all its associated data."""
    service = SpaceService(db)
    await service.delete_space(current_user.id, space_id)
