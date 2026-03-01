# Jetson 设备采集脚本

## 文件说明
- `install_node_exporter.sh`：安装并启动 node_exporter，监听 `:9100`
- `tegrastats_exporter.py`：从 `tegrastats` 解析 GPU/温度等，暴露 Prometheus 指标
- `install_tegrastats_exporter.sh`：部署并以 `systemd` 启动 `tegrastats_exporter.py`，监听 `:9200`

## 使用
1. 将本目录同步到 Jetson（或在服务器通过 SSH 拷贝）
2. 以 root 运行：
   - `bash install_node_exporter.sh`
   - `bash install_tegrastats_exporter.sh`
3. 验证：
   - `curl http://<jetson-ip>:9100/metrics`
   - `curl http://<jetson-ip>:9200/metrics`

