from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import SlaConfig
from app.repositories.base import BaseRepository


class SlaConfigRepository(BaseRepository[SlaConfig]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, SlaConfig)

    async def get_by_service_id(self, service_id: int) -> Optional[SlaConfig]:
        query = (select(self.model).where(self.model.service_id == service_id))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
