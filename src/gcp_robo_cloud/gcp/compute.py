"""GCP Compute Engine VM provisioning.

Creates, monitors, and deletes VMs with GPU accelerators using
Container-Optimized OS for fast boot times.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from google.cloud import compute_v1
from rich.console import Console

from gcp_robo_cloud.core.gpu_map import GPUSpec

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

console = Console()

# Container-Optimized OS image for fast Docker + GPU support
COS_IMAGE_PROJECT = "cos-cloud"
COS_IMAGE_FAMILY = "cos-113-lts"

# Disk size in GB
BOOT_DISK_SIZE_GB = 100


def _build_startup_script(
    image_uri: str,
    gcs_input_path: str,
    gcs_output_path: str,
    script: str,
    args: str,
    max_duration: str,
) -> str:
    """Generate the VM startup script that runs the training job."""
    return f"""#!/bin/bash
set -e

echo "=== gcp-robo-cloud startup ==="

# Install GPU drivers
echo "Installing GPU drivers..."
cos-extensions install gpu 2>&1 || true
mount --bind /var/lib/nvidia /var/lib/nvidia
echo "/var/lib/nvidia/lib64" > /etc/ld.so.conf.d/nvidia.conf
ldconfig

# Configure Docker for GPU access
echo "Configuring Docker..."
cat > /etc/docker/daemon.json <<'DOCKER_EOF'
{{
    "default-runtime": "nvidia",
    "runtimes": {{
        "nvidia": {{
            "path": "/var/lib/nvidia/bin/nvidia-container-runtime",
            "runtimeArgs": []
        }}
    }}
}}
DOCKER_EOF
systemctl restart docker

# Authenticate for GCS and Artifact Registry
echo "Authenticating..."
docker-credential-gcr configure-docker --registries us-central1-docker.pkg.dev,us-docker.pkg.dev

