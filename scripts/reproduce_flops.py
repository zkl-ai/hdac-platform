import torch
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend/hdap-platform-backend'))

from app.models.definitions.resnet_tiny import resnet56

def test_flops():
    model = resnet56(num_classes=10)
    
    # Test CIFAR-10 input size
    input_32 = torch.randn(1, 3, 32, 32)
    
    # Test ImageNet input size (just in case)
    input_224 = torch.randn(1, 3, 224, 224)
    
    print("--- Testing FLOPs for ResNet-Tiny-56 ---")
    
    # 1. Try torch_pruning
    try:
        import torch_pruning as tp
        print("\n[torch_pruning]")
        ops_32, params_32 = tp.utils.count_ops_and_params(model, input_32)
        print(f"Input 32x32: FLOPs={ops_32/1e6:.2f}M, Params={params_32/1e6:.2f}M")
        
        ops_224, params_224 = tp.utils.count_ops_and_params(model, input_224)
        print(f"Input 224x224: FLOPs={ops_224/1e6:.2f}M, Params={params_224/1e6:.2f}M")
    except ImportError:
        print("\n[torch_pruning] Not installed")
    except Exception as e:
        print(f"\n[torch_pruning] Error: {e}")

    # 2. Try thop
    try:
        from thop import profile
        print("\n[thop]")
        ops_32, params_32 = profile(model, inputs=(input_32, ), verbose=False)
        print(f"Input 32x32: FLOPs={ops_32/1e6:.2f}M, Params={params_32/1e6:.2f}M")
        
        ops_224, params_224 = profile(model, inputs=(input_224, ), verbose=False)
        print(f"Input 224x224: FLOPs={ops_224/1e6:.2f}M, Params={params_224/1e6:.2f}M")
    except ImportError:
        print("\n[thop] Not installed")
    except Exception as e:
        print(f"\n[thop] Error: {e}")

if __name__ == "__main__":
    test_flops()
