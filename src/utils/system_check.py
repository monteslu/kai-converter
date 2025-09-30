#!/usr/bin/env python3
"""
System check utilities for detecting installed components and capabilities.
Used by GUI to determine what needs to be downloaded/installed.
"""

import json
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
import os


def check_ffmpeg() -> Dict[str, Any]:
    """Check if ffmpeg is available and get version info."""
    # Check if FFMPEG_PATH environment variable is set (from Electron)
    custom_path = os.environ.get('FFMPEG_PATH')
    if custom_path and Path(custom_path).exists():
        try:
            version = subprocess.check_output(
                [custom_path, '-version'],
                stderr=subprocess.STDOUT,
                text=True
            )
            return {
                "available": True,
                "path": custom_path,
                "source": "bundled",
                "version": parse_ffmpeg_version(version)
            }
        except Exception as e:
            pass

    # Check system PATH
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        try:
            version = subprocess.check_output(
                ['ffmpeg', '-version'],
                stderr=subprocess.STDOUT,
                text=True
            )
            return {
                "available": True,
                "path": ffmpeg_path,
                "source": "system",
                "version": parse_ffmpeg_version(version)
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    return {"available": False, "error": "ffmpeg not found in PATH"}


def parse_ffmpeg_version(version_output: str) -> str:
    """Parse ffmpeg version from output."""
    try:
        first_line = version_output.split('\n')[0]
        # Extract version like "ffmpeg version 6.1.1"
        parts = first_line.split()
        if len(parts) >= 3:
            return parts[2]
    except Exception:
        pass
    return "unknown"


def check_ytdlp() -> Dict[str, Any]:
    """Check if yt-dlp is available."""
    ytdlp_path = shutil.which('yt-dlp')
    if ytdlp_path:
        try:
            version = subprocess.check_output(
                ['yt-dlp', '--version'],
                stderr=subprocess.STDOUT,
                text=True
            ).strip()
            return {
                "available": True,
                "path": ytdlp_path,
                "source": "system",
                "version": version
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    return {"available": False, "error": "yt-dlp not found in PATH"}


def check_pytorch() -> Dict[str, Any]:
    """Check PyTorch installation and capabilities."""
    try:
        import torch

        result = {
            "available": True,
            "version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "mps_available": torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False,
            "device": "cpu"
        }

        if result["cuda_available"]:
            result["device"] = "cuda"
            result["cuda_version"] = torch.version.cuda
            result["cuda_device_count"] = torch.cuda.device_count()
            result["cuda_device_name"] = torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else None
        elif result["mps_available"]:
            result["device"] = "mps"

        return result

    except ImportError:
        return {"available": False, "error": "PyTorch not installed"}
    except Exception as e:
        return {"available": False, "error": str(e)}


def check_whisper_models() -> Dict[str, Any]:
    """Check which Whisper models are downloaded."""
    try:
        import whisper

        # Check default cache location
        whisper_cache = Path.home() / ".cache" / "whisper"

        # Also check custom cache if WHISPER_CACHE_DIR is set
        custom_cache = os.environ.get('WHISPER_CACHE_DIR')
        if custom_cache:
            whisper_cache = Path(custom_cache)

        models = []
        total_size = 0

        if whisper_cache.exists():
            for model_file in whisper_cache.glob("*.pt"):
                size = model_file.stat().st_size
                models.append({
                    "name": model_file.stem,
                    "size_bytes": size,
                    "size_mb": round(size / (1024 * 1024), 1),
                    "path": str(model_file)
                })
                total_size += size

        return {
            "available": True,
            "cache_dir": str(whisper_cache),
            "models": models,
            "total_size_mb": round(total_size / (1024 * 1024), 1),
            "available_model_names": whisper.available_models()
        }

    except ImportError:
        return {"available": False, "error": "Whisper not installed"}
    except Exception as e:
        return {"available": False, "error": str(e)}


def check_demucs_models() -> Dict[str, Any]:
    """Check which Demucs models are downloaded."""
    try:
        from demucs.pretrained import REMOTE_ROOT, _parse_remote_files

        # Demucs models are cached in torch hub
        torch_hub = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"

        models = []
        total_size = 0

        if torch_hub.exists():
            # Look for demucs model files
            for model_file in torch_hub.glob("*.th"):
                if 'demucs' in model_file.name.lower() or 'htdemucs' in model_file.name.lower():
                    size = model_file.stat().st_size
                    models.append({
                        "name": model_file.stem,
                        "size_bytes": size,
                        "size_mb": round(size / (1024 * 1024), 1),
                        "path": str(model_file)
                    })
                    total_size += size

        return {
            "available": True,
            "cache_dir": str(torch_hub),
            "models": models,
            "total_size_mb": round(total_size / (1024 * 1024), 1)
        }

    except ImportError:
        return {"available": False, "error": "Demucs not installed"}
    except Exception as e:
        return {"available": False, "error": str(e)}


def check_gpu_info() -> Dict[str, Any]:
    """Detect GPU capabilities."""
    gpu_info = {
        "nvidia": False,
        "amd": False,
        "apple_silicon": False,
        "details": None
    }

    # Check for NVIDIA GPU
    nvidia_smi = shutil.which('nvidia-smi')
    if nvidia_smi:
        try:
            output = subprocess.check_output(
                [nvidia_smi, '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'],
                stderr=subprocess.STDOUT,
                text=True
            )
            gpu_info["nvidia"] = True
            gpu_info["details"] = output.strip()
        except Exception:
            pass

    # Check for Apple Silicon
    if sys.platform == 'darwin':
        try:
            output = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True)
            if 'Apple' in output:
                gpu_info["apple_silicon"] = True
                gpu_info["details"] = output.strip()
        except Exception:
            pass

    return gpu_info


def check_disk_space(path: str = None) -> Dict[str, Any]:
    """Check available disk space."""
    if path is None:
        path = str(Path.home())

    try:
        import shutil
        usage = shutil.disk_usage(path)

        return {
            "path": path,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round((usage.used / usage.total) * 100, 1)
        }
    except Exception as e:
        return {"error": str(e)}


def check_llm_providers() -> Dict[str, Any]:
    """Check which LLM providers are configured."""
    providers = {}

    # Check OpenAI
    providers["openai"] = {
        "api_key_set": bool(os.environ.get("OPENAI_API_KEY")),
        "available": False
    }
    if providers["openai"]["api_key_set"]:
        try:
            import openai
            providers["openai"]["available"] = True
        except ImportError:
            pass

    # Check Anthropic
    providers["anthropic"] = {
        "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "available": False
    }
    if providers["anthropic"]["api_key_set"]:
        try:
            import anthropic
            providers["anthropic"]["available"] = True
        except ImportError:
            pass

    # Check Google Gemini
    providers["gemini"] = {
        "api_key_set": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "available": False
    }
    if providers["gemini"]["api_key_set"]:
        try:
            import google.generativeai
            providers["gemini"]["available"] = True
        except ImportError:
            pass

    # Check LM Studio (local)
    providers["lmstudio"] = {
        "available": False,
        "url": os.environ.get("LM_STUDIO_URL", "http://localhost:1234")
    }
    try:
        import requests
        response = requests.get(f"{providers['lmstudio']['url']}/v1/models", timeout=2)
        if response.status_code == 200:
            providers["lmstudio"]["available"] = True
            providers["lmstudio"]["models"] = response.json().get("data", [])
    except Exception:
        pass

    return providers


def get_system_info() -> Dict[str, Any]:
    """Get comprehensive system information."""
    return {
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "platform": sys.platform
        },
        "ffmpeg": check_ffmpeg(),
        "ytdlp": check_ytdlp(),
        "pytorch": check_pytorch(),
        "whisper": check_whisper_models(),
        "demucs": check_demucs_models(),
        "gpu": check_gpu_info(),
        "disk": check_disk_space(),
        "llm_providers": check_llm_providers()
    }


