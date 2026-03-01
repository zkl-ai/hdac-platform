import argparse
import sys
import os
import torch

# Try to import torch_pruning first
try:
    import torch_pruning as tp
except ImportError:
    tp = None

# Fallback to thop if torch_pruning is not available
try:
    from thop import profile
except ImportError:
    profile = None

def parse_input_dim(dim_str):
    """
    Parse input dim string like '1x3x224x224' to tuple (1, 3, 224, 224)
    """
    try:
        return tuple(map(int, dim_str.split('x')))
    except:
        return None

def main():
    parser = argparse.ArgumentParser(description='Calculate FLOPs for a model')
    parser.add_argument('--model', type=str, required=True, help='Model name or path')
    parser.add_argument('--input', type=str, required=True, help='Input dimension, e.g. 1x3x224x224')
    parser.add_argument('--version', type=str, default='uncompressed', help='Model version name')
    
    args = parser.parse_args()
    
    # Construct path to inference.py based on conventions
    # Assuming standard path: /data/workspace/hdap-platform/database/models/{model_name}/{version_name}/inference.py
    base_dir = "/data/workspace/hdap-platform/database/models"
    model_dir = os.path.join(base_dir, args.model, args.version)
    inference_script = os.path.join(model_dir, "inference.py")
    
    if not os.path.exists(inference_script):
        # Fallback for testing or if model not found in DB structure
        print(f"Error: inference.py not found at {inference_script}")
        sys.exit(1)
        
    # Dynamically import the inference module
    sys.path.append(model_dir)
    try:
        import inference
        # Reload in case it was already imported
        import importlib
        importlib.reload(inference)
    except ImportError as e:
        print(f"Error importing inference script: {e}")
        sys.exit(1)
        
    # Create dummy input
    input_shape = parse_input_dim(args.input)
    if not input_shape:
        print(f"Error: Invalid input dimension format: {args.input}")
        sys.exit(1)
        
    device = torch.device("cpu")
    try:
        dummy_input = torch.randn(input_shape).to(device)
    except Exception as e:
         print(f"Error creating dummy input: {e}")
         sys.exit(1)

    # Load model
    try:
        if hasattr(inference, 'get_model'):
            model = inference.get_model()
        elif hasattr(inference, 'load_model'):
             # Try passing a dummy path if needed, or rely on defaults
             model_path = os.path.join(model_dir, "model.pth")
             model = inference.load_model(model_path, device='cpu')
        else:
            print("Error: inference.py must contain 'get_model()' or 'load_model()'")
            sys.exit(1)
            
        model.to(device)
        model.eval()
        
        # Calculate FLOPs
        flops = 0
        if tp is not None:
            # Use torch_pruning
            try:
                ops, params = tp.utils.count_ops_and_params(model, dummy_input)
                flops = ops
            except Exception as e:
                # Fallback if tp fails
                if profile is not None:
                    flops, params = profile(model, inputs=(dummy_input, ), verbose=False)
                else:
                    raise e
        elif profile is not None:
            flops, params = profile(model, inputs=(dummy_input, ), verbose=False)
        else:
            print("Error: Neither 'torch_pruning' nor 'thop' library found. Please install one of them.")
            sys.exit(1)
        
        # Output Raw FLOPs (frontend handles formatting)
        print(f"{int(flops)}")
        
    except Exception as e:
        print(f"Error calculating FLOPs: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
