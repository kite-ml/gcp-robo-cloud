"""gcp-robo-cloud: One command to train your robot on cloud GPUs.

Python API:
    import gcp_robo_cloud

    result = gcp_robo_cloud.launch(script="train.py", gpu="a100")
    print(result.output_dir, result.cost_usd)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gcp_robo_cloud._version import __version__
from gcp_robo_cloud.core.job import Job, JobState


@dataclass
class LaunchResult:
    """Result of a training launch."""

    job_id: str
    status: str
    output_dir: str
    cost_usd: float | None
    duration: str


def launch(
    script: str,
    gpu: str = "t4",
    args: str = "",
    spot: bool = True,
    max_duration: str = "4h",
    project_dir: str | None = None,
    output_dir: str | None = None,
    wait: bool = True,
    name: str = "",
) -> LaunchResult | Job:
    """Launch a training job on a GCP GPU instance.

    Args:
        script: Path to the training script.
        gpu: GPU type (t4, v100, a100, l4, h100).
        args: Arguments to pass to the training script.
        spot: Use spot instances for lower cost.
        max_duration: Maximum runtime (e.g., '2h', '30m').
        project_dir: Project directory (default: cwd).
        output_dir: Local directory for results.
        wait: If True, block until training completes. If False, return Job immediately.
        name: Optional job name.

    Returns:
        LaunchResult if wait=True, Job if wait=False.
    """
    from gcp_robo_cloud.core.config import load_config
    from gcp_robo_cloud.core.gpu_map import resolve_gpu
    from gcp_robo_cloud.docker.builder import build_image
    from gcp_robo_cloud.docker.detect import detect_project
    from gcp_robo_cloud.gcp.auth import resolve_project
    from gcp_robo_cloud.gcp.compute import create_instance, wait_for_instance_running
    from gcp_robo_cloud.gcp.pricing import estimate_cost
    from gcp_robo_cloud.gcp.registry import configure_docker_auth, ensure_repository, push_image
    from gcp_robo_cloud.gcp.storage import get_or_create_bucket
    from gcp_robo_cloud.monitor.watchdog import monitor_job
    from gcp_robo_cloud.sync.download import download_results
    from gcp_robo_cloud.sync.upload import upload_project

    proj_dir = Path(project_dir) if project_dir else Path.cwd()

    # Load config
    overrides = {
        "gpu": gpu,
        "spot": spot,
        "max_duration": max_duration,
        "script": script,
        "args": args,
    }
    cfg = load_config(project_dir=proj_dir, overrides=overrides)

    gpu_spec = resolve_gpu(cfg.gpu)
    credentials, project_id = resolve_project(cfg.project)

    # Create job
    job = Job(
        name=name or f"{cfg.gpu}-{script}",
        gpu=cfg.gpu,
        script=cfg.script,
        args=cfg.args,
        spot=cfg.spot,
        max_duration=cfg.max_duration,
        project_id=project_id,
    )
    job.instance_name = f"gcp-robo-cloud-{job.id}"

    # Detect and build
    info = detect_project(proj_dir)
    job.transition(JobState.BUILDING_IMAGE)
    job.save()

    local_tag = f"gcp-robo-cloud-{job.id}:latest"
    build_image(
        proj_dir,
        info,
        cfg.gpu,
        local_tag,
        cfg.docker.base_image,
        cfg.docker.python_version,
    )

    region = cfg.region
    configure_docker_auth(region)
    repo_path = ensure_repository(project_id, region)
    remote_uri = f"{repo_path}/{job.id}:latest"
    push_image(local_tag, remote_uri)
    job.image_uri = remote_uri

    # Upload
    job.transition(JobState.UPLOADING)
    job.save()
    bucket_name = get_or_create_bucket(credentials, project_id, cfg.gcs_bucket, region)
    job.gcs_bucket = bucket_name
    gcs_prefix, _ = upload_project(
        credentials,
        project_id,
        bucket_name,
        job.id,
        proj_dir,
        cfg.sync.exclude,
    )
    job.gcs_prefix = gcs_prefix

    # Provision
    job.transition(JobState.PROVISIONING)
    job.zone = gpu_spec.zones[0]
    job.save()

    gcs_input = f"gs://{bucket_name}/{gcs_prefix}"
    gcs_output = f"gs://{bucket_name}/jobs/{job.id}/output"

    create_instance(
        credentials,
        project_id,
        job.zone,
        job.instance_name,
        gpu_spec,
        job.image_uri,
        gcs_input,
        gcs_output,
        cfg.script,
        cfg.args,
        cfg.spot,
        cfg.max_duration,
    )

    wait_for_instance_running(credentials, project_id, job.zone, job.instance_name)
    job.transition(JobState.RUNNING)
    job.save()

    if not wait:
        return job

    # Monitor until complete
    monitor_job(credentials, job)

    # Download
    job.transition(JobState.DOWNLOADING)
    job.save()
    out_path = Path(output_dir) if output_dir else None
    result_dir, _ = download_results(credentials, project_id, bucket_name, job.id, out_path)

    job.transition(JobState.COMPLETED)
    est = estimate_cost(cfg.gpu, cfg.max_duration, cfg.spot)
    job.cost_usd = est.total_usd
    job.output_dir = str(result_dir)
    job.save()

    return LaunchResult(
        job_id=job.id,
        status="completed",
        output_dir=str(result_dir),
        cost_usd=est.total_usd,
        duration=cfg.max_duration,
    )


def status(job_id: str | None = None) -> Job | list[Job]:
    """Get status of a job or list all jobs.

    Args:
        job_id: Specific job ID, or None to list all.

    Returns:
        Single Job if job_id provided, list of Jobs otherwise.
    """
    if job_id:
        return Job.load(job_id)
    return Job.list_all()


def stop(job_id: str) -> None:
    """Stop a running job and delete the VM.

    Args:
        job_id: The job ID to stop.
    """
    from gcp_robo_cloud.gcp.auth import resolve_project
    from gcp_robo_cloud.monitor.watchdog import cleanup_job

    job = Job.load(job_id)
    if job.is_terminal:
        return

    credentials, _ = resolve_project(job.project_id)
    cleanup_job(credentials, job)
    try:
        job.transition(JobState.STOPPED)
    except ValueError:
        job.state = JobState.STOPPED
    job.save()


__all__ = ["__version__", "launch", "status", "stop", "LaunchResult"]
