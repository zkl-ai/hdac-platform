
from app import create_app
from app.extensions import db
from app.models.model import ModelVersion, Model

app = create_app()
with app.app_context():
    # Update device type for ResNet-Tiny-56
    model = Model.query.filter_by(name='ResNet-Tiny-56').first()
    if model:
        print(f"Found model: {model.name}")
        versions = ModelVersion.query.filter_by(model_id=model.id).all()
        for v in versions:
            print(f"Updating version {v.id} from {v.device_type} to Jetson Xavier NX")
            v.device_type = 'Jetson Xavier NX'
        
        db.session.commit()
        print("Update complete.")
    else:
        # Fallback if name was reset-tiny-56
        model = Model.query.filter_by(name='reset-tiny-56').first()
        if model:
             print(f"Found old model name: {model.name}, renaming...")
             model.name = 'ResNet-Tiny-56'
             versions = ModelVersion.query.filter_by(model_id=model.id).all()
             for v in versions:
                v.device_type = 'Jetson Xavier NX'
             db.session.commit()
             print("Update and rename complete.")
        else:
             print("Model not found, skipping update.")
