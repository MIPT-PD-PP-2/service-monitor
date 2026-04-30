import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.models import SlaConfig
from app.repositories.services import ServiceRepository
from app.repositories.sla_config import SlaConfigRepository
from app.schemas.sla_config import SlaConfigRequest

logger = structlog.get_logger()


class SlaConfigService:
    def __init__(self, db: AsyncSession):
        self.repo = SlaConfigRepository(db)
        self.service_repo = ServiceRepository(db)

    async def create_for_service(self, service_id: int, data: SlaConfigRequest) -> SlaConfig:
        await self._ensure_service_exists(service_id)
        sla_config = await self.repo.create(
            {"service_id": service_id, "target_percent": data.target_percent}
        )
        logger.info(
            "sla_config_created",
            sla_config_id=sla_config.id,
            service_id=service_id,
            target_percent=sla_config.target_percent
        )
        return sla_config

    async def get_by_service_id(self, service_id: int) -> SlaConfig:
      config = await self.repo.get_by_service_id(service_id)
      if not config:
          raise NotFoundError(detail="SLA config not found for this service")
      return config

    async def _ensure_service_exists(self, service_id: int) -> None:
        svc = await self.service_repo.get_by_id(service_id)
        if not svc:
            raise NotFoundError(detail="Service not found")

