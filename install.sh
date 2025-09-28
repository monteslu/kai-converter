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

# Install numpy first (required for madmom build)
echo "Installing numpy first (required for madmom)..."
pip install numpy

# Platform-specific torch installation
echo "Installing PyTorch..."
if [[ "$OS" == "Darwin" ]]; then
    # macOS
    if [[ "$ARCH" == "arm64" ]]; then
        echo "  Detected Apple Silicon Mac"
        pip install torch torchaudio
    else
        echo "  Detected Intel Mac"
        pip install torch torchaudio
    fi
elif [[ "$OS" == "Linux" ]]; then
    # Linux
    if [[ "$ARCH" == "aarch64" ]]; then
        echo "  Detected ARM64 Linux (e.g., Jetson, Raspberry Pi)"
        # For Jetson, might need special wheels
        pip install torch torchaudio || {
            echo "  Standard PyTorch installation failed."
            echo "  For Jetson devices, you may need NVIDIA's wheels:"
            echo "  https://forums.developer.nvidia.com/t/pytorch-for-jetson"
        }
    else
        echo "  Detected x86_64 Linux"
        pip install torch torchaudio
    fi
else
    echo "  Unknown OS, attempting standard installation"
    pip install torch torchaudio
fi

# Install core requirements
echo ""
echo "Installing core audio processing libraries..."
pip install demucs librosa scipy mutagen

# Try to install madmom (optional - provides better music analysis)
echo ""
echo "Attempting to install madmom (optional - provides better music analysis)..."

# Check if Cython is needed for madmom
pip install Cython

if [[ "$OS" == "Darwin" ]]; then
    # macOS might need different compiler flags
    if pip install madmom --no-build-isolation; then
        echo "✓ madmom installed successfully"
    else
        # Try without no-build-isolation on Mac if first attempt fails
        if pip install madmom; then
            echo "✓ madmom installed successfully (fallback method)"
        else
            echo "⚠ madmom installation failed - continuing without it"
            echo "  The converter will use librosa for onset/beat detection instead"
        fi
    fi
else
    # Linux
    if pip install madmom --no-build-isolation; then
        echo "✓ madmom installed successfully"
    else
        echo "⚠ madmom installation failed - continuing without it"
        echo "  The converter will use librosa for onset/beat detection instead"
    fi
fi

# Try to install essentia (optional - provides better key detection)
echo ""
echo "Attempting to install essentia (optional - provides better key detection)..."

if [[ "$ARCH" == "aarch64" ]] || [[ "$ARCH" == "arm64" ]]; then
    # ARM systems may have limited essentia versions
    pip install 'essentia>=2.1b6.dev234' 2>/dev/null || {
        echo "⚠ essentia installation failed - continuing without it"
        echo "  The converter will use librosa for key detection instead"
    }
else
    # x86_64 systems can use newer versions
    pip install 'essentia>=2.1b6.dev374' 2>/dev/null || pip install 'essentia>=2.1b6.dev234' 2>/dev/null || {
        echo "⚠ essentia installation failed - continuing without it"
        echo "  The converter will use librosa for key detection instead"
    }
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
python3 -c "import torch; print(f'  ✓ PyTorch {torch.__version__}')" 2>/dev/null || echo "  ✗ PyTorch"
python3 -c "import torchaudio; print(f'  ✓ torchaudio {torchaudio.__version__}')" 2>/dev/null || echo "  ✗ torchaudio"
python3 -c "import demucs; print('  ✓ demucs')" 2>/dev/null || echo "  ✗ demucs"
python3 -c "import librosa; print(f'  ✓ librosa {librosa.__version__}')" 2>/dev/null || echo "  ✗ librosa"
python3 -c "import madmom; print('  ✓ madmom (enhanced audio analysis)')" 2>/dev/null || echo "  ⚠ madmom (using librosa fallback)"
python3 -c "import essentia; print('  ✓ essentia (enhanced key detection)')" 2>/dev/null || echo "  ⚠ essentia (using librosa fallback)"

echo ""
echo "Installation complete!"
echo ""
echo "To use the converter:"
echo "  python -m kai_pack input.mp3"
echo ""
echo "For more options:"
echo "  python -m kai_pack --help"