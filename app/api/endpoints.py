from typing import Dict

from fastapi import APIRouter, Depends, status

from app.api.deps import get_endpoint_service
from app.schemas.endpoints import EndpointResponse, EndpointUpdateRequest
from app.services.endpoint_service import EndpointService

router = APIRouter(prefix="/endpoints", tags=["endpoints"])


@router.patch("/{endpoint_id}", response_model=EndpointResponse)
async def update_endpoint(
    endpoint_id: int,
    data: EndpointUpdateRequest,
    endpoint: EndpointService = Depends(get_endpoint_service),
) -> Dict:
    return await endpoint.update(endpoint_id, data)


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(
    endpoint_id: int,
    endpoint: EndpointService = Depends(get_endpoint_service),
) -> None:
    await endpoint.delete(endpoint_id)
