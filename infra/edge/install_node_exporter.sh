#!/usr/bin/env bash
set -euo pipefail

if command -v node_exporter >/dev/null 2>&1 || [ -f /usr/local/bin/node_exporter ]; then
  echo "node_exporter binary exists, skip download"
else
  ARCH=$(uname -m)
  if [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
    REL=linux-arm64
  else
    REL=linux-amd64
  fi
  VER=1.8.2
  TMP=$(mktemp -d)
  cd "$TMP"
  wget -q "https://github.com/prometheus/node_exporter/releases/download/v$VER/node_exporter-$VER.$REL.tar.gz" -O ne.tgz
  tar -xzf ne.tgz
  sudo cp "node_exporter-$VER.$REL/node_exporter" /usr/local/bin/
fi
sudo useradd -r -s /sbin/nologin nodeexp || true
sudo tee /etc/systemd/system/node_exporter.service >/dev/null <<'SERVICE'
[Unit]
Description=Prometheus Node Exporter
After=network.target

[Service]
User=nodeexp
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:9100
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE
sudo systemctl daemon-reload
sudo systemctl enable node_exporter || true
sudo systemctl restart node_exporter || sudo systemctl start node_exporter
echo "node_exporter installed and running on :9100"
