from typing import Dict, List

from fastapi import APIRouter, Depends, status

from app.api.deps import get_endpoint_service, get_service_service
from app.schemas.endpoints import EndpointRequest, EndpointResponse
from app.schemas.services import ServiceRequest, ServiceResponse
from app.services.endpoint_service import EndpointService
from app.services.service_service import ServiceService

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    data: ServiceRequest,
    service: ServiceService = Depends(get_service_service),
) -> Dict:
    return await service.create(data)


@router.get("", response_model=List[ServiceResponse])
async def list_services(
    service: ServiceService = Depends(get_service_service),
) -> List[Dict]:
    return await service.list_all()


@router.post(
    "/{service_id}/endpoints",
    response_model=EndpointResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_endpoint(
    service_id: int,
    data: EndpointRequest,
    endpoint: EndpointService = Depends(get_endpoint_service),
) -> Dict:
    return await endpoint.create_for_service(service_id, data)


@router.get("/{service_id}/endpoints", response_model=List[EndpointResponse])
async def list_endpoints(
    service_id: int,
    endpoint: EndpointService = Depends(get_endpoint_service),
) -> List[Dict]:
    return await endpoint.list_for_service(service_id)


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: int,
    service: ServiceService = Depends(get_service_service),
) -> Dict:
    return await service.get(service_id)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: int,
    service: ServiceService = Depends(get_service_service),
) -> None:
    await service.delete(service_id)
