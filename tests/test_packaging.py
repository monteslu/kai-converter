"""Tests for KAI packaging functionality."""

import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from kai_pack.packaging import KaiPackager


class TestKaiPackager:
    """Test KAI file packaging and validation."""
    
    @pytest.fixture
    def packager(self):
        return KaiPackager()
        
    @pytest.fixture
    def sample_song_json(self):
        return {
            "kai_version": "1.0",
            "song": {
                "title": "Test Song",
                "artist": "Test Artist",
                "album": "",
                "album_artist": "",
                "track": {"no": 1, "of": 1},
                "disc": {"no": 1, "of": 1},
                "year": "2024",
                "genre": "",
                "isrc": "",
                "musicbrainz": {
                    "recording_id": "",
                    "track_id": "",
                    "release_id": ""
                },
                "source_filename": "test.mp3",
                "duration_sec": 180.0,
                "sample_rate": 44100,
                "channels": 2
            },
            "audio": {
                "profile": "KAI-4",
                "encoder_delay_samples": 1105,
                "sources": [
                    {"id": "vocals", "file": "vocals.mp3", "role": "vocals", "gain_db": 0.0},
                    {"id": "drums", "file": "drums.mp3", "role": "drums", "gain_db": 0.0},
                    {"id": "bass", "file": "bass.mp3", "role": "bass", "gain_db": 0.0},
                    {"id": "other", "file": "other.mp3", "role": "other", "gain_db": 0.0}
                ],
                "presets": [
                    {"id": "karaoke", "levels": {"vocals": -120}}
                ]
            },
            "timing": {
                "reference": "aligned_to_vocals_wav",
                "offset_sec": 0.0
            },
            "meter": {"bpm": 120.0},
            "singers": [{"id": "A", "name": "Lead", "guide": "vocals.mp3"}],
            "lines": [],
            "meta": {
                "created_utc": "2024-01-01T00:00:00Z",
                "source": {
                    "filename": "test.mp3",
                    "sha256": "abc123"
                }
            }
        }
        
    @pytest.fixture
    def temp_stems(self):
        """Create temporary MP3 stem files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            stem_files = {}
            for stem in ["vocals", "drums", "bass", "other"]:
                stem_file = temp_path / f"{stem}.mp3"
                # Create a minimal MP3-like file (not valid MP3, just for testing)
                stem_file.write_bytes(b"fake mp3 content")
                stem_files[stem] = stem_file
                
            yield stem_files
            
    def test_package_basic_kai(self, packager, sample_song_json, temp_stems):
        """Test basic KAI file packaging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test.kai"
            
            package_info = packager.package_kai(
                output_path=output_path,
                song_json=sample_song_json,
                stem_files=temp_stems
            )
            
            assert output_path.exists()
            assert package_info["kai_file"] == str(output_path)
            assert package_info["size_bytes"] > 0
            assert "sha256" in package_info
            assert "contents" in package_info
            
            # Check ZIP contents
            with zipfile.ZipFile(output_path, 'r') as kai_zip:
                contents = kai_zip.namelist()
                assert "song.json" in contents
                assert "vocals.mp3" in contents
                assert "drums.mp3" in contents
                assert "bass.mp3" in contents
                assert "other.mp3" in contents
                
    def test_validate_valid_kai(self, packager, sample_song_json, temp_stems):
        """Test validation of valid KAI file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test.kai"
            
            packager.package_kai(
                output_path=output_path,
                song_json=sample_song_json,
                stem_files=temp_stems
            )
            
            validation = packager.validate_kai_file(output_path)
            assert validation["valid"] == True
            assert len(validation["errors"]) == 0
            
    def test_validate_missing_stems(self, packager, sample_song_json, temp_stems):
        """Test validation with missing stem files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test.kai"
            
            # Remove one stem file
            incomplete_stems = {k: v for k, v in temp_stems.items() if k != "vocals"}
            
            with pytest.raises(ValueError, match="Missing required stem"):
                packager.package_kai(
                    output_path=output_path,
                    song_json=sample_song_json,
                    stem_files=incomplete_stems
                )
                
    def test_validate_invalid_song_json(self, packager, temp_stems):
        """Test validation with invalid song.json."""
        invalid_song_json = {"invalid": "structure"}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test.kai"
            
            with pytest.raises(ValueError, match="missing required field"):
                packager.package_kai(
                    output_path=output_path,
                    song_json=invalid_song_json,
                    stem_files=temp_stems
                )
                
    def test_extract_kai_info(self, packager, sample_song_json, temp_stems):
        """Test extracting information from KAI file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test.kai"
            
            packager.package_kai(
                output_path=output_path,
                song_json=sample_song_json,
                stem_files=temp_stems
            )
            
            info = packager.extract_kai_info(output_path)
            
            assert info["valid"] == True
            assert info["file_size"] > 0
            assert info["song_info"]["title"] == "Test Song"
            assert info["song_info"]["artist"] == "Test Artist"
            assert info["audio_info"]["profile"] == "KAI-4"
            assert len(info["contents"]) >= 5  # song.json + 4 stems