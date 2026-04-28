from fastapi import APIRouter, Depends, status

from app.api.deps import get_responsible_service
from app.services.responsible_service import ResponsibleService

router = APIRouter(prefix="/responsible", tags=["responsible"])


@router.delete("/{responsible_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_responsible(
    responsible_id: int,
    responsible: ResponsibleService = Depends(get_responsible_service),
) -> None:
    await responsible.delete(responsible_id)
