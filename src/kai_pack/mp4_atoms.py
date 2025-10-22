"""MP4 custom atoms for karaoke data."""

import base64
import json
import logging
import struct
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np

logger = logging.getLogger(__name__)


class MP4CustomAtoms:
    """Write custom MP4 atoms for karaoke data."""

    # Custom atom names (4 characters)
    KARA_ATOM = '----:com.stems:kara'  # Karaoke Data (JSON)
    VPCH_ATOM = '----:com.stems:vpch'  # Vocal Pitch (binary float32 array)
    KONS_ATOM = '----:com.stems:kons'  # Karaoke Onsets (binary float64 array)

    def write_kaid_atom(
        self,
        file_path: Path,
        karaoke_data: Dict[str, Any]
    ) -> None:
        """
        Write 'kaid' (Karaoke Data) atom to MP4 file.

        Args:
            file_path: Path to MP4/M4A file
            karaoke_data: Karaoke data dictionary (will be JSON-encoded)
        """
        try:
            from mutagen.mp4 import MP4
        except ImportError:
            raise ImportError("mutagen library required for MP4 atom writing")

        logger.info(f"Writing kaid atom to {file_path}")

        # Open MP4 file
        mp4 = MP4(file_path)

        # Convert data to JSON bytes
        json_data = json.dumps(karaoke_data, ensure_ascii=False, separators=(',', ':'))
        json_bytes = json_data.encode('utf-8')

        # Write as custom freeform atom
        mp4[self.KAID_ATOM] = [json_bytes]

        mp4.save()
        logger.info(f"✓ kaid atom written ({len(json_bytes)} bytes)")

    def write_vpch_atom(
        self,
        file_path: Path,
        vocal_pitch_data: np.ndarray
    ) -> None:
        """
        Write 'vpch' (Vocal Pitch) atom to MP4 file.

        Args:
            file_path: Path to MP4/M4A file
            vocal_pitch_data: Array of MIDI cents values (float32)
        """
        try:
            from mutagen.mp4 import MP4
        except ImportError:
            raise ImportError("mutagen library required for MP4 atom writing")

        logger.info(f"Writing vpch atom to {file_path}")

        # Convert to float32 binary
        if vocal_pitch_data.dtype != np.float32:
            vocal_pitch_data = vocal_pitch_data.astype(np.float32)

        binary_data = vocal_pitch_data.tobytes()

        # Open MP4 file
        mp4 = MP4(file_path)

        # Write as custom freeform atom
        mp4[self.VPCH_ATOM] = [binary_data]

        mp4.save()
        logger.info(f"✓ vpch atom written ({len(binary_data)} bytes, {len(vocal_pitch_data)} samples)")

    def write_kons_atom(
        self,
        file_path: Path,
        onsets_data: np.ndarray
    ) -> None:
        """
        Write 'kons' (Karaoke Onsets) atom to MP4 file.

        Args:
            file_path: Path to MP4/M4A file
            onsets_data: Array of onset timestamps in seconds (float64)
        """
        try:
            from mutagen.mp4 import MP4
        except ImportError:
            raise ImportError("mutagen library required for MP4 atom writing")

        logger.info(f"Writing kons atom to {file_path}")

        # Convert to float64 binary
        if onsets_data.dtype != np.float64:
            onsets_data = onsets_data.astype(np.float64)

        binary_data = onsets_data.tobytes()

        # Open MP4 file
        mp4 = MP4(file_path)

        # Write as custom freeform atom
        mp4[self.KONS_ATOM] = [binary_data]

        mp4.save()
        logger.info(f"✓ kons atom written ({len(binary_data)} bytes, {len(onsets_data)} onsets)")

    def read_kaid_atom(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Read 'kaid' atom from MP4 file.

        Args:
            file_path: Path to MP4/M4A file

        Returns:
            Karaoke data dictionary or None if not present
        """
        try:
            from mutagen.mp4 import MP4
        except ImportError:
            raise ImportError("mutagen library required for MP4 atom reading")

        mp4 = MP4(file_path)

        if self.KAID_ATOM in mp4:
            json_bytes = mp4[self.KAID_ATOM][0]
            json_str = json_bytes.decode('utf-8')
            return json.loads(json_str)

        return None

    def read_vpch_atom(self, file_path: Path) -> Optional[np.ndarray]:
        """
        Read 'vpch' atom from MP4 file.

        Args:
            file_path: Path to MP4/M4A file

        Returns:
            Vocal pitch array or None if not present
        """
        try:
            from mutagen.mp4 import MP4
        except ImportError:
            raise ImportError("mutagen library required for MP4 atom reading")

        mp4 = MP4(file_path)

        if self.VPCH_ATOM in mp4:
            binary_data = mp4[self.VPCH_ATOM][0]
            return np.frombuffer(binary_data, dtype=np.float32)

        return None

    def read_kons_atom(self, file_path: Path) -> Optional[np.ndarray]:
        """
        Read 'kons' atom from MP4 file.

        Args:
            file_path: Path to MP4/M4A file

        Returns:
            Onsets array or None if not present
        """
        try:
            from mutagen.mp4 import MP4
        except ImportError:
            raise ImportError("mutagen library required for MP4 atom reading")

        mp4 = MP4(file_path)

        if self.KONS_ATOM in mp4:
            binary_data = mp4[self.KONS_ATOM][0]
            return np.frombuffer(binary_data, dtype=np.float64)

        return None

    def get_karaoke_features(self, file_path: Path) -> Dict[str, bool]:
        """
        Fast check for karaoke features in MP4 file.

        Args:
            file_path: Path to MP4/M4A file

        Returns:
            Dictionary of feature flags
        """
        try:
            from mutagen.mp4 import MP4
        except ImportError:
            raise ImportError("mutagen library required for MP4 atom reading")

        features = {
            'has_lyrics': False,
            'has_word_timing': False,
            'has_advanced': False
        }

        try:
            mp4 = MP4(file_path)

            # Check for kaid atom (lyrics)
            if self.KAID_ATOM in mp4:
                features['has_lyrics'] = True

                # Parse to check for word timing
                kaid_data = self.read_kaid_atom(file_path)
                if kaid_data:
                    lines = kaid_data.get('lines', [])
                    features['has_word_timing'] = any(
                        'word_timing' in line for line in lines
                    )

                    # Check for multiple singers
                    has_multiple_singers = len(kaid_data.get('singers', [])) > 1
                    if has_multiple_singers:
                        features['has_advanced'] = True

            # Check for advanced features
            if self.VPCH_ATOM in mp4 or self.KONS_ATOM in mp4:
                features['has_advanced'] = True

        except Exception as e:
            logger.error(f"Error reading karaoke features: {e}")

        return features

    def add_ni_stems_metadata(
        self,
        file_path: Path,
        stem_names: List[str] = None
    ) -> None:
        """
        Add Native Instruments STEMS metadata to MP4 file.

        This writes a 'stem' atom directly under 'udta' for Mixxx/Traktor compatibility.

        Args:
            file_path: Path to MP4/M4A file
            stem_names: List of stem names (default: Drums, Bass, Other, Vocals)
        """
        if stem_names is None:
            stem_names = ["Drums", "Bass", "Other", "Vocals"]

        # Default colors for each stem
        colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"]

        logger.info(f"Adding NI Stems metadata to {file_path}")

        # Build stems metadata following NI STEMS specification
        stems_metadata = {
            "version": 1,
            "mastering_dsp": {
                "compressor": {
                    "enabled": True,
                    "input_gain": 0.0,
                    "output_gain": 0.0,
                    "threshold": -6.0,
                    "dry_wet": 100,
                    "attack": 0.003,
                    "release": 0.3,
                    "ratio": 2.0,
                    "hp_cutoff": 20
                },
                "limiter": {
                    "enabled": True,
                    "threshold": -0.3,
                    "ceiling": -0.3,
                    "release": 0.05
                }
            },
            "stems": [
                {"name": name, "color": colors[i]}
                for i, name in enumerate(stem_names)
            ]
        }

        # Encode metadata as JSON
        metadata_json = json.dumps(stems_metadata, indent=2)
        metadata_bytes = metadata_json.encode('utf-8')

        # Write stem atom directly to moov/udta/stem using binary manipulation
        self._inject_stem_atom(file_path, metadata_bytes)

        logger.info(f"✓ NI Stems metadata added ({len(stem_names)} stems)")

    def _inject_stem_atom(self, file_path: Path, stem_data: bytes) -> None:
        """Inject stem atom into moov/udta/stem location and update chunk offset tables."""
        # Read entire file
        with open(file_path, 'rb') as f:
            data = bytearray(f.read())

        # Find moov atom
        moov_pos, moov_size = self._find_atom(data, b'moov', 0)
        if moov_pos == -1:
            raise RuntimeError("No moov atom found")

        # Store original moov end position - this is where mdat starts
        original_moov_end = moov_pos + moov_size

        # Find or create udta atom within moov
        udta_pos, udta_size = self._find_atom(data, b'udta', moov_pos + 8, moov_pos + moov_size)

        if udta_pos == -1:
            # Create new udta atom at end of moov
            udta_pos = moov_pos + moov_size
            udta_header = struct.pack('>I4s', 8, b'udta')
            data[udta_pos:udta_pos] = udta_header
            udta_size = 8
            # Update moov size
            new_moov_size = moov_size + 8
            struct.pack_into('>I', data, moov_pos, new_moov_size)
            moov_size = new_moov_size

        # Create stem atom
        stem_atom_size = 8 + len(stem_data)
        stem_atom = struct.pack('>I4s', stem_atom_size, b'stem') + stem_data

        # Insert stem atom at end of udta
        insert_pos = udta_pos + udta_size
        data[insert_pos:insert_pos] = stem_atom

        # Update udta size
        new_udta_size = udta_size + stem_atom_size
        struct.pack_into('>I', data, udta_pos, new_udta_size)

        # Update moov size
        new_moov_size = moov_size + stem_atom_size
        struct.pack_into('>I', data, moov_pos, new_moov_size)

        # CRITICAL: Update chunk offset tables (stco/co64)
        # When we insert data inside moov, everything AFTER the moov atom shifts
        # All chunk offsets pointing to >= original_moov_end need to be increased
        logger.info(f"Updating chunk offsets: moov grew by {stem_atom_size} bytes, data after position {original_moov_end} shifted")
        self._update_chunk_offsets(data, moov_pos, moov_pos + new_moov_size, stem_atom_size, original_moov_end)

        # Write back to file
        with open(file_path, 'wb') as f:
            f.write(data)

    def _update_chunk_offsets(self, data: bytearray, search_start: int, search_end: int,
                               offset_delta: int, shift_threshold: int) -> None:
        """
        Update stco/co64 chunk offset tables after inserting data inside moov atom.

        Args:
            data: MP4 file data as bytearray
            search_start: Start position to search for offset tables (moov start)
            search_end: End position to search (moov end after growth)
            offset_delta: Number of bytes the moov atom grew by
            shift_threshold: File position where shift occurred (original moov end)
                           All chunk offsets >= this position need to be increased
        """
        # Recursively search for stco/co64 atoms in the entire moov tree
        stco_count = 0
        co64_count = 0
        total_updated = 0

        def search_atoms(start, end):
            nonlocal stco_count, co64_count, total_updated
            pos = start

            while pos < end - 8 and pos < len(data) - 8:
                try:
                    size = struct.unpack_from('>I', data, pos)[0]
                    if size < 8 or size > end - pos:
                        # Invalid size, skip ahead by 8 bytes
                        pos += 8
                        continue

                    atype = data[pos+4:pos+8]

                    # Update 32-bit chunk offset table (stco)
                    if atype == b'stco':
                        stco_count += 1
                        entry_count = struct.unpack_from('>I', data, pos + 12)[0]
                        logger.info(f"Found stco at position {pos}, {entry_count} entries, updating...")

                        for i in range(entry_count):
                            offset_pos = pos + 16 + (i * 4)
                            chunk_offset = struct.unpack_from('>I', data, offset_pos)[0]

                            # Only update offsets that point to data after the moov atom
                            if chunk_offset >= shift_threshold:
                                new_offset = chunk_offset + offset_delta
                                struct.pack_into('>I', data, offset_pos, new_offset)
                                total_updated += 1
                                if i < 3:  # Log first few
                                    logger.debug(f"  Entry {i}: {chunk_offset} -> {new_offset}")

                    # Update 64-bit chunk offset table (co64)
                    elif atype == b'co64':
                        co64_count += 1
                        entry_count = struct.unpack_from('>I', data, pos + 12)[0]
                        logger.info(f"Found co64 at position {pos}, {entry_count} entries, updating...")

                        for i in range(entry_count):
                            offset_pos = pos + 16 + (i * 8)
                            chunk_offset = struct.unpack_from('>Q', data, offset_pos)[0]

                            # Only update offsets that point to data after the moov atom
                            if chunk_offset >= shift_threshold:
                                new_offset = chunk_offset + offset_delta
                                struct.pack_into('>Q', data, offset_pos, new_offset)
                                total_updated += 1
                                if i < 3:  # Log first few
                                    logger.debug(f"  Entry {i}: {chunk_offset} -> {new_offset}")

                    # Recursively search container atoms
                    elif atype in [b'trak', b'mdia', b'minf', b'stbl', b'moov']:
                        search_atoms(pos + 8, pos + size)

                    pos += size

                except Exception as e:
                    logger.warning(f"Error parsing atom at {pos}: {e}")
                    pos += 8  # Skip ahead

        search_atoms(search_start, search_end)
        logger.info(f"Chunk offset update complete: found {stco_count} stco + {co64_count} co64 atoms, updated {total_updated} offsets")

    def _find_atom(self, data: bytearray, atom_type: bytes, start: int = 0, end: int = None) -> tuple:
        """Find atom in data, return (position, size) or (-1, 0) if not found."""
        if end is None:
            end = len(data)

        pos = start
        while pos < end - 8:
            size = struct.unpack_from('>I', data, pos)[0]
            atype = data[pos+4:pos+8]

            if atype == atom_type:
                return (pos, size)

            pos += size
            if size == 0:  # Avoid infinite loop
                break

        return (-1, 0)

    def disable_tracks(
        self,
        file_path: Path,
        track_indices: List[int]
    ) -> None:
        """
        Disable specific audio tracks in MP4 file.

        This sets the track header flags so that Traktor only plays the first track
        by default, while keeping the other stems available for mixing.

        NOTE: Currently not implemented - track manipulation requires low-level MP4 box editing.
        All tracks will remain enabled. This doesn't affect functionality in most players.

        Args:
            file_path: Path to MP4/M4A file
            track_indices: List of track indices to disable (0-based)
        """
        logger.info(f"Track disabling not yet implemented - skipping tracks {track_indices}")
        logger.info(f"All tracks will remain enabled in {file_path.name}")
        # TODO: Implement track disabling using alternative method
        # Options: ffmpeg -disposition, direct binary editing, or MP4Box
