import os
import torch
from torchvision import datasets, transforms

def get_dataloader(dataset_name: str, batch_size=128, data_root='/data/workspace/datasets'):
    """
    Get train and test dataloaders for standard datasets.
    """
    # Normalize dataset name: lowercase, remove special chars
    dataset_name = dataset_name.lower().replace('-', '').replace('_', '').replace(' ', '')
    
    if dataset_name == 'cifar10':
        mean = (0.4914, 0.4822, 0.4465)
        std = (0.2023, 0.1994, 0.2010)
        num_classes = 10
        input_size = (1, 3, 32, 32)
        transform_train = transforms.Compose([
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ])
        transform_test = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ])
        
        train_set = datasets.CIFAR10(root=data_root, train=True, download=True, transform=transform_train)
        test_set = datasets.CIFAR10(root=data_root, train=False, download=True, transform=transform_test)
        
    elif dataset_name == 'cifar100':
        mean = (0.5071, 0.4867, 0.4408)
        std = (0.2675, 0.2565, 0.2761)
        num_classes = 100
        input_size = (1, 3, 32, 32)
        transform_train = transforms.Compose([
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ])
        transform_test = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ])
        
        train_set = datasets.CIFAR100(root=data_root, train=True, download=True, transform=transform_train)
        test_set = datasets.CIFAR100(root=data_root, train=False, download=True, transform=transform_test)
    
    else:
        # Fallback or error. For now, we support CIFAR which is in the reference.
        raise ValueError(f"Dataset {dataset_name} not supported yet.")

    train_loader = torch.utils.data.DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=2)
    test_loader = torch.utils.data.DataLoader(test_set, batch_size=batch_size, shuffle=False, num_workers=2)
    
    return train_loader, test_loader, num_classes, input_size
