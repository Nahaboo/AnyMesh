#!/bin/bash
set -e

if [ -z "$HF_HOME" ]; then
    echo "[entrypoint] ERROR: HF_HOME is not set. Mount the network volume and set HF_HOME=/runpod-volume/models."
    exit 1
fi

if [ -z "$HF_TOKEN" ]; then
    echo "[entrypoint] ERROR: HF_TOKEN is not set."
    exit 1
fi

MODELS=(
    "microsoft/TRELLIS.2-4B"
    "facebook/dinov3-vitl16-pretrain-lvd1689m"
    "briaai/RMBG-2.0"
)

for MODEL in "${MODELS[@]}"; do
    CACHE_DIR="$HF_HOME/hub/models--$(echo $MODEL | tr '/' '--')/snapshots"
    if [ -d "$CACHE_DIR" ]; then
        echo "[entrypoint] Model cached: $MODEL"
    else
        echo "[entrypoint] Downloading: $MODEL (first cold start, may take several minutes)"
        python -c "
from huggingface_hub import snapshot_download
import os
snapshot_download('$MODEL', token=os.environ['HF_TOKEN'])
"
        echo "[entrypoint] Download complete: $MODEL"
    fi
done

# Patch birefnet.py: .item() fails on meta tensors, .tolist() works
find "$HF_HOME" -name 'birefnet.py' \
    -exec sed -i \
    's/dpr = \[x\.item() for x in torch\.linspace(0, drop_path_rate, sum(depths))\]/dpr = torch.linspace(0, drop_path_rate, sum(depths)).tolist()/g' \
    {} \;
echo "[entrypoint] birefnet .item() -> .tolist() patch applied"

# Patch device_map: transformers may extract birefnet.py at runtime with device_map="auto"
find "$HF_HOME" -name '*.py' \
    -exec grep -l 'device_map="auto"' {} \; \
    | xargs -r sed -i 's/device_map="auto"/device_map=None/g'
echo "[entrypoint] birefnet device_map patch applied"

exec python /workspace/handler.py
