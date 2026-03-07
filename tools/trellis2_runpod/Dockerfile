# TRELLIS.2 RunPod Serverless Worker
# Base: CUDA 12.4 + Ubuntu 22.04 + Python 3.10 (required by TRELLIS.2)
# GPU: A5000 (24 GB) minimum, A100 recommended
#
# Build:
#   docker build -f tools/trellis2_runpod/Dockerfile -t youruser/trellis2-worker:latest .
# Push:
#   docker push youruser/trellis2-worker:latest

FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda
ENV PATH="${CUDA_HOME}/bin:${PATH}"
ENV LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}"

# System dependencies
RUN apt-get update && apt-get install -y \
    python3.10 python3.10-dev python3-pip python3.10-venv \
    git wget curl build-essential ninja-build \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 \
    libxrender-dev libgomp1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Make python3.10 the default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    python -m pip install --upgrade pip

WORKDIR /workspace

# Clone TRELLIS.2
RUN git clone --depth=1 https://github.com/microsoft/TRELLIS.2 /workspace/TRELLIS.2

WORKDIR /workspace/TRELLIS.2

# Core Python deps (before CUDA extensions to cache them separately)
RUN pip install --no-cache-dir \
    torch==2.6.0+cu124 torchvision==0.21.0+cu124 \
    --index-url https://download.pytorch.org/whl/cu124

RUN pip install --no-cache-dir \
    imageio imageio-ffmpeg tqdm easydict \
    opencv-python-headless ninja trimesh \
    transformers pillow kornia timm \
    tensorboard pandas lpips zstandard \
    runpod huggingface_hub

# utils3d (required by TRELLIS.2, not on PyPI)
RUN pip install --no-cache-dir git+https://github.com/EasternJournalist/utils3d.git

# flash-attn (long compile, keep separate layer)
RUN pip install --no-cache-dir flash-attn==2.7.3 --no-build-isolation

# nvdiffrast
RUN pip install --no-cache-dir git+https://github.com/NVlabs/nvdiffrast.git@v0.4.0

# Build TRELLIS.2 custom CUDA extensions
RUN bash setup.sh --o-voxel --flexgemm --cumesh

# Pre-download model weights into a cache dir (baked into image)
# To skip baking weights (use RunPod network volume instead), comment out this block
# and set HF_HOME env var to point to the network volume mount path at runtime.
RUN python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download('microsoft/TRELLIS.2-4B', local_dir='/workspace/models/TRELLIS.2-4B')"

ENV HF_HOME=/workspace/models
ENV TRANSFORMERS_CACHE=/workspace/models

# Copy handler
COPY tools/trellis2_runpod/handler.py /workspace/handler.py

CMD ["python", "/workspace/handler.py"]
