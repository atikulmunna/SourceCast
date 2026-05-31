import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.models.knowledge_space import KnowledgeSpace
from app.schemas.spaces import SpaceCreate, SpaceOut, SpaceUpdate


class SpaceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_spaces(self, user_id: uuid.UUID) -> list[SpaceOut]:
        result = await self.db.execute(
            select(KnowledgeSpace)
            .where(KnowledgeSpace.user_id == user_id)
            .order_by(KnowledgeSpace.created_at)
        )
        spaces = result.scalars().all()
        return [SpaceOut.model_validate(s) for s in spaces]

    async def create_space(self, user_id: uuid.UUID, data: SpaceCreate) -> SpaceOut:
        # Check for name conflict
        existing = await self.db.execute(
            select(KnowledgeSpace).where(
                KnowledgeSpace.user_id == user_id,
                KnowledgeSpace.name == data.name,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException(f"A space named '{data.name}' already exists")

        space = KnowledgeSpace(
            user_id=user_id,
            name=data.name,
            description=data.description,
        )
        self.db.add(space)
        await self.db.commit()
        await self.db.refresh(space)
        return SpaceOut.model_validate(space)

    async def get_space(self, user_id: uuid.UUID, space_id: uuid.UUID) -> SpaceOut:
        space = await self._get_owned_space(user_id, space_id)
        return SpaceOut.model_validate(space)

    async def update_space(
        self, user_id: uuid.UUID, space_id: uuid.UUID, data: SpaceUpdate
    ) -> SpaceOut:
        space = await self._get_owned_space(user_id, space_id)

        if data.name is not None and data.name != space.name:
            # Check new name conflict
            existing = await self.db.execute(
                select(KnowledgeSpace).where(
                    KnowledgeSpace.user_id == user_id,
                    KnowledgeSpace.name == data.name,
                )
            )
            if existing.scalar_one_or_none():
                raise ConflictException(f"A space named '{data.name}' already exists")
            space.name = data.name

        if data.description is not None:
            space.description = data.description

        await self.db.commit()
        await self.db.refresh(space)
        return SpaceOut.model_validate(space)

    async def delete_space(self, user_id: uuid.UUID, space_id: uuid.UUID) -> None:
        space = await self._get_owned_space(user_id, space_id)
        await self.db.delete(space)
        await self.db.commit()

    async def _get_owned_space(
        self, user_id: uuid.UUID, space_id: uuid.UUID
    ) -> KnowledgeSpace:
        result = await self.db.execute(
            select(KnowledgeSpace).where(KnowledgeSpace.id == space_id)
        )
        space = result.scalar_one_or_none()
        if not space:
            raise NotFoundException("Knowledge space not found")
        if space.user_id != user_id:
            raise ForbiddenException("You do not own this space")
        return space
