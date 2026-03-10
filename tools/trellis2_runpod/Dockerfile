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
# GPU arch for build-time CUDA compilation (no GPU visible during docker build)
# 8.0 = A100, 8.6 = A5000/RTX3090, 8.9 = RTX4090
ENV TORCH_CUDA_ARCH_LIST="8.0;8.6;8.9"

# System dependencies
RUN apt-get update && apt-get install -y \
    python3.10 python3.10-dev python3-pip python3.10-venv \
    git wget curl build-essential ninja-build \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 \
    libxrender-dev libgomp1 ffmpeg \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Make python3.10 the default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    python -m pip install --upgrade pip

WORKDIR /workspace

# Clone TRELLIS.2
RUN git clone --depth=1 --recursive https://github.com/microsoft/TRELLIS.2 /workspace/TRELLIS.2

# Fix: RMBG-2.0 BiRefNet uses device_map="auto" which puts tensors on meta device,
# causing Tensor.item() to fail during __init__. Force device_map=None.
RUN grep -rl 'device_map="auto"' /workspace/TRELLIS.2 | xargs -r sed -i 's/device_map="auto"/device_map=None/g'

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

# utils3d (pinned to same commit as setup.sh)
RUN pip install --no-cache-dir git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8

# flash-attn (long compile, keep separate layer)
RUN pip install --no-cache-dir psutil && \
    pip install --no-cache-dir flash-attn==2.7.3 --no-build-isolation

# nvdiffrast (needs --no-build-isolation for PyTorch, but needs recent setuptools first)
RUN pip install --no-cache-dir --upgrade setuptools>=68 wheel ninja && \
    pip install --no-cache-dir git+https://github.com/NVlabs/nvdiffrast.git@v0.4.0 --no-build-isolation

# CUDA extensions — installed directly (no conda needed)
# o-voxel: copied from the cloned repo (local dir)
RUN pip install --no-cache-dir /workspace/TRELLIS.2/o-voxel --no-build-isolation

# cumesh + flexgemm: cloned from GitHub
RUN git clone https://github.com/JeffreyXiang/CuMesh.git --recursive /tmp/CuMesh && \
    pip install --no-cache-dir /tmp/CuMesh --no-build-isolation && \
    rm -rf /tmp/CuMesh

RUN git clone https://github.com/JeffreyXiang/FlexGEMM.git --recursive /tmp/FlexGEMM && \
    pip install --no-cache-dir /tmp/FlexGEMM --no-build-isolation && \
    rm -rf /tmp/FlexGEMM

# Pre-download model weights into the image (baked at build time)
# Pass token via: --build-arg HF_TOKEN=hf_xxx (not stored in ENV, not exposed in final image)
ENV HF_HOME=/workspace/models

ARG HF_TOKEN
RUN python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download('microsoft/TRELLIS.2-4B', token='${HF_TOKEN}')"

RUN python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download('facebook/dinov3-vitl16-pretrain-lvd1689m', token='${HF_TOKEN}')"

RUN python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download('briaai/RMBG-2.0', token='${HF_TOKEN}')"

# Trigger transformers to download the custom code (birefnet.py) into transformers_modules cache
# then patch device_map="auto" -> device_map=None before it is ever executed at runtime
RUN python -c "\
import os; os.environ['HF_TOKEN']='${HF_TOKEN}'; \
from transformers import AutoConfig; \
AutoConfig.from_pretrained('briaai/RMBG-2.0', trust_remote_code=True, token='${HF_TOKEN}')" || true
RUN find /workspace/models/modules/transformers_modules/briaai -name '*.py' \
    -exec grep -l 'device_map="auto"' {} \; \
    | xargs -r sed -i 's/device_map="auto"/device_map=None/g' && \
    echo "Patched birefnet device_map"

# Also patch directly in the HF snapshot so transformers uses our patched version
# even if it re-downloads into transformers_modules from the local snapshot
RUN find /workspace/models/hub/models--briaai--RMBG-2.0 -name '*.py' \
    -exec grep -l 'device_map="auto"' {} \; \
    | xargs -r sed -i 's/device_map="auto"/device_map=None/g' && \
    echo "Patched birefnet in HF snapshot"

# trellis2 is not pip-installed — expose it via PYTHONPATH
ENV PYTHONPATH=/workspace/TRELLIS.2

# Copy handler
COPY tools/trellis2_runpod/handler.py /workspace/handler.py

# Entrypoint: re-patch birefnet at container start before any import
# This ensures the patch survives even if transformers re-copies from the snapshot
COPY tools/trellis2_runpod/entrypoint.sh /workspace/entrypoint.sh
RUN chmod +x /workspace/entrypoint.sh

CMD ["/workspace/entrypoint.sh"]
