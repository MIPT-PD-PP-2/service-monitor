import structlog

logger = structlog.get_logger()


class CheckEngine:
    """Движок проверки эндпоинтов (заглушка)"""

    async def check_endpoint(self, endpoint_id: int) -> None:
        logger.info("check_endpoint", endpoint_id=endpoint_id)
