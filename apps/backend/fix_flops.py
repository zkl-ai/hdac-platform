
from app import create_app
from app.extensions import db
from app.models.model import ModelVersion, Model

app = create_app()
with app.app_context():
    # Update Model FLOPs
    models = Model.query.all()
    for m in models:
        if m.model_flops and m.model_flops < 1000:
            print(f"Fixing Model {m.name} FLOPs: {m.model_flops} -> {m.model_flops * 1e9}")
            m.model_flops = m.model_flops * 1e9
            
    # Update Version FLOPs
    versions = ModelVersion.query.all()
    for v in versions:
        if v.flops and v.flops < 1000:
             print(f"Fixing Version {v.id} FLOPs: {v.flops} -> {v.flops * 1e9}")
             v.flops = v.flops * 1e9
             
    db.session.commit()
    print("FLOPs data fixed.")
