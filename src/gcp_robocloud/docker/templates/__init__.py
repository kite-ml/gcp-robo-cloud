"""Jinja2 Dockerfile templates for different project types."""

CUDA_TEMPLATE = """\
FROM {{ base_image }}

ENV DEBIAN_FRONTEND=noninteractive

# System packages
RUN apt-get update && apt-get install -y --no-install-recommends \\
    python{{ python_version }} \\
    python3-pip \\
    python{{ python_version }}-venv \\
    git \\
    curl \\
    wget \\
{% for pkg in system_packages %}
    {{ pkg }} \\
{% endfor %}
    && rm -rf /var/lib/apt/lists/* \\
    && ln -sf /usr/bin/python{{ python_version }} /usr/bin/python

WORKDIR /workspace

{% if install_method == 'requirements' %}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
{% elif install_method == 'pyproject' %}
COPY pyproject.toml .
{% if has_src_dir %}
COPY src/ src/
{% endif %}
RUN pip install --no-cache-dir .
{% endif %}

# Training code is synced via GCS at runtime, not baked in
"""

ROS2_TEMPLATE = """\
FROM {{ base_image }}

ENV DEBIAN_FRONTEND=noninteractive

# Additional system packages
RUN apt-get update && apt-get install -y --no-install-recommends \\
    python3-pip \\
{% for pkg in system_packages %}
    {{ pkg }} \\
{% endfor %}
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

{% if install_method == 'requirements' %}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
{% elif install_method == 'pyproject' %}
COPY pyproject.toml .
RUN pip install --no-cache-dir .
{% endif %}

# Source ROS 2 setup in entrypoint
SHELL ["/bin/bash", "-c"]
RUN echo "source /opt/ros/$ROS_DISTRO/setup.bash" >> ~/.bashrc
"""
