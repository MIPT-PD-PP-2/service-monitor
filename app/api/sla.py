from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from app.db.database import get_db
import time
import traceback

router = APIRouter(prefix="/sla", tags=["sla"])


@router.get("/test/{service_id}")
async def sla_test(service_id: int, db=Depends(get_db)):
    try:
        service_result = await db.execute(text("SELECT id FROM services WHERE id = :sid"), {"sid": service_id})
        service = service_result.first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")

        start = time.time()
        sql = text("""
                   SELECT COUNT(cr.id)                                            AS total_checks,
                          AVG(cr.response_time_ms)                                AS avg_response_time_ms,
                          SUM(CASE WHEN cr.is_available = TRUE THEN 1 ELSE 0 END) AS success_count
                   FROM check_results cr
                            JOIN endpoints e ON e.id = cr.endpoint_id
                   WHERE e.service_id = :sid
                   """)
        result_proxy = await db.execute(sql, {"sid": service_id})
        result = result_proxy.first()
        elapsed_ms = int((time.time() - start) * 1000)

        total = result.total_checks if result and result.total_checks is not None else 0
        avg_time = float(result.avg_response_time_ms) if result and result.avg_response_time_ms is not None else 0.0
        success = result.success_count if result and result.success_count is not None else 0

        return {
            "query_time_ms": elapsed_ms,
            "service_id": service_id,
            "stats": {
                "total_checks": total,
                "avg_response_time_ms": avg_time,
                "success_count": success
            }
        }
    except Exception as e:
        print("=" * 50)
        print(f"ERROR in /sla/test/{service_id}: {str(e)}")
        traceback.print_exc()
        print("=" * 50)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")