# Blender FBX/OBJ → glTF converter
# Based on official Blender image. Runs headless and exits when conversion is done.
# ECS Fargate task — zero idle cost (task terminates on completion).

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV BLENDER_VERSION=4.2.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget xz-utils libglib2.0-0 libsm6 libxrender1 libxext6 libgl1 \
    python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Blender portable
RUN wget -q "https://download.blender.org/release/Blender4.2/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
    -O /tmp/blender.tar.xz \
    && tar -xf /tmp/blender.tar.xz -C /opt \
    && mv /opt/blender-${BLENDER_VERSION}-linux-x64 /opt/blender \
    && ln -s /opt/blender/blender /usr/local/bin/blender \
    && rm /tmp/blender.tar.xz

# Install Python AWS SDK (for S3/DynamoDB access)
RUN pip3 install --no-cache-dir boto3

COPY convert.py /app/convert.py

# Entrypoint: blender reads ASSET_ID, S3_KEY, S3_BUCKET from env
CMD ["blender", "--background", "--python", "/app/convert.py"]
