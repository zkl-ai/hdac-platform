#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update -y || true
sudo apt-get install -y python3 python3-pip || true
sudo -H pip3 install -U jetson-stats || true

sudo systemctl restart jtop.service || true

sudo pip3 install -U prometheus_client || true

SCRIPT_PATH=/opt/jtop_exporter
sudo mkdir -p "$SCRIPT_PATH"
if [ -n "${1:-}" ] && [ -f "$1" ]; then
  sudo cp "$1" "$SCRIPT_PATH/jtop_exporter.py"
elif [ -f "/data/workspace/hdap-platform/infra/jetson/jtop_exporter.py" ]; then
  sudo cp "/data/workspace/hdap-platform/infra/jetson/jtop_exporter.py" "$SCRIPT_PATH/jtop_exporter.py"
else
  echo "jtop_exporter.py not found" >&2
  exit 1
fi

sudo tee /etc/systemd/system/jtop-exporter.service >/dev/null <<SERVICE
[Unit]
Description=Jetson jtop Prometheus exporter
After=network.target

[Service]
User=root
ExecStart=/usr/bin/python3 /opt/jtop_exporter/jtop_exporter.py
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable jtop-exporter || true
sudo systemctl restart jtop-exporter || sudo systemctl start jtop-exporter
echo "jtop exporter installed and running on :9200"

