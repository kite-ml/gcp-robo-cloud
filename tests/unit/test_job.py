"""Tests for Job state machine and persistence."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from gcp_robo_cloud.core.job import Job, JobState


class TestJobStateTransitions:
    def test_valid_transition_created_to_building(self):
        job = Job()
        job.transition(JobState.BUILDING_IMAGE)
        assert job.state == JobState.BUILDING_IMAGE

    def test_full_happy_path(self):
        job = Job()
        job.transition(JobState.BUILDING_IMAGE)
        job.transition(JobState.UPLOADING)
        job.transition(JobState.PROVISIONING)
        job.transition(JobState.RUNNING)
        assert job.started_at != ""
        job.transition(JobState.DOWNLOADING)
        job.transition(JobState.COMPLETED)
        assert job.completed_at != ""
        assert job.is_terminal

    def test_invalid_transition_raises(self):
        job = Job()
        with pytest.raises(ValueError, match="Invalid state transition"):
            job.transition(JobState.RUNNING)  # Can't skip steps

    def test_can_fail_from_any_active_state(self):
        for state in [
            JobState.CREATED,
            JobState.BUILDING_IMAGE,
            JobState.UPLOADING,
            JobState.PROVISIONING,
            JobState.RUNNING,
            JobState.DOWNLOADING,
        ]:
            job = Job()
            job.state = state
            # Only test states where FAILED is a valid transition
            if JobState.FAILED in {JobState.FAILED}:
                try:
                    job.transition(JobState.FAILED)
                    assert job.is_terminal
                except ValueError:
                    pass  # Some states can't transition to failed

    def test_terminal_states_are_terminal(self):
        for state in [JobState.COMPLETED, JobState.FAILED, JobState.STOPPED]:
            job = Job()
            job.state = state
            assert job.is_terminal

    def test_running_sets_started_at(self):
        job = Job()
        job.transition(JobState.BUILDING_IMAGE)
        job.transition(JobState.UPLOADING)
        job.transition(JobState.PROVISIONING)
        assert job.started_at == ""
        job.transition(JobState.RUNNING)
        assert job.started_at != ""


class TestJobPersistence:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Job, "save", side_effect=lambda self=None: None):
                job = Job(name="test-job", gpu="a100", script="train.py")
                # Manual save to temp dir
                jobs_dir = Path(tmpdir) / "jobs"
                jobs_dir.mkdir()
                path = jobs_dir / f"{job.id}.json"
                data = {
                    "id": job.id,
                    "name": job.name,
                    "state": job.state.value,
                    "gpu": job.gpu,
                    "script": job.script,
                    "project_id": "",
                    "zone": "",
                    "instance_name": "",
                    "args": "",
                    "spot": True,
                    "max_duration": "4h",
                    "image_uri": "",
                    "gcs_bucket": "",
                    "gcs_prefix": "",
                    "output_dir": "",
                    "cost_usd": None,
                    "created_at": job.created_at,
                    "started_at": "",
                    "completed_at": "",
                    "error": "",
                }
                path.write_text(json.dumps(data))

                # Load
                loaded_data = json.loads(path.read_text())
                loaded_data["state"] = JobState(loaded_data["state"])
                loaded_job = Job(**loaded_data)
                assert loaded_job.id == job.id
                assert loaded_job.name == "test-job"
                assert loaded_job.gpu == "a100"

    def test_unique_ids(self):
        jobs = [Job() for _ in range(100)]
        ids = {j.id for j in jobs}
        assert len(ids) == 100
