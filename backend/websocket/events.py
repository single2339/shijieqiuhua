"""WebSocket event types for agent lifecycle and pipeline events."""

from enum import Enum


class WSEventType(str, Enum):
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    COLLECTION_STARTED = "collection_started"
    COLLECTION_PROGRESS = "collection_progress"
    COLLECTION_COMPLETED = "collection_completed"
    MERGE_COMPLETED = "merge_completed"
    REPORT_READY = "report_ready"
    TASK_STATUS = "task_status"
    ERROR = "error"