# Download project files from GCS
echo "Downloading project files..."
mkdir -p /workspace/input /workspace/output
gsutil -m cp -r {gcs_input_path}/* /workspace/input/ 2>&1 || true

# Pull the Docker image
echo "Pulling Docker image: {image_uri}"
docker pull {image_uri}

# Set up max duration watchdog
MAX_DURATION="{max_duration}"
if [ -n "$MAX_DURATION" ]; then
    # Parse duration (e.g., "4h", "30m", "2h30m")
    SECONDS_LIMIT=$(python3 -c "
import re
s = '{max_duration}'
total = 0
for val, unit in re.findall(r'(\\d+)([hms])', s):
    if unit == 'h': total += int(val) * 3600
    elif unit == 'm': total += int(val) * 60
    elif unit == 's': total += int(val)
print(total)
" 2>/dev/null || echo "14400")
    echo "Max duration: $SECONDS_LIMIT seconds"
    (sleep $SECONDS_LIMIT && echo "Max duration reached, shutting down..." \
        && kill -TERM $$ 2>/dev/null) &
    WATCHDOG_PID=$!
fi

# Run training
echo "=== Starting training ==="
TRAIN_ARGS="{args}"
docker run --rm \\
    --gpus all \\
    -v /workspace/input:/workspace \\
    -v /workspace/output:/workspace/outputs \\
    -e NVIDIA_VISIBLE_DEVICES=all \\
    {image_uri} \\
    python /workspace/{script} $TRAIN_ARGS
EXIT_CODE=$?
echo "=== Training finished with exit code: $EXIT_CODE ==="

# Kill watchdog if it exists
[ -n "$WATCHDOG_PID" ] && kill $WATCHDOG_PID 2>/dev/null || true

# Upload results to GCS
echo "Uploading results..."
gsutil -m cp -r /workspace/output/* {gcs_output_path}/ 2>&1 || true

echo "=== gcp-robo-cloud complete ==="

# Self-terminate
echo "Self-terminating VM..."
META_URL="http://metadata.google.internal/computeMetadata/v1/instance"
ZONE=$(curl -s -H "Metadata-Flavor: Google" $META_URL/zone | cut -d'/' -f4)
INSTANCE=$(curl -s -H "Metadata-Flavor: Google" $META_URL/name)
gcloud compute instances delete "$INSTANCE" --zone="$ZONE" --quiet
"""


def create_instance(
    credentials: Credentials,
    project_id: str,
    zone: str,
    instance_name: str,
    gpu_spec: GPUSpec,
    image_uri: str,
    gcs_input_path: str,
    gcs_output_path: str,
    script: str,
    args: str,
    spot: bool,
    max_duration: str,
) -> compute_v1.Instance:
    """Create a VM instance with GPU accelerator.

    Args:
        credentials: GCP credentials.
        project_id: GCP project ID.
        zone: GCP zone (e.g., 'us-central1-a').
        instance_name: Name for the VM.
        gpu_spec: GPU specification from gpu_map.
        image_uri: Docker image URI to pull and run.
        gcs_input_path: GCS path for input files.
        gcs_output_path: GCS path for output files.
        script: Training script filename.
        args: Arguments to pass to the script.
        spot: Whether to use spot/preemptible pricing.
        max_duration: Maximum runtime (e.g., '4h').

    Returns:
        The created Instance resource.
    """
    client = compute_v1.InstancesClient(credentials=credentials)

    startup_script = _build_startup_script(
        image_uri=image_uri,
        gcs_input_path=gcs_input_path,
        gcs_output_path=gcs_output_path,
        script=script,
        args=args,
        max_duration=max_duration,
    )

    # Boot disk from Container-Optimized OS
    boot_disk = compute_v1.AttachedDisk(
        auto_delete=True,
        boot=True,
        initialize_params=compute_v1.AttachedDiskInitializeParams(
            disk_size_gb=BOOT_DISK_SIZE_GB,
            source_image=f"projects/{COS_IMAGE_PROJECT}/global/images/family/{COS_IMAGE_FAMILY}",
        ),
    )

    # Network with external IP for GCS/registry access
    network_interface = compute_v1.NetworkInterface(
        access_configs=[
            compute_v1.AccessConfig(
                name="External NAT",
                type_="ONE_TO_ONE_NAT",
            )
        ],
    )

    # GPU accelerator config (only for N1 machines that need it)
    guest_accelerators = []
    if gpu_spec.machine_type.startswith("n1-"):
        guest_accelerators.append(
            compute_v1.AcceleratorConfig(
                accelerator_type=f"zones/{zone}/acceleratorTypes/{gpu_spec.accelerator_type}",
                accelerator_count=gpu_spec.accelerator_count,
            )
        )

    # Scheduling (spot/preemptible + GPU requirements)
    scheduling = compute_v1.Scheduling(on_host_maintenance="TERMINATE")
    if spot:
        scheduling.provisioning_model = "SPOT"
        scheduling.instance_termination_action = "DELETE"

    # Service account with full cloud-platform scope
    service_account = compute_v1.ServiceAccount(
        email="default",
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    instance = compute_v1.Instance(
        name=instance_name,
        machine_type=f"zones/{zone}/machineTypes/{gpu_spec.machine_type}",
        disks=[boot_disk],
        network_interfaces=[network_interface],
        guest_accelerators=guest_accelerators if guest_accelerators else None,
        scheduling=scheduling,
        service_accounts=[service_account],
        metadata=compute_v1.Metadata(
            items=[
                compute_v1.Items(key="startup-script", value=startup_script),
            ]
        ),
    )

    operation = client.insert(
        project=project_id,
        zone=zone,
        instance_resource=instance,
    )
    operation.result()  # type: ignore[no-untyped-call]  # Wait for creation

    return client.get(project=project_id, zone=zone, instance=instance_name)


def delete_instance(
    credentials: Credentials,
    project_id: str,
    zone: str,
    instance_name: str,
) -> None:
    """Delete a VM instance."""
    client = compute_v1.InstancesClient(credentials=credentials)
    try:
        operation = client.delete(
            project=project_id,
            zone=zone,
            instance=instance_name,
        )
        operation.result()  # type: ignore[no-untyped-call]
    except Exception:
        pass  # Instance may already be deleted (self-terminate)


def get_instance_status(
    credentials: Credentials,
    project_id: str,
    zone: str,
    instance_name: str,
) -> str | None:
    """Get VM instance status (RUNNING, TERMINATED, etc.)."""
    client = compute_v1.InstancesClient(credentials=credentials)
    try:
        instance = client.get(project=project_id, zone=zone, instance=instance_name)
        return instance.status
    except Exception:
        return None


def get_serial_output(
    credentials: Credentials,
    project_id: str,
    zone: str,
    instance_name: str,
    start: int = 0,
) -> tuple[str, int]:
    """Get serial port output from a VM for log streaming.

    Returns:
        Tuple of (output_text, next_offset).
    """
    client = compute_v1.InstancesClient(credentials=credentials)
    try:
        request = compute_v1.GetSerialPortOutputInstanceRequest(
            project=project_id,
            zone=zone,
            instance=instance_name,
            start=start,
        )
        response = client.get_serial_port_output(request=request)
        return response.contents, response.next_
    except Exception:
        return "", start


def wait_for_instance_running(
    credentials: Credentials,
    project_id: str,
    zone: str,
    instance_name: str,
    timeout: int = 300,
    poll_interval: int = 5,
) -> bool:
    """Wait for a VM to reach RUNNING status.

    Returns:
        True if instance is running, False if timed out.
    """
    elapsed = 0
    while elapsed < timeout:
        status = get_instance_status(credentials, project_id, zone, instance_name)
        if status == "RUNNING":
            return True
        if status in ("TERMINATED", "STOPPED", "SUSPENDED"):
            return False
        time.sleep(poll_interval)
        elapsed += poll_interval
    return False
