from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Responsible
from app.repositories.base import BaseRepository


class ResponsibleRepository(BaseRepository[Responsible]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Responsible)

    async def list_by_service(self, service_id: int) -> list[Responsible]:
        query = (
            select(Responsible).where(Responsible.service_id == service_id).order_by(Responsible.id)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
