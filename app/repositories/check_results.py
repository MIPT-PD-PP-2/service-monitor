from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CheckResult
from app.repositories.base import BaseRepository


class CheckResultsRepository(BaseRepository[CheckResult]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, CheckResult)

    async def list_by_endpoint(self, endpoint_id: int) -> list[CheckResult]:
        query = select(CheckResult).where(CheckResult.endpoint_id == endpoint_id).order_by(CheckResult.id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
