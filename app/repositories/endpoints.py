from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Endpoint
from app.repositories.base import BaseRepository


class EndpointRepository(BaseRepository[Endpoint]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Endpoint)

    async def list_by_service(self, service_id: int) -> list[Endpoint]:
        query = select(Endpoint).where(Endpoint.service_id == service_id).order_by(Endpoint.id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # Получение списка активных эндпоинтов
    async def get_active_endpoints(self) -> list[Endpoint]:
        query = select(Endpoint).where(Endpoint.is_active == True).order_by(Endpoint.id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
