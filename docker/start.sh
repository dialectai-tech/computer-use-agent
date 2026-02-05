#!/bin/bash
set -e

echo "Starting Computer Use Automation Browser Container..."

# Wait for X server to be ready
echo "Waiting for X server..."
for i in {1..30}; do
    if xdpyinfo -display :1 >/dev/null 2>&1; then
        echo "X server is ready!"
        break
    fi
    sleep 1
done

echo "Container is ready for automation!"

# Keep container running
tail -f /dev/null
