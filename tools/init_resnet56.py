import torch
import sys
import os
sys.path.append('/data/workspace/cluster-compression/benchmarks')
from engine.models.cifar.resnet_tiny import resnet56

def main():
    print("Generating ResNet56 weights...")
    model = resnet56(num_classes=10)
    
    # Randomly initialize (already random by default init)
    
    # Save to a temporary location for the user to upload, 
    # OR save directly to the infra folder if simulating "upload" via script.
    # The user asked to "complete the steps to upload... and save result in hdap-platform".
    # Since I implemented the upload API, I should probably use the API to upload it to verify the flow.
    # So I will save it to a temp file first.
    
    temp_dir = '/data/workspace/hdap-platform/temp_models'
    os.makedirs(temp_dir, exist_ok=True)
    save_path = os.path.join(temp_dir, 'resnet56_cifar10_init.pth')
    torch.save(model.state_dict(), save_path)
    print(f"Model saved to {save_path}")

if __name__ == "__main__":
    main()
