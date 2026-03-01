import importlib.util
import sys
import os
import torch
import logging
import inspect
from app.models.model import ModelVersion
from app.extensions import db

logger = logging.getLogger(__name__)

class ModelLoader:
    @staticmethod
    def _load_module(definition_path: str):
        if not os.path.exists(definition_path):
            raise FileNotFoundError(f"Model definition file not found: {definition_path}")
            
        # Add the directory containing the file to sys.path so it can import its own dependencies if needed
        model_dir = os.path.dirname(definition_path)
        if model_dir not in sys.path:
            sys.path.insert(0, model_dir)
            
        module_name = os.path.splitext(os.path.basename(definition_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, definition_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        return None

    @staticmethod
    def load_custom_components(definition_path: str):
        """
        Load custom training components (get_criterion, get_optimizer, get_dataloader) from the definition file.
        """
        components = {}
        try:
            module = ModelLoader._load_module(definition_path)
            if not module:
                return components
                
            if hasattr(module, 'get_criterion'):
                components['get_criterion'] = getattr(module, 'get_criterion')
            
            if hasattr(module, 'get_optimizer'):
                components['get_optimizer'] = getattr(module, 'get_optimizer')
                
            if hasattr(module, 'get_dataloader'):
                components['get_dataloader'] = getattr(module, 'get_dataloader')

            if hasattr(module, 'train_one_epoch'):
                components['train_one_epoch'] = getattr(module, 'train_one_epoch')
                
        except Exception as e:
            logger.warning(f"Failed to load custom components: {e}")
            
        return components

    @staticmethod
    def load_model_class(definition_path: str):
        """
        Dynamically load the model class from a python file.
        The file is expected to define a class that inherits from torch.nn.Module.
        """
        module = ModelLoader._load_module(definition_path)
        if not module:
            raise ValueError("Failed to load module")
            
        # Find the first class that inherits from nn.Module
        # Improved logic: look for class named 'ResNet' or similar if multiple exist?
        # Or assume standard export format where the main model is obvious.
        # For resnet_tiny.py, it exports 'resnet'.
        
        # Priority 1: Check __all__
        if hasattr(module, '__all__'):
            try:
                for name in module.__all__:
                    if hasattr(module, name):
                        obj = getattr(module, name)
                        # It might be a function (e.g. resnet56) or a class
                        if isinstance(obj, type) and issubclass(obj, torch.nn.Module):
                            return obj
            except Exception as e:
                logger.warning(f"Error processing __all__ in {definition_path}: {e}, falling back to full scan.")
        
        # Priority 2: Find any class inheriting from nn.Module that is NOT Bottleneck/BasicBlock unless it's the only one.
        candidates = []
        for name, obj in module.__dict__.items():
            if isinstance(obj, type) and issubclass(obj, torch.nn.Module) and obj is not torch.nn.Module:
                candidates.append(obj)
        
        # Filter out common blocks if possible, or pick the "biggest" one?
        # For resnet_tiny, we have BasicBlock, Bottleneck, ResNet. We want ResNet.
        for c in candidates:
            if c.__name__ == 'ResNet':
                return c
        
        # Fallback: Return the last one or first one?
        if candidates:
            return candidates[-1]
                
        raise ValueError("No valid torch.nn.Module class found in the definition file.")

    @staticmethod
    def get_pruning_config(model_name: str):
        """
        Get the pruning layer sizes definition for a given model.
        This aligns with the surrogate model training definitions.
        """
        import numpy as np
        if model_name in ['resnet56', 'ResNet-Tiny-56']:
            return np.array(
                [16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 
                 32, 32, 32, 32, 32, 32, 32, 32, 32,
                 64, 64, 64, 64, 64, 64, 64, 64]
                ).astype(dtype=np.int32)
        elif model_name in ['vgg16', 'VGG16']:
            return np.array([64, 64, 128, 128, 256, 256, 256, 512, 512, 512, 512, 512, 512]).astype(dtype=np.int32)
        elif model_name in ['resnet50', 'ResNet50']:
             return np.array([
                64, 64, 64,
                128, 128, 128, 128,
                256, 256, 256, 256, 256, 256, 
                512, 512, 512,
            ]).astype(dtype=np.int32)
        
        return None

    @staticmethod
    def load_model_instance(model_name: str, device_type: str = None) -> torch.nn.Module:
        """
        Load a model instance based on the database record.
        """
        from app.models.model import Model
        model_meta = Model.query.filter_by(name=model_name).first()
        if not model_meta:
            raise ValueError(f"Model {model_name} not found in database.")
            
        # Try to find a version with definition path
        query = ModelVersion.query.filter_by(model_id=model_meta.id)
        if device_type:
            v = query.filter_by(device_type=device_type).first()
            if not v:
                v = query.first()
        else:
            v = query.first()
            
        if not v or not v.definition_path:
             # If local debug/dev environment, fallback to known paths for resnet_tiny
             if model_name in ['resnet56', 'ResNet-Tiny-56']: # resnet_tiny
                 fallback_path = '/data/workspace/hdap-platform/backend/hdap-platform-backend/app/models/definitions/resnet_tiny.py'
                 if os.path.exists(fallback_path):
                     logger.warning(f"Using fallback definition for {model_name}")
                     v_mock = type('obj', (object,), {'definition_path': fallback_path, 'file_path': None, 'dataset': 'cifar10'})
                     v = v_mock
                 else:
                     raise ValueError(f"No model version with definition found for {model_name}")
             else:
                 raise ValueError(f"No model version with definition found for {model_name}")

        cls = ModelLoader.load_model_class(v.definition_path)
        
        # Instantiate
        try:
            # Smart instantiation for ResNet-Tiny
            # resnet_tiny.ResNet needs (depth, num_filters, block_name, num_classes)
            # Or use factory functions like resnet56() if we loaded the module.
            # But we loaded the class.
            
            # Hardcoded logic for known models (Registry pattern would be better)
            if model_name in ['resnet56', 'ResNet-Tiny-56']:
                # ResNet-56 for CIFAR
                # depth=56, num_filters=[16, 16, 32, 64]
                model = cls(depth=56, num_filters=[16, 16, 32, 64], block_name='BasicBlock', num_classes=10)
            elif model_name == 'resnet20':
                model = cls(depth=20, num_filters=[16, 16, 32, 64], block_name='BasicBlock', num_classes=10)
            else:
                # Default generic init
                import inspect
                sig = inspect.signature(cls.__init__)
                if 'num_classes' in sig.parameters:
                    model = cls(num_classes=10)
                else:
                    model = cls()
        except Exception as e:
            raise RuntimeError(f"Failed to instantiate model class {cls.__name__}: {e}")
            
        # Load weights if available
        if v.file_path and os.path.exists(v.file_path):
            state_dict = torch.load(v.file_path, map_location='cpu')
            # Handle DataParallel wrap
            if 'state_dict' in state_dict:
                state_dict = state_dict['state_dict']
            new_state_dict = {}
            for k, val in state_dict.items():
                if k.startswith('module.'):
                    new_state_dict[k[7:]] = val
                else:
                    new_state_dict[k] = val
            model.load_state_dict(new_state_dict)
            
        return model, v
