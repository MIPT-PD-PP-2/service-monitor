from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.endpoint_service import EndpointService
from app.services.responsible_service import ResponsibleService
from app.services.service_service import ServiceService
from app.services.sla_config_service import SlaConfigService


async def get_service_service(db: AsyncSession = Depends(get_db)) -> ServiceService:
    return ServiceService(db)


async def get_endpoint_service(db: AsyncSession = Depends(get_db)) -> EndpointService:
    return EndpointService(db)


async def get_responsible_service(db: AsyncSession = Depends(get_db)) -> ResponsibleService:
    return ResponsibleService(db)

async def get_sla_config_service(db: AsyncSession = Depends(get_db)) -> SlaConfigService:
    return SlaConfigService(db)
