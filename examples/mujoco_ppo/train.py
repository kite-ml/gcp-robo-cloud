"""MuJoCo + Stable Baselines3 PPO training example.

Train a locomotion policy using PPO on a MuJoCo environment.

Usage:
    gcp-robocloud launch train.py --gpu t4
    gcp-robocloud launch train.py --gpu a100 --args "--env Ant-v4 --timesteps 1000000"
"""

import argparse
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import CheckpointCallback


def train(env_id: str, total_timesteps: int, n_envs: int):
    print(f"Training PPO on {env_id}")
    print(f"Total timesteps: {total_timesteps}")
    print(f"Parallel envs: {n_envs}")

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    # Create vectorized environments
    vec_env = make_vec_env(env_id, n_envs=n_envs)

    # Checkpoint callback
    checkpoint_callback = CheckpointCallback(
        save_freq=max(total_timesteps // 10, 1000),
        save_path=str(output_dir / "checkpoints"),
        name_prefix="ppo",
    )

    # Train
    model = PPO(
        "MlpPolicy",
        vec_env,
        verbose=1,
        device="auto",
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
    )

    model.learn(
        total_timesteps=total_timesteps,
        callback=checkpoint_callback,
    )

    # Save final model
    model.save(str(output_dir / "ppo_final"))
    print(f"\nModel saved to {output_dir / 'ppo_final.zip'}")

    vec_env.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=str, default="HalfCheetah-v4")
    parser.add_argument("--timesteps", type=int, default=500_000)
    parser.add_argument("--n-envs", type=int, default=8)
    args = parser.parse_args()

    train(env_id=args.env, total_timesteps=args.timesteps, n_envs=args.n_envs)
