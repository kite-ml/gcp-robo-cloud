"""Job dataclass and lifecycle state machine.

A Job represents a single training run on a GCP VM. It tracks state through:
    CREATED -> BUILDING_IMAGE -> UPLOADING -> PROVISIONING -> RUNNING
        -> DOWNLOADING -> COMPLETED | FAILED | STOPPED
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

JOBS_DIR = Path.home() / ".gcp-robo-cloud" / "jobs"


class JobState(str, Enum):
    CREATED = "created"
    BUILDING_IMAGE = "building_image"
    UPLOADING = "uploading"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


_VALID_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.CREATED: {JobState.BUILDING_IMAGE, JobState.FAILED},
    JobState.BUILDING_IMAGE: {JobState.UPLOADING, JobState.FAILED},
    JobState.UPLOADING: {JobState.PROVISIONING, JobState.FAILED},
    JobState.PROVISIONING: {JobState.RUNNING, JobState.FAILED, JobState.STOPPED},
    JobState.RUNNING: {JobState.DOWNLOADING, JobState.FAILED, JobState.STOPPED},
    JobState.DOWNLOADING: {JobState.COMPLETED, JobState.FAILED},
    JobState.COMPLETED: set(),
    JobState.FAILED: set(),
    JobState.STOPPED: set(),
}


@dataclass
class Job:
    """Represents a single training job on GCP."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    state: JobState = JobState.CREATED

    # GCP resources
    project_id: str = ""
    zone: str = ""
    instance_name: str = ""

    # Training config
    gpu: str = ""
    script: str = ""
    args: str = ""
    spot: bool = True
    max_duration: str = "4h"

    # Docker
    image_uri: str = ""

    # Storage
    gcs_bucket: str = ""
    gcs_prefix: str = ""

    # Results
    output_dir: str = ""
    cost_usd: float | None = None

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str = ""
    completed_at: str = ""

    # Error info
    error: str = ""

    def transition(self, new_state: JobState) -> None:
        """Transition to a new state, enforcing valid transitions."""
        valid = _VALID_TRANSITIONS.get(self.state, set())
        if new_state not in valid:
            raise ValueError(f"Invalid state transition: {self.state.value} -> {new_state.value}")
        self.state = new_state
        if new_state == JobState.RUNNING:
            self.started_at = datetime.now(timezone.utc).isoformat()
        elif new_state in (JobState.COMPLETED, JobState.FAILED, JobState.STOPPED):
            self.completed_at = datetime.now(timezone.utc).isoformat()

    @property
    def is_terminal(self) -> bool:
        return self.state in (JobState.COMPLETED, JobState.FAILED, JobState.STOPPED)

    def save(self) -> Path:
        """Persist job state to disk."""
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        path = JOBS_DIR / f"{self.id}.json"
        data = asdict(self)
        data["state"] = self.state.value
        path.write_text(json.dumps(data, indent=2))
        return path

    @classmethod
    def load(cls, job_id: str) -> Job:
        """Load a job from disk by ID."""
        path = JOBS_DIR / f"{job_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Job '{job_id}' not found")
        data = json.loads(path.read_text())
        data["state"] = JobState(data["state"])
        return cls(**data)

    @classmethod
    def list_all(cls) -> list[Job]:
        """List all saved jobs, most recent first."""
        if not JOBS_DIR.exists():
            return []
        jobs = []
        for path in JOBS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                data["state"] = JobState(data["state"])
                jobs.append(cls(**data))
            except (json.JSONDecodeError, KeyError):
                continue
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs
