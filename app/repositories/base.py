from typing import Any, Generic, Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    def __init__(self, db: AsyncSession, model: type) -> None:
        self.db = db
        self.model = model

    async def get_by_id(self, obj_id: int) -> Any:
        query = select(self.model).where(self.model.id == obj_id)  # type: ignore[attr-defined,var-annotated]
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_all(self) -> list[Any]:
        query = select(self.model).order_by(self.model.id)  # type: ignore[attr-defined,var-annotated]
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, data: dict) -> Any:
        obj = self.model(**data)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj_id: int, data: dict) -> Optional[Any]:
        obj = await self.get_by_id(obj_id)
        if not obj:
            return None
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj_id: int) -> bool:
        obj = await self.get_by_id(obj_id)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True
