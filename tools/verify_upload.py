import sys
import os
sys.path.append('/data/workspace/hdap-platform/backend/hdap-platform-backend')
from app import create_app
from app.extensions import db

app = create_app()

def verify():
    with app.test_client() as client:
        # 1. Init Seed
        print("Initializing seed data...")
        res = client.post('/api/models/seed', json={'force': True}) # Force reset to be clean
        print("Seed response:", res.json)
        
        # 2. Verify Dataset Creation
        print("Verifying Dataset creation...")
        res = client.get('/api/datasets')
        datasets = res.json.get('data', {}).get('items', [])
        cifar = next((d for d in datasets if d['name'] == 'CIFAR-10'), None)
        if cifar:
            print(f"Dataset found: {cifar['name']} -> {cifar['path']}")
        else:
            print("Dataset CIFAR-10 NOT found!")
        
        # 3. Upload Model
        print("Uploading model...")
        file_path = '/data/workspace/hdap-platform/temp_models/resnet56_cifar10_init.pth'
        if not os.path.exists(file_path):
             print(f"File not found: {file_path}")
             return

        with open(file_path, 'rb') as f:
            data = {
                'file': (f, 'resnet56_cifar10_init.pth'),
                'name': 'ResNet56-CIFAR10',
                'version': 'v1-uploaded',
                'dataset': 'CIFAR-10',
                'deviceType': 'Jetson Nano',
                'inputDim': '1x3x32x32',
                'outputDim': '10',
                'taskType': 'Image Classification'
            }
            res = client.post('/api/models/upload', data=data, content_type='multipart/form-data')
            print(f"Upload Status: {res.status_code}")
            print(f"Upload Response Data: {res.data.decode('utf-8')}")
            if res.status_code != 200:
                print("Upload failed!")
                return
            
        # 4. Check Tree
        print("Checking model tree...")
        res = client.get('/api/models/tree')
        tree = res.json.get('data', {}).get('items', [])
        found = False
        for m in tree:
            if m['name'] == 'ResNet56-CIFAR10':
                print(f"Found model: {m['name']}")
                for child in m.get('children', []):
                    # child is device group
                     for v in child.get('children', []):
                         if v['name'] == 'v1-uploaded':
                             print(f"Found version: {v['name']}, Dataset: {v.get('dataset')}")
                             found = True
        
        if found:
            print("Verification SUCCESS!")
        else:
            print("Verification FAILED: Model/Version not found in tree.")

if __name__ == "__main__":
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created/verified.")
        except Exception as e:
            print(f"Warning: db.create_all() failed: {e}")
        verify()
