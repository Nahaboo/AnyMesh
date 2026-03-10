#!/bin/bash
# Re-patch birefnet.py at container start.
# transformers with trust_remote_code=True may copy birefnet.py from the HF snapshot
# into transformers_modules at runtime. We patch both locations to be safe.
find /workspace/models -name '*.py' \
    -exec grep -l 'device_map="auto"' {} \; \
    | xargs -r sed -i 's/device_map="auto"/device_map=None/g'
echo "[entrypoint] birefnet device_map patch applied"

exec python /workspace/handler.py
