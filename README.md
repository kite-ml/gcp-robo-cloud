# gcp-robocloud

**One command to train your robot on cloud GPUs.**

gcp-robocloud makes it dead simple for robotics developers to run training jobs on GCP GPU instances. No Kubernetes, no Terraform, no infrastructure expertise needed.

```bash
pip install gcp-robocloud
gcp-robocloud launch train.py --gpu a100
```

That's it. Your training script runs on a cloud A100, and results are downloaded when it finishes.

## Why?

Training robotics policies (RL, imitation learning, sim-to-real) requires GPU compute that most developers don't have locally. Getting cloud GPUs currently means wrestling with VM provisioning, Docker, networking, and cost management. gcp-robocloud handles all of that.

## Features

- **One-command launch** - `gcp-robocloud launch train.py --gpu a100`
- **Auto-containerization** - Detects your dependencies, builds and pushes a Docker image automatically
- **Framework agnostic** - Works with PyTorch, Isaac Lab, MuJoCo, PyBullet, ROS 2, or any Python project
- **Cost-conscious** - Spot instances by default (60-91% cheaper), auto-shutdown after training, cost estimates
- **File sync** - Uploads your code, downloads results automatically via GCS
- **Simple auth** - Uses your existing `gcloud` credentials
- **Python API** - Use programmatically: `gcp_robocloud.launch(script="train.py", gpu="a100")`

## Quick Start

### 1. Install

```bash
pip install gcp-robocloud
```

### 2. Authenticate (if you haven't already)

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 3. First-time setup

```bash
gcp-robocloud config --init
```

This enables the required GCP APIs (Compute Engine, Cloud Storage, Artifact Registry).

### 4. Launch training

```bash
cd my-robotics-project/
gcp-robocloud launch train.py --gpu a100
```

## Available GPUs

| GPU | VRAM | Spot $/hr | On-demand $/hr | Best for |
|-----|------|-----------|----------------|----------|
| `t4` | 16 GB | $0.11 | $0.35 | Prototyping, small models |
| `l4` | 24 GB | $0.22 | $0.72 | Inference, medium training |
| `v100` | 16 GB | $0.74 | $2.48 | General training |
| `a100` | 40 GB | $1.10 | $3.67 | Large-scale training |
| `a100-80gb` | 80 GB | $1.47 | $4.90 | Very large models |
| `h100` | 80 GB | $3.54 | $11.81 | Maximum performance |

## CLI Reference

```bash
# Launch training
gcp-robocloud launch train.py --gpu a100
gcp-robocloud launch train.py --gpu t4 --no-spot           # On-demand instance
gcp-robocloud launch train.py --gpu a100 --args "--epochs 100 --lr 0.001"
gcp-robocloud launch train.py --gpu l4 --max-duration 2h   # Auto-stop after 2 hours
gcp-robocloud launch train.py --gpu a100 --async            # Don't wait for completion

# Job management
gcp-robocloud status                   # List all jobs
gcp-robocloud status <job_id>          # Job details
gcp-robocloud stop <job_id>            # Stop and delete VM

# Cost estimation
gcp-robocloud estimate --gpu a100 --duration 2h
gcp-robocloud estimate --all --duration 4h     # Compare all GPUs

# Configuration
gcp-robocloud config --init            # First-time setup
gcp-robocloud config --show            # Show current config
gcp-robocloud config --set gpu=a100    # Set defaults
```

## Python API

```python
import gcp_robocloud

# Blocking - waits for training to complete
result = gcp_robocloud.launch(
    script="train.py",
    gpu="a100",
    args="--epochs 100",
    spot=True,
    max_duration="2h",
)
print(result.output_dir)   # Path to downloaded results
print(result.cost_usd)     # Estimated cost

# Non-blocking - returns immediately
job = gcp_robocloud.launch(script="train.py", gpu="a100", wait=False)
print(job.id)              # Job ID for tracking

# Check status later
status = gcp_robocloud.status(job.id)
print(status.state)

# Stop a running job
gcp_robocloud.stop(job.id)
```

## Configuration

Create a `gcp-robocloud.yaml` in your project root for persistent settings:

```yaml
project: my-gcp-project
region: us-central1
gpu: a100
spot: true
max_duration: 4h

docker:
  base_image: nvidia/cuda:12.4.1-runtime-ubuntu22.04
  python_version: "3.11"
  system_packages: [libgl1-mesa-glx, libegl1]

sync:
  exclude: [data/raw/, "*.pth", __pycache__/]
  output_patterns: ["outputs/**", "checkpoints/*.pth"]

script: train.py
args: "--num-envs 4096 --headless"
```

## How It Works

1. **Detects dependencies** - Finds `requirements.txt` or `pyproject.toml`
2. **Builds Docker image** - Generates a Dockerfile, builds locally, pushes to Artifact Registry
3. **Uploads code** - Syncs project files to GCS (training code is not baked into the image for fast iteration)
4. **Provisions VM** - Creates a spot GPU instance with Container-Optimized OS
5. **Runs training** - Pulls the image, downloads code, executes your script
6. **Streams logs** - Shows training output in your terminal
7. **Downloads results** - Copies artifacts (models, logs) to your local machine
8. **Cleans up** - VM self-terminates after training to stop billing

## Custom Dockerfiles

If you need more control, place a `Dockerfile` in your project root. gcp-robocloud will use it directly instead of auto-generating one.

Or specify a base image in your config:

```yaml
docker:
  base_image: nvcr.io/nvidia/isaac-lab:4.5.0
```

## File Sync

By default, gcp-robocloud uploads your project files (excluding `.git`, `__pycache__`, `.venv`, etc.) and downloads everything from `outputs/` after training.

Create a `.gcp-robocloud-ignore` file (gitignore syntax) to customize:

```
# Don't upload large data files
data/raw/
*.hdf5
datasets/

# Don't upload pre-trained models
*.pth
*.onnx
```

## Requirements

- Python 3.10+
- Docker (for building images locally)
- `gcloud` CLI (for authentication)
- A GCP project with billing enabled

## License

Apache 2.0
