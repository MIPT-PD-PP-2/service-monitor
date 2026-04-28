from typing import Any, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository:
    def __init__(self, db: AsyncSession, model: Type[Any]):
        self.db = db
        self.model = model

    async def get_by_id(self, obj_id: Any) -> Optional[Any]:
        query = select(self.model).where(self.model.id == obj_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_all(self) -> List[Any]:
        query = select(self.model).order_by(self.model.id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, data: dict) -> Any:
        obj = self.model(**data)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj_id: Any, data: dict) -> Optional[Any]:
        obj = await self.get_by_id(obj_id)
        if not obj:
            return None
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj_id: Any) -> bool:
        obj = await self.get_by_id(obj_id)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True
