import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

import structlog

from app.config import settings
from app.models.models import Endpoint
from app.schemas.check_results import CheckResultsResponse

logger = structlog.get_logger()


class Notifier:

    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_from = settings.smtp_from
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password


    async def send_notification(
        self,
        endpoint: Endpoint,
        check_result: CheckResultsResponse,
        status: str,
        service_name: str,
        responsible_list: List[str],
    ):
        if status == "DOWN":
            subject = f"[ALERT] {service_name} is DOWN"
            body = self.format_down_message(endpoint, check_result, service_name)
        else:
            subject = f"[RECOVERY] {service_name} is UP"
            body = self.format_up_message(endpoint, check_result, service_name)

        res = await self.send_email(responsible_list, subject, body)

        return res


    @staticmethod
    def format_down_message(
        endpoint: Endpoint, check_results: CheckResultsResponse, service_name: str
    ):
        time_str = check_results.checked_at.strftime("%Y-%m-%d %H:%M:%S UTC")

        if check_results.status_code:
            error_detail = f"HTTP Status Code: {check_results.status_code}"
        elif check_results.error_message:
            error_detail = f"Error: {check_results.error_message}"
        else:
            error_detail = "Service is not responding"

        return f"""Service Monitor Alert - Service DOWN

Service Name: {service_name}
Endpoint URL: {endpoint.url}
Detection Time: {time_str}
Status: DOWN
Details: {error_detail}
Response Time: {check_results.response_time_ms} ms

Please investigate the issue.

---
This is an automated message from Service Monitor.
"""


    @staticmethod
    def format_up_message(
        endpoint: Endpoint, check_results: CheckResultsResponse, service_name: str
    ):
        time_str = check_results.checked_at.strftime("%Y-%m-%d %H:%M:%S UTC")

        return f"""Service Monitor Alert - Service RECOVERED

Service Name: {service_name}
Endpoint URL: {endpoint.url}
Recovery Time: {time_str}
Status: UP
Response Time: {check_results.response_time_ms} ms

The service is back online.

---
This is an automated message from Service Monitor.
"""


    async def send_email(self, responsible_list: List[str], subject: str, body: str) -> str:
        emails: List[str] = []

        for to_email in responsible_list:
            try:
                msg = MIMEMultipart()
                msg["From"] = self.smtp_from
                msg["To"] = to_email
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain", "utf-8"))

                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.smtp_user and self.smtp_password:
                        server.starttls()
                        server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)

                logger.info("Email sent", to=to_email, subject=subject)
                emails.append(to_email)

            except Exception as e:
                logger.error("Email send failed", to=to_email, error=str(e))


        return f"Notification sent to: {', '.join(emails)}"
