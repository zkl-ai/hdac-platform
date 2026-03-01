
import torch
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend/hdap-platform-backend'))

from app.models.definitions.resnet_tiny import resnet56

def check_input_dim():
    model = resnet56(num_classes=10)
    model.eval()
    
    # Case 1: Correct Input (1, 3, 32, 32)
    input_correct = torch.randn(1, 3, 32, 32)
    try:
        output = model(input_correct)
        print(f"Input (1, 3, 32, 32): Success, Output shape {output.shape}")
    except Exception as e:
        print(f"Input (1, 3, 32, 32): Failed, {e}")

    # Case 2: Incorrect Input (3, 32, 32) - Missing Batch Dim
    input_incorrect = torch.randn(3, 32, 32)
    try:
        output = model(input_incorrect)
        print(f"Input (3, 32, 32): Success, Output shape {output.shape}")
    except Exception as e:
        print(f"Input (3, 32, 32): Failed\nError: {e}")

if __name__ == "__main__":
    check_input_dim()
