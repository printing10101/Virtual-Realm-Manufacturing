# GPU Accelerated Training Design

## Overview
Add CUDA GPU acceleration support for LNN model training with automatic device detection, mixed precision training, and DataLoader optimization.

## Architecture

### Device Management
- Create `device_manager.py` with auto-detection via `torch.cuda.is_available()`
- Priority: GPU > CPU with automatic fallback
- Support environment variable `LNN_TRAINING_DEVICE` for manual override

### Model Updates
- Add `to_torch()` method to NumPy models (CFCModel, LTCModel) for PyTorch conversion
- Enhance existing torch models with device-aware initialization

### Trainer Enhancements
- Integrate `torch.cuda.amp.autocast()` and `GradScaler` for mixed precision
- Automatic tensor movement to target device
- GPU memory monitoring and OOM prevention
- Device info in training logs

### DataLoader Optimization
- Conditional `pin_memory=True` for GPU mode
- Dynamic `num_workers` based on CPU cores
- Auto-adjust `batch_size` for GPU

### API Extensions
- `GET /api/v1/lnn/device/info` - device information
- Add `device` parameter to training requests (auto/gpu/cpu)
- Device status monitoring endpoint

## Implementation Plan
1. Create device_manager.py
2. Enhance trainer.py with AMP and GPU support
3. Update CFC/LTC models with to_torch() conversion
4. Add API endpoints
5. Write tests
