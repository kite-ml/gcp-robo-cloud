"""Simple PyTorch training example for gcp-robo-cloud.

Usage:
    gcp-robo-cloud launch train.py --gpu t4
    gcp-robo-cloud launch train.py --gpu a100 --args "--epochs 50 --lr 0.001"
"""

import argparse
import os
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim


class SimpleNet(nn.Module):
    def __init__(self, input_dim=10, hidden_dim=64, output_dim=3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, x):
        return self.net(x)


def train(epochs: int, lr: float, device: str):
    print(f"Training on: {device}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    model = SimpleNet().to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    # Synthetic data (replace with your real dataset)
    x_train = torch.randn(1000, 10, device=device)
    y_train = torch.randn(1000, 3, device=device)

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        output = model(x_train)
        loss = criterion(output, y_train)
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 10 == 0:
            print(f"epoch {epoch+1}/{epochs} | loss: {loss.item():.4f}")

    # Save model to outputs/
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    torch.save(model.state_dict(), output_dir / "model.pth")
    print(f"\nModel saved to {output_dir / 'model.pth'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--lr", type=float, default=0.001)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    train(epochs=args.epochs, lr=args.lr, device=device)