def calculate_download_requirements(requested_components: List[str]) -> Dict[str, Any]:
    """Calculate what needs to be downloaded based on current system state."""
    current_state = get_system_info()

    downloads = []
    total_size_mb = 0

    # Check each requested component
    if "ffmpeg" in requested_components and not current_state["ffmpeg"]["available"]:
        size = 100  # ~100MB
        downloads.append({
            "component": "ffmpeg",
            "size_mb": size,
            "required": True,
            "reason": "Required for audio encoding"
        })
        total_size_mb += size

    if "pytorch_cpu" in requested_components and not current_state["pytorch"]["available"]:
        size = 2000  # ~2GB
        downloads.append({
            "component": "pytorch_cpu",
            "size_mb": size,
            "required": True,
            "reason": "Required for AI processing"
        })
        total_size_mb += size

    if "pytorch_cuda" in requested_components and current_state["gpu"]["nvidia"]:
        if not current_state["pytorch"]["available"] or not current_state["pytorch"]["cuda_available"]:
            size = 6000  # ~6GB
            downloads.append({
                "component": "pytorch_cuda",
                "size_mb": size,
                "required": False,
                "reason": "GPU acceleration (NVIDIA detected)"
            })
            total_size_mb += size

    # Check Whisper models
    available_whisper = [m["name"] for m in current_state["whisper"].get("models", [])]
    whisper_sizes = {"tiny": 75, "base": 142, "small": 244, "medium": 769, "large": 1550}

    for model in ["tiny", "base", "small", "medium", "large"]:
        if f"whisper_{model}" in requested_components and model not in available_whisper:
            size = whisper_sizes[model]
            downloads.append({
                "component": f"whisper_{model}",
                "size_mb": size,
                "required": model == "small",  # Small is recommended
                "reason": f"Whisper {model} model for transcription"
            })
            total_size_mb += size

    return {
        "downloads": downloads,
        "total_size_mb": total_size_mb,
        "total_size_gb": round(total_size_mb / 1024, 2),
        "required_downloads": [d for d in downloads if d["required"]],
        "optional_downloads": [d for d in downloads if not d["required"]]
    }


def main():
    """Command-line interface for system check."""
    import argparse

    parser = argparse.ArgumentParser(description="Check KAI Converter system requirements")
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--component', choices=['ffmpeg', 'pytorch', 'whisper', 'demucs', 'gpu', 'all'],
                       default='all', help='Check specific component')

    args = parser.parse_args()

    if args.component == 'all':
        info = get_system_info()
    elif args.component == 'ffmpeg':
        info = check_ffmpeg()
    elif args.component == 'pytorch':
        info = check_pytorch()
    elif args.component == 'whisper':
        info = check_whisper_models()
    elif args.component == 'demucs':
        info = check_demucs_models()
    elif args.component == 'gpu':
        info = check_gpu_info()

    if args.json:
        print(json.dumps(info, indent=2))
    else:
        # Pretty print for humans
        print("KAI Converter System Check")
        print("=" * 50)
        print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()