"""ID3 metadata ingestion and processing."""

import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, Union

from mutagen import File
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TRCK, TPOS, TDRC, TCON, TSRC, COMM
from mutagen.id3 import TXXX, UFID


logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Handles ID3 metadata extraction and normalization."""
    
    def __init__(self):
        # Mapping of common ID3 frames to canonical fields
        self.id3_mapping = {
            # Text frames
            "TIT2": "title",
            "TPE1": "artist", 
            "TALB": "album",
            "TPE2": "album_artist",
            "TRCK": "track",
            "TPOS": "disc",
            "TDRC": "date",
            "TDAT": "date",  # v2.3
            "TYER": "year",  # v2.3
            "TCON": "genre",
            "TSRC": "isrc",
            "COMM": "comment",
            
            # User defined text
            "TXXX:MusicBrainz Recording Id": "musicbrainz_recording_id",
            "TXXX:MusicBrainz Track Id": "musicbrainz_track_id", 
            "TXXX:MusicBrainz Release Id": "musicbrainz_release_id",
            "TXXX:MusicBrainz Artist Id": "musicbrainz_artist_id",
            
            # Unique file identifiers
            "UFID:http://musicbrainz.org": "musicbrainz_recording_id"
        }
        
    def extract_metadata(
        self, 
        audio_file: Path,
        overrides: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Extract and normalize metadata from audio file.
        
        Args:
            audio_file: Path to audio file
            overrides: Optional metadata overrides
            
        Returns:
            Dict with normalized metadata and raw ID3 snapshot
        """
        logger.info(f"Extracting metadata from {audio_file}")
        
        # Load file with mutagen
        try:
            audio_meta = File(audio_file)
            if audio_meta is None:
                raise ValueError("Could not load metadata")
        except Exception as e:
            logger.warning(f"Failed to load metadata: {e}")
            audio_meta = {}
            
        # Extract raw ID3 data
        raw_id3 = self._extract_raw_id3(audio_meta)
        
        # Normalize to canonical fields
        normalized = self._normalize_metadata(raw_id3, audio_file)
        
        # Apply overrides
        if overrides:
            normalized.update(overrides)
            logger.info(f"Applied metadata overrides: {list(overrides.keys())}")
            
        # Create full metadata structure
        metadata = {
            "song": normalized,
            "id3": {
                "version": raw_id3.get("version", "unknown"),
                "raw": raw_id3.get("frames", {}),
                "normalized": normalized
            }
        }
        
        return metadata
        
    def _extract_raw_id3(self, audio_meta: Any) -> Dict[str, Any]:
        """Extract raw ID3 frame data."""
        raw_data = {
            "version": "unknown",
            "frames": {}
        }
        
        if hasattr(audio_meta, "tags") and audio_meta.tags:
            tags = audio_meta.tags
            
            # Determine ID3 version
            if hasattr(tags, "version"):
                version = tags.version
                raw_data["version"] = f"ID3v{version[0]}.{version[1]}"
            
            # Extract all frames
            for key, value in tags.items():
                if hasattr(value, 'text'):
                    # Text frames
                    raw_data["frames"][key] = value.text[0] if value.text else ""
                elif key.startswith('COMM') and hasattr(value, 'text'):
                    # Comment frames - extract text content
                    raw_data["frames"]["COMM"] = value.text[0] if value.text else ""
                elif hasattr(value, 'data'):
                    # Binary frames (like UFID)
                    raw_data["frames"][key] = value.data.hex() if value.data else ""
                else:
                    # Other frame types
                    raw_data["frames"][key] = str(value)
                    
        return raw_data
        
    def _normalize_metadata(
        self, 
        raw_id3: Dict[str, Any], 
        audio_file: Path
    ) -> Dict[str, Any]:
        """Normalize raw ID3 data to canonical fields."""
        frames = raw_id3.get("frames", {})
        normalized = {}
        
        # Extract basic fields
        for frame_key, canonical_key in self.id3_mapping.items():
            if frame_key in frames:
                value = frames[frame_key]
                if value:
                    normalized[canonical_key] = self._clean_text(value)
                    
        # Handle special cases
        self._normalize_track_disc(frames, normalized)
        self._normalize_date(frames, normalized) 
        self._normalize_musicbrainz(frames, normalized)
        
        # Apply fallbacks
        self._apply_fallbacks(normalized, audio_file)
        
        # Add technical info (will be filled by audio processor)
        normalized.update({
            "source_filename": audio_file.name,
            "duration_sec": 0.0,  # Filled later
            "sample_rate": 44100,  # Filled later  
            "channels": 2  # Filled later
        })
        
        return normalized
        
    def _normalize_track_disc(
        self, 
        frames: Dict[str, str], 
        normalized: Dict[str, Any]
    ) -> None:
        """Normalize track and disc numbers."""
        # Track number (TRCK)
        if "TRCK" in frames:
            track_str = frames["TRCK"]
            match = re.match(r"(\d+)(?:/(\d+))?", track_str)
            if match:
                track_no = int(match.group(1))
                track_of = int(match.group(2)) if match.group(2) else None
                normalized["track"] = {
                    "no": track_no,
                    "of": track_of or 0
                }
                
        # Disc number (TPOS)
        if "TPOS" in frames:
            disc_str = frames["TPOS"]
            match = re.match(r"(\d+)(?:/(\d+))?", disc_str)
            if match:
                disc_no = int(match.group(1))
                disc_of = int(match.group(2)) if match.group(2) else None
                normalized["disc"] = {
                    "no": disc_no,
                    "of": disc_of or 1
                }
                
    def _normalize_date(
        self, 
        frames: Dict[str, str], 
        normalized: Dict[str, Any]
    ) -> None:
        """Normalize date/year fields."""
        year = None
        
        # Try TDRC (v2.4 date)
        if "TDRC" in frames:
            date_str = str(frames["TDRC"])  # Convert ID3TimeStamp to string
            match = re.match(r"(\d{4})", date_str)
            if match:
                year = match.group(1)
                
        # Try TYER (v2.3 year)
        elif "TYER" in frames:
            year_str = str(frames["TYER"])  # Convert ID3TimeStamp to string
            match = re.match(r"(\d{4})", year_str)
            if match:
                year = match.group(1)
                
        # Try TDAT + TYER combination (v2.3)
        elif "TDAT" in frames and "TYER" in frames:
            year = str(frames["TYER"])
            
        if year:
            normalized["year"] = year
            
    def _normalize_musicbrainz(
        self, 
        frames: Dict[str, str], 
        normalized: Dict[str, Any]
    ) -> None:
        """Extract MusicBrainz IDs."""
        mb_ids = {}
        
        # Check TXXX frames for MusicBrainz IDs
        for key, value in frames.items():
            if key.startswith("TXXX:MusicBrainz"):
                if "Recording Id" in key:
                    mb_ids["recording_id"] = value
                elif "Track Id" in key:
                    mb_ids["track_id"] = value
                elif "Release Id" in key:
                    mb_ids["release_id"] = value
                elif "Artist Id" in key:
                    mb_ids["artist_id"] = value
                    
        # Check UFID frame
        ufid_key = "UFID:http://musicbrainz.org"
        if ufid_key in frames:
            mb_ids["recording_id"] = frames[ufid_key]
            
        if mb_ids:
            normalized["musicbrainz"] = mb_ids
        else:
            # Empty placeholders as per spec
            normalized["musicbrainz"] = {
                "recording_id": "",
                "track_id": "", 
                "release_id": ""
            }
            
    def _apply_fallbacks(
        self, 
        normalized: Dict[str, Any], 
        audio_file: Path
    ) -> None:
        """Apply fallback values for missing fields."""
        # Title fallback: use filename stem
        if "title" not in normalized or not normalized["title"]:
            normalized["title"] = audio_file.stem
            logger.info(f"Using filename as title: {audio_file.stem}")
            
        # Artist fallback
        if "artist" not in normalized or not normalized["artist"]:
            normalized["artist"] = "Unknown Artist"
            logger.info("Using fallback artist: Unknown Artist")
            
        # Ensure track/disc defaults
        if "track" not in normalized:
            normalized["track"] = {"no": 1, "of": 1}
        if "disc" not in normalized:
            normalized["disc"] = {"no": 1, "of": 1}
            
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text fields."""
        if not isinstance(text, str):
            text = str(text)
            
        # Remove null bytes and normalize whitespace
        text = text.replace('\x00', '').strip()
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        
        return text
        
    def create_manifest_metadata(
        self, 
        normalized: Dict[str, Any],
        raw_id3: Dict[str, Any],
        source_file: Path,
        processing_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create manifest.json metadata structure."""
        return {
            "kai_version": "1.0",
            "created_utc": processing_info.get("timestamp", ""),
            "source": {
                "filename": source_file.name,
                "sha256": processing_info.get("source_sha256", "")
            },
            "id3": {
                "version": raw_id3.get("version", "unknown"),
                "raw": raw_id3.get("frames", {}),
                "normalized": normalized
            },
            "processing": processing_info.get("processing", {}),
            "outputs": processing_info.get("outputs", {})
        }