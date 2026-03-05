"""The `gcp-robo-cloud launch` command - main entry point for training jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from gcp_robo_cloud._version import __version__
from gcp_robo_cloud.core.config import load_config
from gcp_robo_cloud.core.gpu_map import VALID_GPU_ALIASES, resolve_gpu
from gcp_robo_cloud.core.job import Job, JobState
from gcp_robo_cloud.docker.builder import build_image
from gcp_robo_cloud.docker.detect import detect_project
from gcp_robo_cloud.gcp.auth import resolve_project
from gcp_robo_cloud.gcp.compute import create_instance, wait_for_instance_running
from gcp_robo_cloud.gcp.pricing import estimate_cost, format_estimate
from gcp_robo_cloud.gcp.registry import configure_docker_auth, ensure_repository, push_image
from gcp_robo_cloud.gcp.storage import get_or_create_bucket
from gcp_robo_cloud.monitor.logs import stream_logs
from gcp_robo_cloud.monitor.watchdog import cleanup_job, monitor_job
from gcp_robo_cloud.sync.download import download_results
from gcp_robo_cloud.sync.upload import upload_project

console = Console()


def launch(
    script: str = typer.Argument(..., help="Path to the training script."),
    gpu: str = typer.Option("t4", "--gpu", "-g", help=f"GPU type: {', '.join(VALID_GPU_ALIASES)}"),
    gpu_count: int = typer.Option(1, "--gpu-count", help="Number of GPUs."),
    args: str = typer.Option("", "--args", "-a", help="Arguments to pass to the training script."),
    spot: bool = typer.Option(True, "--spot/--no-spot", help="Use spot instances (cheaper)."),
    max_duration: str = typer.Option("4h", "--max-duration", "-d", help="Max runtime (e.g., 2h, 30m)."),
    name: str = typer.Option("", "--name", "-n", help="Job name."),
    project_dir: Optional[str] = typer.Option(None, "--dir", help="Project directory (default: cwd)."),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to gcp-robo-cloud.yaml."),
    async_mode: bool = typer.Option(False, "--async", help="Launch and return immediately."),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o", help="Local dir for results."),
) -> None:
    """Launch a training job on a GCP GPU instance."""

    console.print(f"\n[bold]gcp-robo-cloud[/bold] v{__version__}\n")

    # Resolve project directory
    proj_dir = Path(project_dir) if project_dir else Path.cwd()
    if not (proj_dir / script).exists():
        console.print(f"[red]Error:[/red] Script not found: {proj_dir / script}")
        raise typer.Exit(1)

    # Load config with CLI overrides
    overrides = {
        "gpu": gpu,
        "gpu_count": gpu_count,
        "spot": spot,
        "max_duration": max_duration,
        "script": script,
        "args": args,
    }
    cfg = load_config(project_dir=proj_dir, overrides=overrides)

    # Resolve GPU
    try:
        gpu_spec = resolve_gpu(cfg.gpu)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Show cost estimate
    est = estimate_cost(cfg.gpu, cfg.max_duration, cfg.spot)
    console.print(Panel(format_estimate(est), title="Cost Estimate", border_style="dim"))

    # Authenticate
    console.print("[1/6] Authenticating with GCP...")
    credentials, project_id = resolve_project(cfg.project)
    console.print(f"  Project: {project_id}")

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

    try:
        # Detect project
        console.print("[2/6] Detecting dependencies...")
        info = detect_project(proj_dir)
        if info.frameworks:
            console.print(f"  Detected frameworks: {', '.join(info.frameworks)}")
        if info.has_requirements_txt:
            console.print("  Found requirements.txt")
        elif info.has_pyproject_toml:
            console.print("  Found pyproject.toml")

        # Build Docker image
        console.print("[3/6] Building Docker image...")
        job.transition(JobState.BUILDING_IMAGE)
        job.save()

        local_tag = f"gcp-robo-cloud-{job.id}:latest"
        build_image(
            project_dir=proj_dir,
            info=info,
            gpu=cfg.gpu,
            tag=local_tag,
            base_image=cfg.docker.base_image,
            python_version=cfg.docker.python_version,
            extra_system_packages=cfg.docker.system_packages,
        )

        # Push to Artifact Registry
        region = cfg.region
        configure_docker_auth(region)
        repo_path = ensure_repository(project_id, region)
        remote_uri = f"{repo_path}/{job.id}:latest"
        push_image(local_tag, remote_uri)
        job.image_uri = remote_uri

        # Upload project files
        console.print("[4/6] Uploading project files...")
        job.transition(JobState.UPLOADING)
        job.save()

        bucket_name = get_or_create_bucket(credentials, project_id, cfg.gcs_bucket, region)
        job.gcs_bucket = bucket_name
        gcs_prefix, file_count = upload_project(
            credentials=credentials,
            project_id=project_id,
            bucket_name=bucket_name,
            job_id=job.id,
            project_dir=proj_dir,
            extra_excludes=cfg.sync.exclude,
        )
        job.gcs_prefix = gcs_prefix
        console.print(f"  Uploaded {file_count} files to gs://{bucket_name}/{gcs_prefix}/")

        # Provision VM
        console.print(f"[5/6] Provisioning {gpu_spec.machine_type} with {cfg.gpu.upper()} in {gpu_spec.zones[0]}...")
        job.transition(JobState.PROVISIONING)
        job.zone = gpu_spec.zones[0]
        job.save()

        gcs_input = f"gs://{bucket_name}/{gcs_prefix}"
        gcs_output = f"gs://{bucket_name}/jobs/{job.id}/output"

        create_instance(
            credentials=credentials,
            project_id=project_id,
            zone=job.zone,
            instance_name=job.instance_name,
            gpu_spec=gpu_spec,
            image_uri=job.image_uri,
            gcs_input_path=gcs_input,
            gcs_output_path=gcs_output,
            script=cfg.script,
            args=cfg.args,
            spot=cfg.spot,
            max_duration=cfg.max_duration,
        )

        console.print(f"  Instance: {job.instance_name}")

        # Wait for running
        if wait_for_instance_running(credentials, project_id, job.zone, job.instance_name):
            job.transition(JobState.RUNNING)
            job.save()
            console.print("  Instance running. Starting training...")
        else:
            raise RuntimeError("Instance failed to start")

        if async_mode:
            console.print(f"\n  Job launched: {job.id}")
            console.print(f"  Check status: gcp-robo-cloud status {job.id}")
            console.print(f"  View logs:    gcp-robo-cloud logs {job.id}")
            return

        # Stream logs and monitor
        console.print("[6/6] Training running. Streaming logs:\n")
        console.print("  " + "─" * 50)

        stream_logs(
            credentials=credentials,
            project_id=project_id,
            zone=job.zone,
            instance_name=job.instance_name,
        )

        console.print("  " + "─" * 50)

        # Download results
        job.transition(JobState.DOWNLOADING)
        job.save()
        console.print("\nDownloading results...")

        out_path = Path(output_dir) if output_dir else None
        result_dir, result_count = download_results(
            credentials=credentials,
            project_id=project_id,
            bucket_name=bucket_name,
            job_id=job.id,
            output_dir=out_path,
        )

        if result_count > 0:
            console.print(f"  Downloaded {result_count} files to {result_dir}")
        else:
            console.print("  No output files found.")

        # Mark complete
        job.transition(JobState.COMPLETED)
        job.output_dir = str(result_dir)
        job.cost_usd = est.total_usd
        job.save()

        pricing_type = "spot" if cfg.spot else "on-demand"
        console.print(
            f"\n[green]Training completed.[/green] "
            f"Estimated cost: ${est.total_usd:.2f} ({pricing_type} {cfg.gpu.upper()})"
        )

    except KeyboardInterrupt:
        console.print("\n\nInterrupted. Cleaning up...")
        cleanup_job(credentials, job)
        job.transition(JobState.STOPPED)
        job.save()
        console.print(f"  Job {job.id} stopped. VM deleted.")

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        job.error = str(e)
        if not job.is_terminal:
            try:
                job.transition(JobState.FAILED)
            except ValueError:
                job.state = JobState.FAILED
        job.save()
        # Try to clean up VM
        try:
            cleanup_job(credentials, job)
        except Exception:
            pass
        raise typer.Exit(1)
