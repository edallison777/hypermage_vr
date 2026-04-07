#!/usr/bin/env bash
# Start the UnrealBridge and (optionally) an ngrok tunnel.
# Run this on the dev PC when you want agents to control UE5.
#
# Usage:
#   ./start.sh           # bridge only, localhost:8765
#   ./start.sh --ngrok   # bridge + ngrok tunnel, updates SSM automatically

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8765
REGION="eu-west-1"
SSM_KEY="/hypermage/unreal-bridge-url"

cd "$SCRIPT_DIR"

# Install deps if needed
if ! python -c "import fastapi" 2>/dev/null; then
  echo "[bridge] Installing Python deps..."
  pip install -r requirements.txt
fi

if [[ "${1:-}" == "--ngrok" ]]; then
  if ! command -v ngrok &>/dev/null; then
    echo "[bridge] ERROR: ngrok not found. Install from https://ngrok.com/download"
    exit 1
  fi

  echo "[bridge] Starting ngrok tunnel on port $PORT..."
  ngrok http "$PORT" --log=stdout &
  NGROK_PID=$!
  sleep 3

  # Get the public URL from ngrok API
  NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python -c \
    "import sys,json; t=json.load(sys.stdin)['tunnels']; \
     print([x['public_url'] for x in t if x['proto']=='https'][0])" 2>/dev/null || echo "")

  if [[ -n "$NGROK_URL" ]]; then
    echo "[bridge] Tunnel: $NGROK_URL"
    echo "[bridge] Updating SSM $SSM_KEY..."
    aws ssm put-parameter \
      --name "$SSM_KEY" \
      --value "$NGROK_URL" \
      --type String \
      --overwrite \
      --region "$REGION"
    echo "[bridge] SSM updated — agents can now reach UE5 at $NGROK_URL"
  else
    echo "[bridge] WARNING: could not auto-detect ngrok URL. Update SSM manually."
  fi
fi

echo "[bridge] Starting UnrealBridge on port $PORT..."
python bridge.py --host 0.0.0.0 --port "$PORT"
