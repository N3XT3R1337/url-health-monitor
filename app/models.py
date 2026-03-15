import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    Enum, ForeignKey, Text, Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


class MonitorStatus(str, enum.Enum):
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class NotificationType(str, enum.Enum):
    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"


class IncidentSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(2048), nullable=False)
    method = Column(String(10), default="GET")
    headers = Column(Text, default="{}")
    body = Column(Text, nullable=True)
    expected_status_code = Column(Integer, default=200)
    check_interval = Column(Integer, default=60)
    timeout = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    status = Column(Enum(MonitorStatus), default=MonitorStatus.UNKNOWN)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    checks = relationship("HealthCheck", back_populates="monitor", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="monitor", cascade="all, delete-orphan")
    notification_channels = relationship("NotificationChannel", back_populates="monitor", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_monitor_active_status", "is_active", "status"),
    )


class HealthCheck(Base):
    __tablename__ = "health_checks"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    is_healthy = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)

    monitor = relationship("Monitor", back_populates="checks")

    __table_args__ = (
        Index("idx_healthcheck_monitor_time", "monitor_id", "checked_at"),
    )


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(Enum(IncidentSeverity), default=IncidentSeverity.MEDIUM)
    started_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    is_resolved = Column(Boolean, default=False)
    consecutive_failures = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    monitor = relationship("Monitor", back_populates="incidents")

    __table_args__ = (
        Index("idx_incident_monitor_resolved", "monitor_id", "is_resolved"),
    )


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False)
    channel_type = Column(Enum(NotificationType), nullable=False)
    webhook_url = Column(String(2048), nullable=True)
    email_address = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    monitor = relationship("Monitor", back_populates="notification_channels")


class ResponseTimeStats(Base):
    __tablename__ = "response_time_stats"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    avg_response_time_ms = Column(Float, default=0.0)
    min_response_time_ms = Column(Float, default=0.0)
    max_response_time_ms = Column(Float, default=0.0)
    p95_response_time_ms = Column(Float, default=0.0)
    total_checks = Column(Integer, default=0)
    successful_checks = Column(Integer, default=0)
    uptime_percentage = Column(Float, default=0.0)

    __table_args__ = (
        Index("idx_stats_monitor_period", "monitor_id", "period_start"),
    )
