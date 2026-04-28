from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.endpoint_service import EndpointService
from app.services.service_service import ServiceService


async def get_service_service(db: AsyncSession = Depends(get_db)) -> ServiceService:
    return ServiceService(db)


async def get_endpoint_service(db: AsyncSession = Depends(get_db)) -> EndpointService:
    return EndpointService(db)
