bash -lc 'set -euo pipefail
PROM_DIR=/data/workspace/hdap-platform/infra/prometheus
mkdir -p "$PROM_DIR/bin" "$PROM_DIR/data"
cd "$PROM_DIR/bin"
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then REL_ARCH=linux-amd64; elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then REL_ARCH=linux-arm64; else REL_ARCH=linux-amd64; fi
VER=$(curl -s https://api.github.com/repos/prometheus/prometheus/releases/latest | grep tag_name | cut -d '"' -f4 | tr -d v)
URL="https://github.com/prometheus/prometheus/releases/download/v$VER/prometheus-$VER.$REL_ARCH.tar.gz"
wget -q "$URL" -O prometheus.tgz
 tar -xzf prometheus.tgz --strip-components=1
rm -f prometheus.tgz
# launch
CMD="./prometheus --config.file=$PROM_DIR/prometheus.yml --storage.tsdb.path=$PROM_DIR/data --web.listen-address=:9090 --storage.tsdb.retention.time=90d"
nohup bash -lc "$CMD" > "$PROM_DIR/prometheus.out" 2>&1 &
echo PROMETHEUS_STARTED:$(date +%s)
'