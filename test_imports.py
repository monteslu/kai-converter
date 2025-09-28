#!/usr/bin/env python3
"""Debug script to test package imports"""

import sys
print("Python executable:", sys.executable)
print("Python version:", sys.version)
print("Python path:")
for p in sys.path:
    print(f"  {p}")

print("\nTesting imports:")

# Test each package
packages = [
    ("torch", "version", "__version__"),
    ("torchaudio", "version", "__version__"),
    ("demucs", "module", None),
    ("librosa", "version", "__version__"),
    ("torchcrepe", "module", None),
    ("madmom", "module", None),
    ("essentia", "module", None),
]

for pkg_name, pkg_type, version_attr in packages:
    try:
        pkg = __import__(pkg_name)
        if pkg_type == "version" and version_attr:
            version = getattr(pkg, version_attr, "unknown")
            print(f"  ✓ {pkg_name} {version}")
        else:
            print(f"  ✓ {pkg_name}")
    except ImportError as e:
        print(f"  ✗ {pkg_name}: {e}")
    except Exception as e:
        print(f"  ✗ {pkg_name}: Unexpected error: {e}")

# Special test for torchcrepe
print("\nDetailed torchcrepe test:")
try:
    import torchcrepe
    print("  Successfully imported torchcrepe")
    print(f"  torchcrepe location: {torchcrepe.__file__ if hasattr(torchcrepe, '__file__') else 'unknown'}")
except Exception as e:
    print(f"  Failed to import torchcrepe: {e}")
    import traceback
    traceback.print_exc()

# Test CUDA
print("\nGPU Support:")
try:
    import torch
    if torch.cuda.is_available():
        print(f"  CUDA available: {torch.cuda.get_device_name(0)}")
    elif torch.backends.mps.is_available():
        print("  MPS (Apple Silicon) available")
    else:
        print("  CPU only")
except Exception as e:
    print(f"  Error checking GPU: {e}")