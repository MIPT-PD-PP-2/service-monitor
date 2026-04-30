from typing import Any

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    get_endpoint_service,
    get_responsible_service,
    get_service_service,
    get_sla_config_service,
)
from app.schemas.endpoints import EndpointRequest, EndpointResponse
from app.schemas.responsible import ResponsibleRequest, ResponsibleResponse
from app.schemas.services import ServiceRequest, ServiceResponse
from app.schemas.sla_config import SlaConfigRequest, SlaConfigResponse
from app.services.endpoint_service import EndpointService
from app.services.responsible_service import ResponsibleService
from app.services.service_service import ServiceService
from app.services.sla_config_service import SlaConfigService

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    data: ServiceRequest,
    service: ServiceService = Depends(get_service_service),
) -> Any:
    return await service.create(data)


@router.get("", response_model=list[ServiceResponse])
async def list_services(
    service: ServiceService = Depends(get_service_service),
) -> Any:
    return await service.list_all()


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: int,
    service: ServiceService = Depends(get_service_service),
) -> Any:
    return await service.get(service_id)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: int,
    service: ServiceService = Depends(get_service_service),
) -> None:
    await service.delete(service_id)


@router.post(
    "/{service_id}/endpoints",
    response_model=EndpointResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_endpoint(
    service_id: int,
    data: EndpointRequest,
    endpoint: EndpointService = Depends(get_endpoint_service),
) -> Any:
    return await endpoint.create_for_service(service_id, data)


@router.get("/{service_id}/endpoints", response_model=list[EndpointResponse])
async def list_endpoints(
    service_id: int,
    endpoint: EndpointService = Depends(get_endpoint_service),
) -> Any:
    return await endpoint.list_for_service(service_id)


@router.post(
    "/{service_id}/responsible",
    response_model=ResponsibleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_responsible(
    service_id: int,
    data: ResponsibleRequest,
    responsible: ResponsibleService = Depends(get_responsible_service),
) -> Any:
    return await responsible.create_for_service(service_id, data)


@router.get("/{service_id}/responsible", response_model=list[ResponsibleResponse])
async def list_responsible(
    service_id: int,
    responsible: ResponsibleService = Depends(get_responsible_service),
) -> Any:
    return await responsible.list_for_service(service_id)


@router.get(
    "/{service_id}/config",
    response_model=SlaConfigResponse
)
async def get_sla_config(
    service_id: int,
    sla_config: SlaConfigService = Depends(get_sla_config_service)
) -> Any:
    return await sla_config.get_by_service_id(service_id)


@router.post(
    "/{service_id}/sla-config",
    response_model=SlaConfigResponse,
    status_code=status.HTTP_201_CREATED
)
async def set_sla_config(
    service_id: int,
    data: SlaConfigRequest,
    sla_config: SlaConfigService = Depends(get_sla_config_service)
) -> Any:
    return await sla_config.create_for_service(service_id, data)
