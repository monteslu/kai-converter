"""KAI file packaging utilities."""

import hashlib
import json
import logging
import zipfile
from pathlib import Path
from typing import Dict, List, Any, Optional

from .song_json import KaiJSONEncoder

logger = logging.getLogger(__name__)


class KaiPackager:
    """Handles packaging of KAI files."""
    
    def __init__(self):
        self.required_stems = ["vocals.mp3", "drums.mp3", "bass.mp3", "other.mp3"]
        
    def package_kai(
        self,
        output_path: Path,
        song_json: Dict[str, Any],
        stem_files: Dict[str, Path],
        features_files: Optional[Dict[str, Path]] = None,
        assets_files: Optional[Dict[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Package all components into a .kai file.
        
        Args:
            output_path: Output .kai file path
            song_json: song.json content (may include optional meta section)
            stem_files: Dict mapping stem names to MP3 file paths
            features_files: Optional features/*.json files
            assets_files: Optional assets/* files
            
        Returns:
            Dict with packaging information
        """
        logger.info(f"Packaging KAI file: {output_path}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Validate inputs
        self._validate_inputs(song_json, stem_files)
        
        # Create ZIP file
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as kai_zip:
            # Add song.json at root
            song_json_str = json.dumps(song_json, indent=2, ensure_ascii=False, cls=KaiJSONEncoder)
            kai_zip.writestr("song.json", song_json_str)
            logger.debug("Added song.json to package")
            
            # Add MP3 stems at root - use whatever stems were actually provided
            for stem_key, stem_path in stem_files.items():
                stem_name = f"{stem_key}.mp3"
                kai_zip.write(stem_path, stem_name)
                logger.debug(f"Added {stem_name} to package")
                    
            # Add features/ directory if provided
            if features_files:
                for feature_name, feature_path in features_files.items():
                    archive_path = f"features/{feature_name}"
                    if not archive_path.endswith('.json'):
                        archive_path += '.json'
                    kai_zip.write(feature_path, archive_path)
                    logger.debug(f"Added {archive_path} to package")
                    
            # Add assets/ directory if provided
            if assets_files:
                for asset_name, asset_path in assets_files.items():
                    archive_path = f"assets/{asset_name}"
                    kai_zip.write(asset_path, archive_path)
                    logger.debug(f"Added {archive_path} to package")
                    
        # Compute final file info
        kai_stats = output_path.stat()
        kai_sha256 = self._compute_file_hash(output_path)
        
        package_info = {
            "kai_file": str(output_path),
            "size_bytes": kai_stats.st_size,
            "sha256": kai_sha256,
            "contents": self._list_kai_contents(output_path)
        }
        
        logger.info(f"Successfully packaged KAI file: {output_path} ({kai_stats.st_size:,} bytes)")
        return package_info
        
    def _validate_inputs(self, song_json: Dict[str, Any], stem_files: Dict[str, Path]) -> None:
        """Validate packaging inputs."""
        # Validate song.json structure
        required_fields = ["kai_version", "song", "audio", "timing"]
        for field in required_fields:
            if field not in song_json:
                raise ValueError(f"song.json missing required field: {field}")
                
        # Validate audio profile - support both KAI-4 (4-stem) and KAI-2 (2-stem)
        audio_profile = song_json.get("audio", {}).get("profile")
        if audio_profile not in ["KAI-4", "KAI-2"]:
            raise ValueError(f"Unsupported audio profile: {audio_profile} (expected KAI-4 or KAI-2)")
            
        # Validate stem files exist - support both 4-stem and 2-stem modes
        if "music" in stem_files:
            # 2-stem mode: vocals + music
            required_stem_keys = ["vocals", "music"]
            logger.debug("Using 2-stem mode validation: vocals + music")
        else:
            # 4-stem mode: vocals + drums + bass + other
            required_stem_keys = ["vocals", "drums", "bass", "other"]
            logger.debug("Using 4-stem mode validation: vocals + drums + bass + other")
            
        for stem_key in required_stem_keys:
            if stem_key not in stem_files:
                raise ValueError(f"Missing stem file: {stem_key}")
            stem_path = stem_files[stem_key]
            if not stem_path.exists():
                raise ValueError(f"Stem file does not exist: {stem_path}")
                
        logger.debug("Input validation passed")
        
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
        
    def _list_kai_contents(self, kai_path: Path) -> List[str]:
        """List contents of KAI file."""
        contents = []
        try:
            with zipfile.ZipFile(kai_path, 'r') as kai_zip:
                contents = kai_zip.namelist()
        except Exception as e:
            logger.warning(f"Could not list KAI contents: {e}")
        return sorted(contents)
        
    def validate_kai_file(self, kai_path: Path) -> Dict[str, Any]:
        """
        Validate a KAI file according to spec.
        
        Args:
            kai_path: Path to .kai file
            
        Returns:
            Dict with validation results
        """
        logger.info(f"Validating KAI file: {kai_path}")
        
        validation_result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "contents": []
        }
        
        if not kai_path.exists():
            validation_result["errors"].append("KAI file does not exist")
            return validation_result
            
        try:
            with zipfile.ZipFile(kai_path, 'r') as kai_zip:
                contents = kai_zip.namelist()
                validation_result["contents"] = contents
                
                # Check for song.json at root
                if "song.json" not in contents:
                    validation_result["errors"].append("Missing song.json at root")
                else:
                    # Validate song.json content
                    try:
                        song_json_str = kai_zip.read("song.json").decode('utf-8')
                        song_json = json.loads(song_json_str)
                        
                        # Check kai_version
                        if song_json.get("kai_version") != "1.0":
                            validation_result["errors"].append(
                                f"Invalid kai_version: {song_json.get('kai_version')}"
                            )
                            
                        # Check audio profile and sources
                        audio = song_json.get("audio", {})
                        profile = audio.get("profile")
                        
                        if profile == "KAI-4":
                            # Check for required MP3 stems
                            for stem_name in self.required_stems:
                                if stem_name not in contents:
                                    validation_result["errors"].append(
                                        f"Missing required stem: {stem_name}"
                                    )
                                    
                            # Check sources list matches files
                            sources = audio.get("sources", [])
                            expected_files = {source["file"] for source in sources}
                            missing_files = expected_files - set(contents)
                            if missing_files:
                                validation_result["errors"].append(
                                    f"Missing files referenced in sources: {missing_files}"
                                )
                        elif profile == "KAI-2":
                            # Check for required MP3 stems for 2-stem mode
                            required_2stem = ["vocals.mp3", "music.mp3"]
                            for stem_name in required_2stem:
                                if stem_name not in contents:
                                    validation_result["errors"].append(
                                        f"Missing required stem for KAI-2: {stem_name}"
                                    )
                            
                            # Check sources list matches files
                            sources = audio.get("sources", [])
                            expected_files = {source["file"] for source in sources}
                            missing_files = expected_files - set(contents)
                            if missing_files:
                                validation_result["errors"].append(
                                    f"Missing files referenced in sources: {missing_files}"
                                )
                        else:
                            validation_result["errors"].append(
                                f"Unsupported audio profile: {profile}"
                            )
                            
                        # Check encoder_delay_samples exists
                        if "encoder_delay_samples" not in audio:
                            validation_result["errors"].append(
                                "Missing audio.encoder_delay_samples"
                            )
                            
                        # Check timing reference exists
                        timing = song_json.get("timing", {})
                        if "reference" not in timing or "offset_sec" not in timing:
                            validation_result["errors"].append(
                                "Missing timing.reference or timing.offset_sec"
                            )
                            
                    except json.JSONDecodeError as e:
                        validation_result["errors"].append(
                            f"Invalid JSON in song.json: {e}"
                        )
                    except Exception as e:
                        validation_result["errors"].append(
                            f"Error reading song.json: {e}"
                        )
                        
                # Check for optional components
                has_features = any(name.startswith("features/") for name in contents)
                has_assets = any(name.startswith("assets/") for name in contents)
                has_meta = "meta" in song_json
                
                if has_features:
                    validation_result["warnings"].append("Contains features/ directory")
                if has_assets:
                    validation_result["warnings"].append("Contains assets/ directory")
                if has_meta:
                    validation_result["warnings"].append("Contains optional meta section")
                    
        except zipfile.BadZipFile:
            validation_result["errors"].append("Not a valid ZIP file")
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {e}")
            
        # Set valid flag
        validation_result["valid"] = len(validation_result["errors"]) == 0
        
        if validation_result["valid"]:
            logger.info("KAI file validation passed")
        else:
            logger.error(f"KAI file validation failed: {validation_result['errors']}")
            
        return validation_result
        
    def extract_kai_info(self, kai_path: Path) -> Dict[str, Any]:
        """
        Extract basic information from KAI file.
        
        Args:
            kai_path: Path to .kai file
            
        Returns:
            Dict with KAI file information
        """
        info = {
            "file_path": str(kai_path),
            "file_size": 0,
            "valid": False,
            "song_info": {},
            "audio_info": {},
            "contents": []
        }
        
        if not kai_path.exists():
            return info
            
        info["file_size"] = kai_path.stat().st_size
        
        try:
            with zipfile.ZipFile(kai_path, 'r') as kai_zip:
                info["contents"] = kai_zip.namelist()
                
                if "song.json" in info["contents"]:
                    song_json_str = kai_zip.read("song.json").decode('utf-8')
                    song_json = json.loads(song_json_str)
                    
                    info["song_info"] = song_json.get("song", {})
                    info["audio_info"] = song_json.get("audio", {})
                    info["valid"] = True
                    
        except Exception as e:
            logger.error(f"Error extracting KAI info: {e}")
            
        return info