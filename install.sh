#!/bin/bash

echo "Installing KAI Converter dependencies..."

# Detect OS
OS="$(uname -s)"
ARCH="$(uname -m)"

echo "Detected: $OS on $ARCH"
echo ""

# Find a Python version with venv support
PYTHON_CMD=""
TEMP_VENV_TEST="/tmp/kai_venv_test_$$"

# Try python3 first, then find all python3.* in PATH
candidates=("python3")
while IFS= read -r py_path; do
    py_name=$(basename "$py_path")
    candidates+=("$py_name")
done < <(find /usr/bin -name 'python3.*' -type f 2>/dev/null | sort -V -r)

for py_version in "${candidates[@]}"; do
    if command -v "$py_version" &> /dev/null; then
        # Check version is >= 3.8
        ver=$("$py_version" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)

        if [ "$major" -eq 3 ] && [ "$minor" -ge 8 ]; then
            # Actually test venv creation (not just --help)
            if "$py_version" -m venv "$TEMP_VENV_TEST" &> /dev/null; then
                PYTHON_CMD="$py_version"
                rm -rf "$TEMP_VENV_TEST"
                break
            fi
            rm -rf "$TEMP_VENV_TEST"
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "✗ No Python 3.8+ with venv support found."
    echo ""
    echo "Please install Python venv support for one of your installed Python versions:"
    echo "  sudo apt install python3-venv"
    echo ""
    echo "Or for a specific version (e.g., Python 3.12):"
    echo "  sudo apt install python3.12-venv"
    echo ""
    exit 1
fi

