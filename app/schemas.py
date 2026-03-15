from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, HttpUrl, Field

from app.models import MonitorStatus, NotificationType, IncidentSeverity


class NotificationChannelCreate(BaseModel):
    channel_type: NotificationType
    webhook_url: Optional[str] = None
    email_address: Optional[str] = None
    is_active: bool = True


class NotificationChannelResponse(BaseModel):
    id: int
    monitor_id: int
    channel_type: NotificationType
    webhook_url: Optional[str] = None
    email_address: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MonitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=2048)
    method: str = Field(default="GET", pattern="^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$")
    headers: Optional[str] = "{}"
    body: Optional[str] = None
    expected_status_code: int = Field(default=200, ge=100, le=599)
    check_interval: int = Field(default=60, ge=10, le=86400)
    timeout: int = Field(default=30, ge=1, le=120)
    notification_channels: Optional[List[NotificationChannelCreate]] = None


class MonitorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = Field(None, min_length=1, max_length=2048)
    method: Optional[str] = Field(None, pattern="^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$")
    headers: Optional[str] = None
    body: Optional[str] = None
    expected_status_code: Optional[int] = Field(None, ge=100, le=599)
    check_interval: Optional[int] = Field(None, ge=10, le=86400)
    timeout: Optional[int] = Field(None, ge=1, le=120)
    is_active: Optional[bool] = None


class MonitorResponse(BaseModel):
    id: int
    name: str
    url: str
    method: str
    expected_status_code: int
    check_interval: int
    timeout: int
    is_active: bool
    status: MonitorStatus
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    notification_channels: List[NotificationChannelResponse] = []

    class Config:
        from_attributes = True


class HealthCheckResponse(BaseModel):
    id: int
    monitor_id: int
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    is_healthy: bool
    error_message: Optional[str] = None
    checked_at: datetime

    class Config:
        from_attributes = True


class IncidentResponse(BaseModel):
    id: int
    monitor_id: int
    title: str
    description: Optional[str] = None
    severity: IncidentSeverity
    started_at: datetime
    resolved_at: Optional[datetime] = None
    is_resolved: bool
    consecutive_failures: int
    created_at: datetime

    class Config:
        from_attributes = True


class IncidentUpdate(BaseModel):
    is_resolved: Optional[bool] = None
    severity: Optional[IncidentSeverity] = None
    description: Optional[str] = None


class DashboardStats(BaseModel):
    total_monitors: int
    monitors_up: int
    monitors_down: int
    monitors_degraded: int
    overall_uptime_percentage: float
    active_incidents: int
    avg_response_time_ms: float


class MonitorDetailedStats(BaseModel):
    monitor_id: int
    monitor_name: str
    current_status: MonitorStatus
    uptime_percentage: float
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p95_response_time_ms: float
    total_checks: int
    successful_checks: int
    recent_checks: List[HealthCheckResponse] = []
    active_incidents: List[IncidentResponse] = []


class ResponseTimeEntry(BaseModel):
    checked_at: datetime
    response_time_ms: Optional[float] = None
    is_healthy: bool


class UptimeReport(BaseModel):
    monitor_id: int
    monitor_name: str
    period_start: datetime
    period_end: datetime
    uptime_percentage: float
    total_checks: int
    successful_checks: int
    failed_checks: int
    avg_response_time_ms: float
    incidents_count: int


class BulkMonitorCreate(BaseModel):
    monitors: List[MonitorCreate]


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int
