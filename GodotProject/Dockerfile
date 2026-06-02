FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    GODOT_VERSION=4.6.3-stable

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}/Godot_v${GODOT_VERSION}_linux.x86_64.zip" \
    && unzip "Godot_v${GODOT_VERSION}_linux.x86_64.zip" \
    && mv "Godot_v${GODOT_VERSION}_linux.x86_64" /usr/local/bin/godot \
    && chmod +x /usr/local/bin/godot \
    && rm -f *.zip

WORKDIR /app/project
COPY . .

# Disable OpenXR auto-init (server has no XR hardware) and set server scene as main
RUN sed -i \
    -e 's/openxr\/enabled=true/openxr\/enabled=false/' \
    -e 's|run/main_scene=".*"|run/main_scene="res://scenes/server_main.tscn"|' \
    project.godot

EXPOSE 7777/udp
EXPOSE 7777/tcp

ENTRYPOINT ["/usr/local/bin/godot", "--headless", "--path", "/app/project"]
