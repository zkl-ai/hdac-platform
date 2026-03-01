from app import create_app
from app.models.model import ModelVersion
from app.extensions import db

app = create_app()
with app.app_context():
    # Find the version with the wrong path
    v = ModelVersion.query.get(1) # We saw ID 1 in debug output
    if v:
        print(f"Old Path: {v.file_path}")
        if 'reset-tiny-56' in v.file_path:
            new_path = v.file_path.replace('reset-tiny-56', 'ResNet-Tiny-56')
            v.file_path = new_path
            print(f"New Path: {v.file_path}")
            db.session.commit()
            print("Fixed.")
        else:
            print("Path does not contain typo.")
    else:
        print("Version 1 not found.")
