#!/bin/bash

echo "Installing KAI Converter dependencies..."

# Detect OS
OS="$(uname -s)"
ARCH="$(uname -m)"

echo "Detected: $OS on $ARCH"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
echo "Python version: $PYTHON_VERSION"

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Warning: Not in a virtual environment. Consider creating one with:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Upgrade pip first
echo "Upgrading pip..."
pip install --upgrade pip

# Install build dependencies
echo "Installing build dependencies..."
pip install wheel setuptools

# Install numpy <2.0 for scipy compatibility
echo "Installing numpy <2.0 (required for scipy/madmom compatibility)..."
pip install "numpy<2.0"

# Platform-specific torch installation
echo "Installing PyTorch..."
if [[ "$OS" == "Darwin" ]]; then
    # macOS
    if [[ "$ARCH" == "arm64" ]]; then
        echo "  Detected Apple Silicon Mac"
        pip install torch torchaudio torchcrepe
    else
        echo "  Detected Intel Mac"
        pip install torch torchaudio torchcrepe
    fi
elif [[ "$OS" == "Linux" ]]; then
    # Linux
    if [[ "$ARCH" == "aarch64" ]]; then
        echo "  Detected ARM64 Linux (e.g., Jetson, Raspberry Pi)"

        # Check if this is a Jetson device
        if [ -f /etc/nv_tegra_release ] || [ -d /usr/local/cuda ]; then
            echo "  Detected NVIDIA Jetson device"
            echo ""
            echo "  ⚠️  IMPORTANT: Jetson requires special PyTorch wheels!"
            echo "  See the Jetson section in README.md for proper CUDA setup"
            echo "  or visit: https://forums.developer.nvidia.com/t/pytorch-for-jetson"
            echo ""
            echo "  Attempting standard installation (may not have CUDA support)..."
        fi

        pip install torch torchaudio torchcrepe || {
            echo "  Standard PyTorch installation may not have CUDA support on Jetson."
            echo "  See the Jetson section in README.md for proper installation."
        }
    else
        echo "  Detected x86_64 Linux"
        pip install torch torchaudio torchcrepe
    fi
else
    echo "  Unknown OS, attempting standard installation"
    pip install torch torchaudio torchcrepe
fi

# Install core requirements
echo ""
echo "Installing core audio processing libraries..."
pip install demucs librosa scipy mutagen

# Try to install optional packages
echo ""
echo "Installing optional analysis packages..."

# Cython is needed for madmom
pip install Cython 2>/dev/null || true

# Try madmom (optional - provides better music analysis)
echo "  Attempting madmom (better onset/beat detection)..."
if pip install madmom --no-build-isolation 2>/dev/null; then
    echo "  ✓ madmom installed successfully"
else
    echo "  ⚠ madmom installation failed - will use librosa fallback"
fi

# Try essentia (optional - provides better key detection)
echo "  Attempting essentia (better key detection)..."
if [[ "$ARCH" == "aarch64" ]] || [[ "$ARCH" == "arm64" ]]; then
    # ARM systems may have limited essentia versions
    pip install 'essentia>=2.1b6.dev234' 2>/dev/null && echo "  ✓ essentia installed successfully" || echo "  ⚠ essentia installation failed - will use librosa fallback"
else
    # x86_64 systems can use newer versions
    (pip install 'essentia>=2.1b6.dev374' 2>/dev/null || pip install 'essentia>=2.1b6.dev234' 2>/dev/null) && echo "  ✓ essentia installed successfully" || echo "  ⚠ essentia installation failed - will use librosa fallback"
fi

# Install any remaining requirements
echo ""
echo "Installing any remaining requirements..."
grep -v "^#" requirements.txt | grep -v "^$" | while read -r requirement; do
    # Skip if already installed or if it's madmom and failed
    pip show "$(echo $requirement | cut -d'>' -f1 | cut -d'=' -f1)" &>/dev/null || pip install "$requirement" 2>/dev/null || true
done

# Verify installation
echo ""
echo "Verifying installation..."

# If not in venv, ensure user site-packages is in path
if [[ "$VIRTUAL_ENV" == "" ]]; then
    export PYTHONPATH="$HOME/.local/lib/python$PYTHON_VERSION/site-packages:$PYTHONPATH"
fi

# Use the same Python that pip is using
PYTHON_CMD="${PYTHON_CMD:-python3}"

$PYTHON_CMD -c "import torch; print('  ✓ PyTorch', torch.__version__)" 2>/dev/null || echo "  ✗ PyTorch"
$PYTHON_CMD -c "import torchaudio; print('  ✓ torchaudio', torchaudio.__version__)" 2>/dev/null || echo "  ✗ torchaudio"
$PYTHON_CMD -c "import demucs; print('  ✓ demucs')" 2>/dev/null || echo "  ✗ demucs"
$PYTHON_CMD -c "import librosa; print('  ✓ librosa', librosa.__version__)" 2>/dev/null || echo "  ✗ librosa"
$PYTHON_CMD -c "import torchcrepe; print('  ✓ torchcrepe (GPU-capable pitch detection)')" 2>/dev/null || echo "  ✗ torchcrepe"
$PYTHON_CMD -c "import madmom; print('  ✓ madmom (enhanced audio analysis)')" 2>/dev/null || echo "  ⚠ madmom (using librosa fallback)"
$PYTHON_CMD -c "import essentia; print('  ✓ essentia (enhanced key detection)')" 2>/dev/null || echo "  ⚠ essentia (using librosa fallback)"

# Check CUDA availability
echo ""
$PYTHON_CMD -c "import torch; print('  GPU Support:', 'CUDA' if torch.cuda.is_available() else 'MPS' if torch.backends.mps.is_available() else 'CPU only')" 2>/dev/null

echo ""
echo "Installation complete!"
echo ""
echo "To use the converter:"
echo "  python -m kai_pack input.mp3"
echo ""
echo "For more options:"
echo "  python -m kai_pack --help"