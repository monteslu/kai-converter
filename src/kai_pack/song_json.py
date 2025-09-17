"""Song.json generation for KAI format."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class KaiJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles ID3TimeStamp and other special objects."""
    
    def default(self, obj):
        # Handle ID3TimeStamp objects by converting to string
        if hasattr(obj, '__class__') and 'ID3TimeStamp' in str(obj.__class__):
            return str(obj)
        # Handle other non-serializable objects
        try:
            return str(obj)
        except:
            return super().default(obj)


class SongJsonGenerator:
    """Generates song.json for KAI format."""
    
    def __init__(self):
        self.kai_version = "1.0"
        
    def generate(
        self,
        metadata: Dict[str, Any],
        audio_info: Dict[str, Any],
        alignment_data: Dict[str, Any],
        stem_info: Dict[str, Any],
        encoder_delay: int = 1105,
        processing_info: Optional[Dict[str, Any]] = None,
        analysis_features: Optional[Dict[str, Any]] = None,
        include_meta: bool = True,
        include_id3_raw: bool = True
    ) -> Dict[str, Any]:
        """
        Generate complete song.json structure.
        
        Args:
            metadata: Normalized metadata from MetadataExtractor
            audio_info: Audio technical information
            alignment_data: Lyrics alignment results
            stem_info: Information about separated stems
            encoder_delay: MP3 encoder delay in samples
            processing_info: Optional processing provenance information
            analysis_features: Optional analysis features including key detection
            include_meta: Whether to include optional meta section
            include_id3_raw: Whether to include raw ID3 frames in meta
            
        Returns:
            Complete song.json dict structure
        """
        logger.info("Generating song.json")
        
        song_json = {
            "kai_version": self.kai_version,
            "song": self._build_song_section(metadata, audio_info, analysis_features),
            "audio": self._build_audio_section(stem_info, encoder_delay),
            "timing": self._build_timing_section(alignment_data),
            "meter": self._build_meter_section(),
            "singers": self._build_singers_section(),
            "lines": alignment_data.get("lines", [])
        }

        # Add vocal_pitch if available in analysis features
        if analysis_features and "vocal_pitch" in analysis_features:
            song_json["vocal_pitch"] = analysis_features["vocal_pitch"]
        
        # Add optional meta section if requested
        if include_meta and processing_info:
            song_json["meta"] = self._build_meta_section(
                metadata, processing_info, include_id3_raw
            )
        
        logger.info(f"Generated song.json with {len(song_json['lines'])} lines")
        return song_json
        
    def _build_song_section(self, metadata: Dict[str, Any], audio_info: Dict[str, Any], analysis_features: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build the song metadata section."""
        song_meta = metadata.get("song", {})
        
        # Handle track/disc numbers
        track_info = song_meta.get("track", {"no": 1, "of": 0})
        disc_info = song_meta.get("disc", {"no": 1, "of": 1})
        
        # Handle MusicBrainz IDs
        mb_ids = song_meta.get("musicbrainz", {})
        if not isinstance(mb_ids, dict):
            mb_ids = {"recording_id": "", "track_id": "", "release_id": ""}
        
        # Extract key detection from analysis features
        key_info = "unknown"
        key_confidence = 0.0
        if analysis_features and "key_detection" in analysis_features:
            key_data = analysis_features["key_detection"]
            key_info = key_data.get("key", "unknown")
            key_confidence = key_data.get("confidence", 0.0)
            
        song_section = {
            "title": song_meta.get("title", "Unknown Title"),
            "artist": song_meta.get("artist", "Unknown Artist"),
            "album": song_meta.get("album", ""),
            "album_artist": song_meta.get("album_artist", ""),
            "track": {
                "no": track_info.get("no", 1),
                "of": track_info.get("of", 0)
            },
            "disc": {
                "no": disc_info.get("no", 1), 
                "of": disc_info.get("of", 1)
            },
            "year": song_meta.get("year", ""),
            "genre": song_meta.get("genre", ""),
            "key": key_info,
            "isrc": song_meta.get("isrc", ""),
            "musicbrainz": {
                "recording_id": mb_ids.get("recording_id", ""),
                "track_id": mb_ids.get("track_id", ""),
                "release_id": mb_ids.get("release_id", "")
            },
            "comment": song_meta.get("comment", ""),
            "source_filename": song_meta.get("source_filename", ""),
            "duration_sec": audio_info.get("duration_seconds", 0.0),
            "sample_rate": audio_info.get("target_sample_rate", 44100),
            "channels": 2
        }
        
        return song_section
        
    def _build_audio_section(self, stem_info: Dict[str, Any], encoder_delay: int) -> Dict[str, Any]:
        """Build the audio configuration section."""
        # Detect which stems are available - if 'music' exists, we're in 2-stem mode
        if 'music' in stem_info:
            # 2-stem mode: vocals + music
            sources = [
                {"id": "vocals", "file": "vocals.mp3", "role": "vocals", "type": "stem", "gain_db": 0.0},
                {"id": "music", "file": "music.mp3", "role": "music", "type": "stem", "gain_db": 0.0}
            ]
            profile = "KAI-2"
            
            # Simplified presets for 2-stem
            presets = [
                {
                    "id": "karaoke",
                    "levels": {"vocals": -120}  # Mute vocals for karaoke
                }
            ]
        else:
            # 4-stem mode: vocals + drums + bass + other
            sources = [
                {"id": "vocals", "file": "vocals.mp3", "role": "vocals", "type": "stem", "gain_db": 0.0},
                {"id": "drums", "file": "drums.mp3", "role": "drums", "type": "stem", "gain_db": 0.0},
                {"id": "bass", "file": "bass.mp3", "role": "bass", "type": "stem", "gain_db": 0.0},
                {"id": "other", "file": "other.mp3", "role": "other", "type": "stem", "gain_db": 0.0}
            ]
            profile = "KAI-4"
            
            # Standard presets for KAI-4
            presets = [
                {
                    "id": "karaoke",
                    "levels": {"vocals": -120}  # Mute vocals for karaoke
                },
                {
                    "id": "drums_only", 
                    "solo": ["drums"]
                },
                {
                    "id": "band_only",
                    "levels": {"vocals": -120}
                }
            ]
        
        audio_section = {
            "profile": profile,
            "encoder_delay_samples": encoder_delay,
            "sources": sources,
            "presets": presets
        }
        
        return audio_section
        
    def _build_timing_section(self, alignment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build the timing reference section."""
        return {
            "reference": alignment_data.get("reference", "aligned_to_vocals_wav"),
            "offset_sec": alignment_data.get("offset_sec", 0.0)
        }
        
    def _build_meter_section(self) -> Dict[str, Any]:
        """Build the meter section with basic defaults."""
        # TODO: Extract actual BPM from tempo analysis
        return {
            "bpm": 100.0  # Default, should be extracted from analysis
        }
        
    def _build_singers_section(self) -> List[Dict[str, Any]]:
        """Build the singers section."""
        # For MVP, single lead singer
        return [
            {
                "id": "A",
                "name": "Lead",
                "guide": "vocals.mp3"
            }
        ]
        
    def save_json(self, song_data: Dict[str, Any], output_path: Path) -> None:
        """Save song.json to file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(song_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved song.json to {output_path}")
        
    def validate_json(self, song_data: Dict[str, Any]) -> bool:
        """Validate song.json structure."""
        required_fields = [
            "kai_version", "song", "audio", "timing", "meter", "singers", "lines"
        ]
        
        for field in required_fields:
            if field not in song_data:
                logger.error(f"Missing required field: {field}")
                return False
                
        # Validate audio section
        audio = song_data.get("audio", {})
        if audio.get("profile") not in ["KAI-4", "KAI-2"]:
            logger.error("Only KAI-4 and KAI-2 profiles supported")
            return False
            
        sources = audio.get("sources", [])
        profile = audio.get("profile")
        
        if profile == "KAI-2":
            expected_roles = {"vocals", "music"}
        else:  # KAI-4
            expected_roles = {"vocals", "drums", "bass", "other"}
            
        found_roles = {source["role"] for source in sources}
        
        if found_roles != expected_roles:
            logger.error(f"Expected roles for {profile}: {expected_roles}, found {found_roles}")
            return False
            
        # Validate kai_version
        if song_data.get("kai_version") != self.kai_version:
            logger.error(f"Unexpected kai_version: {song_data.get('kai_version')}")
            return False
            
        logger.info("song.json validation passed")
        return True
        
    def _build_meta_section(
        self, 
        metadata: Dict[str, Any],
        processing_info: Dict[str, Any],
        include_id3_raw: bool = True
    ) -> Dict[str, Any]:
        """Build the optional meta section with provenance data."""
        from datetime import datetime
        
        meta = {
            "created_utc": processing_info.get("timestamp", datetime.utcnow().isoformat() + "Z"),
            "source": {
                "filename": processing_info.get("source_filename", ""),
                "sha256": processing_info.get("source_sha256", "")
            }
        }
        
        # Add ID3 information if available
        id3_info = metadata.get("id3", {})
        if id3_info:
            meta["id3"] = {
                "version": id3_info.get("version", "unknown"),
                "normalized": id3_info.get("normalized", {})
            }
            
            # Include raw ID3 frames if requested
            if include_id3_raw and "raw" in id3_info:
                meta["id3"]["raw"] = id3_info["raw"]
        
        # Add processing information
        if "processing" in processing_info:
            meta["processing"] = processing_info["processing"]
            
        # Add file hashes
        if "outputs" in processing_info:
            meta["hashes"] = processing_info["outputs"]
            
        return meta


# ManifestGenerator is no longer needed - functionality moved to SongJsonGenerator