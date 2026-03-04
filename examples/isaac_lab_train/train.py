"""Isaac Lab training example.

Train a robot locomotion policy using Isaac Lab's RL workflow.
Requires NVIDIA Isaac Lab (installed in the base image).

Usage:
    gcp-robocloud launch train.py --gpu a100 --args "--task Isaac-Cartpole-v0 --num_envs 4096"
"""

import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=str, default="Isaac-Cartpole-v0")
    parser.add_argument("--num_envs", type=int, default=4096)
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--max_iterations", type=int, default=1000)
    args = parser.parse_args()

    # Isaac Lab imports (available in the Isaac Lab Docker image)
    from omni.isaac.lab.app import AppLauncher

    app_launcher = AppLauncher(headless=args.headless)
    simulation_app = app_launcher.app

    from omni.isaac.lab_tasks.utils import parse_env_cfg
    from omni.isaac.lab_tasks.utils.wrappers.rsl_rl import RslRlVecEnvWrapper

    # This is a skeleton - actual training would use RSL-RL or RL-Games
    print(f"Task: {args.task}")
    print(f"Num envs: {args.num_envs}")
    print(f"Max iterations: {args.max_iterations}")
    print(f"Headless: {args.headless}")
    print("\nNote: Full Isaac Lab training requires the NVIDIA Isaac Sim runtime.")
    print("Configure with: docker.base_image: nvcr.io/nvidia/isaac-lab:4.5.0")

    simulation_app.close()


if __name__ == "__main__":
    main()