# Check Python version
PYTHON_VERSION=$("$PYTHON_CMD" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
echo "Using Python: $PYTHON_CMD (version $PYTHON_VERSION)"

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
        echo "Virtual environment exists but not activated."
        echo "Activating virtual environment..."
        source venv/bin/activate
        if [[ "$VIRTUAL_ENV" == "" ]]; then
            echo "Error: Failed to activate virtual environment."
            exit 1
        fi
        echo "✓ Virtual environment activated"
        echo ""
    else
        # Remove incomplete venv if it exists
        if [ -d "venv" ]; then
            echo "Found incomplete virtual environment, removing..."
            rm -rf venv
        fi
        echo "No virtual environment detected."
        read -p "Create one now? (Y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "Installation cancelled. Create a virtual environment with:"
            echo "  $PYTHON_CMD -m venv venv"
            echo "  source venv/bin/activate"
            exit 1
        fi
        echo "Creating virtual environment..."
        if ! "$PYTHON_CMD" -m venv venv; then
            echo ""
            echo "✗ Failed to create virtual environment."
            echo ""
            echo "This should not happen as venv support was detected."
            echo "Please report this issue."
            echo ""
            exit 1
        fi
        echo "✓ Virtual environment created"
        echo "Activating virtual environment..."
        source venv/bin/activate
        if [[ "$VIRTUAL_ENV" == "" ]]; then
            echo "Error: Failed to activate virtual environment."
            exit 1
        fi
        echo "✓ Virtual environment activated"
        echo ""
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
        echo "  Detected ARM64 Linux"

        # Check if this is a Jetson device
        if [ -f /etc/nv_tegra_release ] || [ -d /usr/local/cuda ]; then
            echo "  Detected NVIDIA Jetson device - installing CUDA-enabled PyTorch"

            # Detect JetPack version
            if [ -f /etc/nv_tegra_release ]; then
                L4T_VERSION=$(head -n 1 /etc/nv_tegra_release | grep -oE 'R[0-9]+' | sed 's/R//')
                if [ -z "$L4T_VERSION" ]; then
                    # Fallback parsing
                    L4T_VERSION=$(cat /etc/nv_tegra_release | grep -oE 'R[0-9]+' | head -1 | sed 's/R//')
                fi
                echo "  L4T Release: R${L4T_VERSION}"
            else
                L4T_VERSION="32"  # Default to older version for safety
            fi

            # Uninstall CPU-only PyTorch if present
            echo "  Removing any existing PyTorch installations..."
            pip uninstall torch torchvision torchaudio -y 2>/dev/null || true

            # Install NVIDIA's PyTorch wheels based on JetPack version
            if [ "$L4T_VERSION" -ge "36" ] 2>/dev/null; then
                # JetPack 6.x (L4T R36.x) - newest
                echo "  Installing PyTorch 2.3.0 for JetPack 6.x (L4T R36)..."

                # PyTorch 2.3.0 with CUDA 12.4 for Python 3.10
                TORCH_URL="https://nvidia.box.com/shared/static/zvultzsmd4iuheykxy17s4l2n91ylpl8.whl"
                TORCHAUDIO_URL="https://nvidia.box.com/shared/static/9si945yrzesspmg9up4ys380lqxjylc3.whl"
                TORCHVISION_URL="https://nvidia.box.com/shared/static/u0ziu01c0kyji4zz3gxam79181nebylf.whl"

                echo "  Downloading PyTorch 2.3.0 with CUDA 12.4..."
                TORCH_WHEEL="torch-2.3.0a0+6a974be.nv24.05.14710581-cp310-cp310-linux_aarch64.whl"
                if wget --no-check-certificate --show-progress "$TORCH_URL" -O "$TORCH_WHEEL"; then
                    # Check if it's a valid wheel file
                    if file "$TORCH_WHEEL" | grep -q "Zip archive" && [[ $(stat -c%s "$TORCH_WHEEL") -gt 100000000 ]]; then
                        echo "  Installing CUDA PyTorch..."
                        if pip install "$TORCH_WHEEL"; then
                            echo "  ✓ CUDA PyTorch 2.3.0 installed successfully!"
                            CUDA_PYTORCH_INSTALLED=true

                            # Install compatible torchvision and torchaudio
                            echo "  Installing torchvision and torchaudio..."
                            TORCHVISION_WHEEL="torchvision-0.18.0a0+6043bc2.nv24.05-cp310-cp310-linux_aarch64.whl"
                            TORCHAUDIO_WHEEL="torchaudio-2.3.0a0+6d5c5b4.nv24.05-cp310-cp310-linux_aarch64.whl"
                            wget --no-check-certificate -q "$TORCHVISION_URL" -O "$TORCHVISION_WHEEL" && pip install --no-deps "$TORCHVISION_WHEEL" && rm "$TORCHVISION_WHEEL" 2>/dev/null || true
                            wget --no-check-certificate -q "$TORCHAUDIO_URL" -O "$TORCHAUDIO_WHEEL" && pip install --no-deps "$TORCHAUDIO_WHEEL" && rm "$TORCHAUDIO_WHEEL" 2>/dev/null || true
                        else
                            echo "  ✗ CUDA PyTorch installation failed, trying CPU version..."
                            pip install torch
                        fi
                    else
                        echo "  ✗ Downloaded file is invalid (size: $(stat -c%s "$TORCH_WHEEL" 2>/dev/null || echo "unknown"))"
                        echo "  Installing CPU PyTorch..."
                        pip install torch
                    fi
                    rm -f "$TORCH_WHEEL"
                else
                    echo "  ✗ Download failed, installing CPU version..."
                    pip install torch
                fi
            elif [ "$L4T_VERSION" -eq "35" ] 2>/dev/null; then
                # JetPack 5.x (L4T R35.x) - exact match only
                echo "  Installing PyTorch for JetPack 5.x (L4T R35)..."
                # Direct download link that works
                TORCH_URL="https://developer.download.nvidia.com/compute/redist/jp/v512/pytorch/torch-2.1.0a0+41361538.nv23.06-cp310-cp310-linux_aarch64.whl"
                echo "  Downloading PyTorch 2.1.0 with CUDA support..."
                if wget --no-check-certificate -O torch_cuda.whl "$TORCH_URL" 2>/dev/null; then
                    if file torch_cuda.whl | grep -q "Zip archive"; then
                        pip install torch_cuda.whl && echo "  ✓ CUDA PyTorch installed" || pip install torch
                    else
                        echo "  Download failed, installing CPU version..."
                        pip install torch
                    fi
                    rm -f torch_cuda.whl
                else
                    echo "  Download failed, installing CPU version..."
                    pip install torch
                fi
            elif [ "$L4T_VERSION" -eq "32" ] 2>/dev/null; then
                # JetPack 4.x (L4T R32.x)
                echo "  Installing PyTorch for JetPack 4.x (L4T R32)..."
                echo "  Note: You may need to manually download PyTorch from NVIDIA"
                echo "  Visit: https://forums.developer.nvidia.com/t/pytorch-for-jetson"
                pip install torch==1.10.0
            else
                # Unknown version
                echo "  Warning: Could not detect L4T version"
                pip install torch
            fi

            # Only install these if we didn't already install CUDA versions
            if [ "$CUDA_PYTORCH_INSTALLED" != "true" ]; then
                # Install torchvision and torchaudio WITHOUT dependencies to avoid reinstalling CPU torch
                echo "  Installing torchvision and torchaudio..."
                pip install --no-deps torchvision torchaudio 2>/dev/null || true
            fi

            # Install torchcrepe WITHOUT dependencies to avoid reinstalling CPU torch
            echo "  Installing torchcrepe..."
            pip install --no-deps torchcrepe

            # Verify CUDA
            if python3 -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
                echo "  ✓ CUDA-enabled PyTorch installed successfully!"
            else
                echo "  ⚠ PyTorch installed but CUDA not detected. Check CUDA installation."
            fi
        else
            # Regular ARM64 (Raspberry Pi, etc)
            echo "  Detected ARM64 Linux (non-Jetson)"
            pip install torch torchaudio torchcrepe
        fi
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
if [ "$CUDA_PYTORCH_INSTALLED" = "true" ]; then
    # Install without torch dependency to avoid overwriting CUDA version
    pip install --no-deps demucs || pip install demucs
    pip install scipy mutagen
else
    pip install demucs scipy mutagen
fi

# Try to install optional packages
echo ""
echo "Installing optional analysis packages..."

# Cython is needed for madmom
pip install Cython 2>/dev/null || true

# Try madmom (optional - provides better music analysis)
echo "  Attempting madmom (onset/beat detection)..."
if pip install madmom --no-build-isolation 2>/dev/null; then
    echo "  ✓ madmom installed successfully"
else
    echo "  ⚠ madmom installation failed - onset/beat features will be unavailable"
fi

# Try essentia (optional - provides better key detection)
echo "  Attempting essentia (key detection)..."
if [[ "$ARCH" == "aarch64" ]] || [[ "$ARCH" == "arm64" ]]; then
    # ARM systems may have limited essentia versions
    pip install 'essentia>=2.1b6.dev234' 2>/dev/null && echo "  ✓ essentia installed successfully" || echo "  ⚠ essentia installation failed - key detection features will be unavailable"
else
    # x86_64 systems can use newer versions
    (pip install 'essentia>=2.1b6.dev374' 2>/dev/null || pip install 'essentia>=2.1b6.dev234' 2>/dev/null) && echo "  ✓ essentia installed successfully" || echo "  ⚠ essentia installation failed - key detection features will be unavailable"
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

$PYTHON_CMD -c "import torch; print('  ✓ PyTorch', torch.__version__)" 2>/dev/null || echo "  ✗ PyTorch"
$PYTHON_CMD -c "import torchaudio; print('  ✓ torchaudio', torchaudio.__version__)" 2>/dev/null || echo "  ✗ torchaudio"
$PYTHON_CMD -c "import demucs; print('  ✓ demucs')" 2>/dev/null || echo "  ✗ demucs"
$PYTHON_CMD -c "import torchcrepe; print('  ✓ torchcrepe (GPU-capable pitch detection)')" 2>/dev/null || echo "  ✗ torchcrepe"
$PYTHON_CMD -c "import madmom; print('  ✓ madmom (onset/beat detection)')" 2>/dev/null || echo "  ⚠ madmom (optional - onset/beat features unavailable)"
$PYTHON_CMD -c "import essentia; print('  ✓ essentia (key detection)')" 2>/dev/null || echo "  ⚠ essentia (optional - key detection features unavailable)"

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