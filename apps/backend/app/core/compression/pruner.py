import torch
import torch_pruning as tp
import copy
import logging

logger = logging.getLogger(__name__)

def get_model_layer_sizes(model):
    """
    Return the number of channels/filters in each prunable UNIT (Block or Layer).
    Used to initialize the Evolutionary Algorithm.
    """
    sizes = []
    model_name = model.__class__.__name__
    
    if model_name == 'ResNet':
        # Count Blocks
        for m in model.modules():
            if m.__class__.__name__ in ['BasicBlock', 'Bottleneck']:
                # What size to return? The number of output channels of the block?
                # Or just a placeholder size to indicate "this is a gene".
                # The EA usually needs `layer_sizes` to calculate compression ratio or bounds.
                # For ResNet Block, it's usually the planes (output channels).
                # BasicBlock has `conv1`, `conv2`. `planes` attribute?
                if hasattr(m, 'conv1'):
                    sizes.append(m.conv1.out_channels) # Approx
                else:
                    sizes.append(64) # Fallback
    else:
        # Conv2d count
        for m in model.modules():
            if isinstance(m, torch.nn.Conv2d):
                sizes.append(m.out_channels)
                
    return sizes

class ModelPruner:
    def __init__(self, model: torch.nn.Module, example_input: torch.Tensor, layer_sizes=None):
        self.model = model
        self.example_input = example_input
        self.fixed_layer_sizes = layer_sizes
        self.base_ops, self.base_params = tp.utils.count_ops_and_params(model, example_inputs=example_input)

    def prune_by_rates(self, prune_rates: list):
        """
        Prune the model based on a list of pruning rates.
        Supports Block-wise pruning for ResNet-Tiny.
        """
        model_copy = copy.deepcopy(self.model)
        model_copy.eval()
        
        pruning_ratio_dict = {}
        ignored_layers = []
        
        # Determine model type and prune accordingly
        # We can check class name or structure
        model_name = model_copy.__class__.__name__
        
        if model_name == 'ResNet':
            # ResNet-Tiny Logic (from reference grid_search_resnet56_cifar.py)
            # Find BasicBlocks and map prune_rates to them sequentially
            
            if prune_rates is None:
                logger.warning("Prune rates is None, skipping pruning map")
                return model_copy
            
            idx = 0
            for m in model_copy.modules():
                # Check for BasicBlock or Bottleneck
                if m.__class__.__name__ in ['BasicBlock', 'Bottleneck']:
                    if idx < len(prune_rates):
                        pruning_ratio_dict[m] = prune_rates[idx]
                        idx += 1
                
                # Check for Classifier (Linear)
                if isinstance(m, torch.nn.Linear):
                    # Usually the last linear is the classifier.
                    # Reference logic: `if isinstance(m, torch.nn.Linear) and m.out_features == 10: ignored_layers.append(m)`
                    # We should be more generic: ignore the last Linear layer found?
                    # Or check against num_classes if known.
                    pass
            
            # Explicitly ignore the final FC layer (often named 'fc' or 'linear')
            if hasattr(model_copy, 'fc'):
                ignored_layers.append(model_copy.fc)
            elif hasattr(model_copy, 'classifier'):
                ignored_layers.append(model_copy.classifier)
            elif hasattr(model_copy, 'linear'):
                ignored_layers.append(model_copy.linear)
                
        else:
            # Fallback to Layer-wise pruning (Conv2d)
            logger.warning(f"Unknown model type {model_name}, falling back to Conv2d layer-wise pruning")
            prunable_modules = [m for m in model_copy.modules() if isinstance(m, torch.nn.Conv2d)]
            idx = 0
            for m in prunable_modules:
                if idx < len(prune_rates):
                    pruning_ratio_dict[m] = prune_rates[idx]
                    idx += 1
            
            # Try to find classifier to ignore
            for m in model_copy.modules():
                if isinstance(m, torch.nn.Linear):
                    ignored_layers.append(m)

        # Importance
        imp = tp.importance.MagnitudeImportance(p=2)
        
        pruner = tp.pruner.MetaPruner(
            model_copy,
            self.example_input,
            importance=imp,
            pruning_ratio=0.0, # Default to 0 (no pruning) for unspecified layers
            pruning_ratio_dict=pruning_ratio_dict,
            ignored_layers=ignored_layers,
        )
        
        pruner.step()
        
        return model_copy

    def get_flops_and_params(self, model=None):
        if model is None:
            model = self.model
        return tp.utils.count_ops_and_params(model, example_inputs=self.example_input)

    def get_layer_sizes(self):
        """
        Return the number of channels/filters in each prunable UNIT (Block or Layer).
        Used to initialize the Evolutionary Algorithm.
        """
        if self.fixed_layer_sizes is not None:
            return self.fixed_layer_sizes.tolist() if hasattr(self.fixed_layer_sizes, 'tolist') else self.fixed_layer_sizes

        return get_model_layer_sizes(self.model)
