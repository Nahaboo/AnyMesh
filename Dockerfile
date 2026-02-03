FROM python:3.12.10-slim

WORKDIR /app

# Dépendances système pour mesh processing + wget/unzip pour Instant Meshes
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Télécharger Instant Meshes Linux (binaire officiel AWS S3)
RUN mkdir -p /app/tools/instant-meshes && \
    wget -q https://instant-meshes.s3.eu-central-1.amazonaws.com/instant-meshes-linux.zip -O /tmp/im.zip && \
    unzip -q /tmp/im.zip -d /app/tools/instant-meshes && \
    chmod +x "/app/tools/instant-meshes/Instant Meshes" && \
    rm /tmp/im.zip

COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt

COPY src/ ./src/

RUN mkdir -p data/input data/output data/input_images \
    data/generated_meshes data/retopo data/segmented data/temp data/saved

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
