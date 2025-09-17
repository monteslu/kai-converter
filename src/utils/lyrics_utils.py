#!/usr/bin/env python3
"""Common lyrics utilities for LRCLIB integration and vocabulary extraction."""

import logging
import os
import re
import sys
import tempfile
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)


def fetch_lyrics_from_lrclib(title: str, artist: str) -> Optional[str]:
    """Fetch plain lyrics from LRCLIB API."""
    try:
        url = "https://lrclib.net/api/search"
        params = {
            "track_name": title,
            "artist_name": artist
        }

        logger.info(f"Searching LRCLIB for: {title} by {artist}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        results = response.json()

        if not results:
            logger.warning("No lyrics found on LRCLIB")
            return None

        # Get first non-instrumental result with plain lyrics
        for result in results:
            if not result.get("instrumental", False) and result.get("plainLyrics"):
                logger.info(f"✓ Found lyrics: {result.get('name', 'Unknown')} from {result.get('albumName', 'Unknown')}")
                return result["plainLyrics"]

        logger.warning("No suitable lyrics found (all instrumental or missing plainLyrics)")
        return None

    except Exception as e:
        logger.warning(f"Failed to fetch lyrics from LRCLIB: {e}")
        return None


def extract_vocabulary_hints(lyrics: str) -> str:
    """Extract meaningful vocabulary words from lyrics for Whisper context."""
    if not lyrics:
        return ""

    # Keep only letters (English + common accented characters)
    words_only = re.sub(r'[^a-zA-ZáéíóúñüÁÉÍÓÚÑÜ\s]', ' ', lyrics)

    # Split into words, filter meaningful ones
    words = [w.lower() for w in words_only.split() if len(w) > 3]

    # Remove common words
    common_words = {
        'this', 'that', 'with', 'will', 'were', 'when', 'where', 'what',
        'they', 'them', 'then', 'than', 'like', 'just', 'have', 'from',
        'been', 'your', 'come', 'said', 'would', 'could', 'should', 'there',
        'their', 'these', 'those', 'through', 'before', 'after', 'about',
        'dont', 'cant', 'wont', 'isnt', 'arent', 'wasnt', 'werent', 'doesnt'
    }

    # Count word frequency with boost for opening words
    word_counts = {}
    for i, word in enumerate(words):
        if word not in common_words:
            count = word_counts.get(word, 0) + 1

            # Boost first 3 meaningful words (give them +1 initial score)
            if i < 3:
                count += 1

            word_counts[word] = count

    # Get most frequent words (minimum 2 occurrences for importance)
    frequent_words = [(word, count) for word, count in word_counts.items() if count >= 2]

    # Sort by frequency (descending), then alphabetically for consistency
    frequent_words.sort(key=lambda x: (-x[1], x[0]))

    # Build word list prioritizing frequency, but respect token limits
    all_candidates = []

    # Start with frequent words (priority)
    all_candidates.extend([word for word, count in frequent_words])

    # Add single-occurrence words if we have room
    if len(frequent_words) < 15:
        single_words = [word for word, count in word_counts.items() if count == 1]
        single_words.sort()  # Alphabetical for consistency
        remaining_slots = 15 - len(all_candidates)
        all_candidates.extend(single_words[:remaining_slots])

    # Estimate tokens and trim to fit Whisper's 224-token limit with safety buffer
    # Reserve ~50 tokens for base prompt + 20 token safety buffer = 70 tokens reserved
    # Whisper limit: 224 - 70 reserved = 154 tokens available for vocabulary
    max_vocab_tokens = 150

    selected_words = []
    estimated_tokens = 0

    for word in all_candidates:
        # Rough estimate: 1 token per 4 characters + 1 token for comma/space
        word_tokens = len(word) // 4 + 1 + 1

        if estimated_tokens + word_tokens <= max_vocab_tokens:
            selected_words.append(word)
            estimated_tokens += word_tokens
        else:
            break  # Stop adding words to stay under limit

    return ', '.join(selected_words)


def prepare_whisper_context(title: str, artist: str = "") -> Tuple[Optional[str], Optional[str]]:
    """
    Prepare Whisper initial_prompt with LRCLIB vocabulary enhancement.

    Returns:
        tuple: (initial_prompt, lyrics_temp_file_path)
    """
    vocabulary_hints = ""
    lyrics_temp_file = None

    # Try to fetch lyrics from LRCLIB for vocabulary hints
    if title and artist:
        lyrics = fetch_lyrics_from_lrclib(title, artist)
        if lyrics:
            vocabulary_hints = extract_vocabulary_hints(lyrics)

            # Save lyrics to temp file for potential fix_lyrics usage
            try:
                lyrics_temp_fd, lyrics_temp_file = tempfile.mkstemp(suffix='.txt', prefix='lrclib_lyrics_')
                with open(lyrics_temp_file, 'w', encoding='utf-8') as f:
                    f.write(lyrics)
                os.close(lyrics_temp_fd)  # Close file descriptor, keep file
                logger.info(f"Saved reference lyrics to: {lyrics_temp_file}")
            except Exception as e:
                logger.warning(f"Failed to save lyrics to temp file: {e}")
                lyrics_temp_file = None

    # Build initial prompt with vocabulary context
    initial_prompt = None
    if title:
        if vocabulary_hints:
            initial_prompt = f"This song is called {title}. Song vocabulary includes: {vocabulary_hints}"
        else:
            initial_prompt = f"This song is called {title}"
        logger.info(f"Using initial prompt: {initial_prompt}")
    elif artist:
        # Fallback to artist only if no title available
        initial_prompt = f"This is a song by {artist}"
        logger.info(f"Using initial prompt: {initial_prompt}")

    return initial_prompt, lyrics_temp_file


def save_lyrics_temp_info(lyrics_temp_file: str) -> None:
    """Save lyrics temp file path for shell script integration."""
    if lyrics_temp_file:
        try:
            temp_info_file = os.path.join(tempfile.gettempdir(), f"lrclib_lyrics_path_{os.getpid()}.txt")
            with open(temp_info_file, 'w') as f:
                f.write(lyrics_temp_file)
            # Output the info file path for shell script to find
            print(f"LRCLIB_INFO_FILE={temp_info_file}", file=sys.stderr)
        except Exception as e:
            logger.warning(f"Failed to save temp file path info: {e}")