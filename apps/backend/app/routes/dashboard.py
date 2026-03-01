# app/routes/analytics.py
from flask import Blueprint, request, jsonify
import random

dashboard_bp = Blueprint("analytics", __name__, url_prefix="/api")

# 模拟设备、模型、输入维度关系
DEVICE_MODEL_INPUT = {
    "Jetson nano": {
        "ResNet50": ["1x224x224x3", "1x32x32x3"],
        "VGG16": ["1x224x224x3"],
        "MobileNetV1": ["1x224x224x3", "1x32x32x3"]
    },
    "Jetson Nx": {
        "ResNet50": ["1x224x224x3"],
        "VGG16": ["1x224x224x3", "1x32x32x3"],
        "MobileNetV1": ["1x224x224x3"]
    }
}

@dashboard_bp.route("/options", methods=["GET"])
def get_options():
    """
    返回筛选框可选值
    任意一个筛选框值可选，其余根据约束返回可选值
    """
    device = request.args.get("device")
    model = request.args.get("model")
    input_dim = request.args.get("input")

    # 处理 devices
    devices = list(DEVICE_MODEL_INPUT.keys())

    # 处理 models
    models = set()
    if device:
        models.update(DEVICE_MODEL_INPUT.get(device, {}).keys())
    else:
        # 没选设备时，列出所有模型
        for m in DEVICE_MODEL_INPUT.values():
            models.update(m.keys())
    models = list(models)

    # 处理 inputs
    inputs = set()
    if device and model:
        inputs.update(DEVICE_MODEL_INPUT.get(device, {}).get(model, []))
    elif device:
        for m_inputs in DEVICE_MODEL_INPUT.get(device, {}).values():
            inputs.update(m_inputs)
    elif model:
        for dev_models in DEVICE_MODEL_INPUT.values():
            if model in dev_models:
                inputs.update(dev_models[model])
    else:
        # 没选任何值时，返回所有
        for dev_models in DEVICE_MODEL_INPUT.values():
            for m_inputs in dev_models.values():
                inputs.update(m_inputs)
    inputs = list(inputs)

    return jsonify({
        "devices": devices,
        "models": models,
        "inputs": inputs
    })


@dashboard_bp.route("/boxplot", methods=["GET"])
def get_boxplot():
    """
    根据筛选条件返回箱型图数据
    """
    device = request.args.get("device")
    model = request.args.get("model")
    input_dim = request.args.get("input")

    # 这里模拟生成 5 个分组，每组 10 个随机值
    group_count = 10
    group_size = 100

    groups = [
        [random.randint(500, 1500) for _ in range(group_size)]
        for _ in range(group_count)
    ]

    labels = [f"Device {i+1}" for i in range(group_count)]

    return jsonify({
        "labels": labels,
        "groups": groups
    })
