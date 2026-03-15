import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Monitor, Incident, NotificationChannel, NotificationType
from app.config import settings


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def notify_incident_opened(self, incident: Incident, monitor: Monitor):
        channels = (
            self.db.query(NotificationChannel)
            .filter(
                NotificationChannel.monitor_id == monitor.id,
                NotificationChannel.is_active == True,
            )
            .all()
        )

        for channel in channels:
            if channel.channel_type == NotificationType.SLACK:
                self._send_slack_notification(channel, incident, monitor, is_resolved=False)
            elif channel.channel_type == NotificationType.DISCORD:
                self._send_discord_notification(channel, incident, monitor, is_resolved=False)
            elif channel.channel_type == NotificationType.EMAIL:
                self._send_email_notification(channel, incident, monitor, is_resolved=False)

        if not channels:
            if settings.SLACK_WEBHOOK_URL:
                self._send_slack_webhook(
                    settings.SLACK_WEBHOOK_URL,
                    self._format_slack_message(incident, monitor, is_resolved=False),
                )
            if settings.DISCORD_WEBHOOK_URL:
                self._send_discord_webhook(
                    settings.DISCORD_WEBHOOK_URL,
                    self._format_discord_message(incident, monitor, is_resolved=False),
                )

    def notify_incident_resolved(self, incident: Incident, monitor: Monitor):
        channels = (
            self.db.query(NotificationChannel)
            .filter(
                NotificationChannel.monitor_id == monitor.id,
                NotificationChannel.is_active == True,
            )
            .all()
        )

        for channel in channels:
            if channel.channel_type == NotificationType.SLACK:
                self._send_slack_notification(channel, incident, monitor, is_resolved=True)
            elif channel.channel_type == NotificationType.DISCORD:
                self._send_discord_notification(channel, incident, monitor, is_resolved=True)
            elif channel.channel_type == NotificationType.EMAIL:
                self._send_email_notification(channel, incident, monitor, is_resolved=True)

    def _send_slack_notification(
        self,
        channel: NotificationChannel,
        incident: Incident,
        monitor: Monitor,
        is_resolved: bool,
    ):
        webhook_url = channel.webhook_url or settings.SLACK_WEBHOOK_URL
        if not webhook_url:
            return
        payload = self._format_slack_message(incident, monitor, is_resolved)
        self._send_slack_webhook(webhook_url, payload)

    def _send_discord_notification(
        self,
        channel: NotificationChannel,
        incident: Incident,
        monitor: Monitor,
        is_resolved: bool,
    ):
        webhook_url = channel.webhook_url or settings.DISCORD_WEBHOOK_URL
        if not webhook_url:
            return
        payload = self._format_discord_message(incident, monitor, is_resolved)
        self._send_discord_webhook(webhook_url, payload)

    def _send_email_notification(
        self,
        channel: NotificationChannel,
        incident: Incident,
        monitor: Monitor,
        is_resolved: bool,
    ):
        email = channel.email_address
        if not email or not settings.SMTP_HOST:
            return
        subject, body = self._format_email(incident, monitor, is_resolved)
        self._send_email(email, subject, body)

    def _format_slack_message(self, incident: Incident, monitor: Monitor, is_resolved: bool) -> dict:
        if is_resolved:
            color = "#36a64f"
            title = f":white_check_mark: Resolved: {monitor.name}"
            text = f"The incident '{incident.title}' has been resolved."
        else:
            color = "#ff0000"
            title = f":rotating_light: Alert: {monitor.name}"
            text = f"Incident detected: {incident.title}\nSeverity: {incident.severity.value}\nURL: {monitor.url}"

        return {
            "attachments": [
                {
                    "color": color,
                    "title": title,
                    "text": text,
                    "fields": [
                        {"title": "Monitor", "value": monitor.name, "short": True},
                        {"title": "URL", "value": monitor.url, "short": True},
                        {"title": "Severity", "value": incident.severity.value, "short": True},
                        {"title": "Status", "value": "Resolved" if is_resolved else "Active", "short": True},
                    ],
                    "ts": int(incident.started_at.timestamp()),
                }
            ]
        }

    def _format_discord_message(self, incident: Incident, monitor: Monitor, is_resolved: bool) -> dict:
        if is_resolved:
            color = 3586116
            title = f"Resolved: {monitor.name}"
            description = f"The incident '{incident.title}' has been resolved."
        else:
            color = 16711680
            title = f"Alert: {monitor.name}"
            description = f"Incident detected: {incident.title}"

        return {
            "embeds": [
                {
                    "title": title,
                    "description": description,
                    "color": color,
                    "fields": [
                        {"name": "Monitor", "value": monitor.name, "inline": True},
                        {"name": "URL", "value": monitor.url, "inline": True},
                        {"name": "Severity", "value": incident.severity.value, "inline": True},
                        {"name": "Status", "value": "Resolved" if is_resolved else "Active", "inline": True},
                    ],
                }
            ]
        }

    def _format_email(self, incident: Incident, monitor: Monitor, is_resolved: bool) -> tuple:
        if is_resolved:
            subject = f"[RESOLVED] {monitor.name} - {incident.title}"
            body = (
                f"The incident has been resolved.\n\n"
                f"Monitor: {monitor.name}\n"
                f"URL: {monitor.url}\n"
                f"Incident: {incident.title}\n"
                f"Resolved at: {incident.resolved_at}\n"
            )
        else:
            subject = f"[ALERT] {monitor.name} - {incident.title}"
            body = (
                f"A new incident has been detected.\n\n"
                f"Monitor: {monitor.name}\n"
                f"URL: {monitor.url}\n"
                f"Incident: {incident.title}\n"
                f"Severity: {incident.severity.value}\n"
                f"Description: {incident.description or 'N/A'}\n"
                f"Started at: {incident.started_at}\n"
            )
        return subject, body

    def _send_slack_webhook(self, url: str, payload: dict):
        try:
            with httpx.Client(timeout=10) as client:
                client.post(url, json=payload)
        except Exception:
            pass

    def _send_discord_webhook(self, url: str, payload: dict):
        try:
            with httpx.Client(timeout=10) as client:
                client.post(url, json=payload)
        except Exception:
            pass

    def _send_email(self, to_address: str, subject: str, body: str):
        if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASSWORD]):
            return
        try:
            msg = MIMEMultipart()
            msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
            msg["To"] = to_address
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
        except Exception:
            pass

    def add_channel(
        self,
        monitor_id: int,
        channel_type: NotificationType,
        webhook_url: Optional[str] = None,
        email_address: Optional[str] = None,
    ) -> NotificationChannel:
        channel = NotificationChannel(
            monitor_id=monitor_id,
            channel_type=channel_type,
            webhook_url=webhook_url,
            email_address=email_address,
        )
        self.db.add(channel)
        self.db.commit()
        self.db.refresh(channel)
        return channel

    def remove_channel(self, channel_id: int) -> bool:
        channel = (
            self.db.query(NotificationChannel)
            .filter(NotificationChannel.id == channel_id)
            .first()
        )
        if not channel:
            return False
        self.db.delete(channel)
        self.db.commit()
        return True

    def toggle_channel(self, channel_id: int) -> Optional[NotificationChannel]:
        channel = (
            self.db.query(NotificationChannel)
            .filter(NotificationChannel.id == channel_id)
            .first()
        )
        if not channel:
            return None
        channel.is_active = not channel.is_active
        self.db.commit()
        self.db.refresh(channel)
        return channel
