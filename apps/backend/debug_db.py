from app import create_app
from app.extensions import db
from app.models.model import Model, ModelVersion

app = create_app()
with app.app_context():
    model_name = "ResNet-Tiny-56"
    m = Model.query.filter_by(name=model_name).first()
    print(f"Model: {m}")
    if m:
        versions = ModelVersion.query.filter_by(model_id=m.id).all()
        print(f"Versions count: {len(versions)}")
        for v in versions:
            print(f"Version ID: {v.id}, Device: {v.device_type}, DefPath: {v.definition_path}")
