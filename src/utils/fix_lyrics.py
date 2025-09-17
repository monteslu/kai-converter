#!/usr/bin/env python3
"""
fix_lyrics.py - Fix transcribed lyrics in KAI file using correct lyrics text
Usage: python3 fix_lyrics.py input.kai [--lyrics-source FILE/URL] [--output FILE.kai]
"""

import json
import sys
import zipfile
import tempfile
import shutil
from pathlib import Path
import os
import requests
from bs4 import BeautifulSoup
import click
import logging

# Set up logging with error file handler
def setup_logging():
    """Set up logging with error file for lyrics fixing issues."""
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Set up logger
    logger = logging.getLogger(__name__)
    
    # Clear existing handlers to prevent duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(logging.INFO)
    
    # Console handler for all messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # File handler for ALL lyrics fixing activity (successes and errors)
    activity_file = logs_dir / "fix_lyrics_activity.log"
    file_handler = logging.FileHandler(activity_file, mode='a')
    file_handler.setLevel(logging.INFO)  # Log everything
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # Force an immediate test log to verify logging is working
    logger.info(f"Logging initialized for lyrics fixing - PID: {os.getpid()}")
    
    # Force flush to ensure it's written
    for handler in logger.handlers:
        if hasattr(handler, 'flush'):
            handler.flush()
    
    return logger

logger = setup_logging()

def load_kai_lyrics(kai_path):
    """Extract song.json from KAI file."""
    with zipfile.ZipFile(kai_path, 'r') as z:
        with z.open('song.json') as f:
            return json.load(f)

def load_correct_lyrics(lyrics_source):
    """Load correct lyrics from text file or URL."""
    # Check if it's a URL
    if lyrics_source.startswith(('http://', 'https://')):
        import requests
        from bs4 import BeautifulSoup
        
        logger.info(f"Fetching lyrics from URL: {lyrics_source}")
        try:
            response = requests.get(lyrics_source, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            # Parse HTML and extract text
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Try to find lyrics in common containers
            # Musixmatch specific selectors
            lyrics_containers = [
                soup.find('div', class_='lyrics__content'),
                soup.find('span', class_='lyrics__content__ok'),
                soup.find('div', {'class': lambda x: x and 'lyrics__content' in x}),
                soup.find('div', class_='lyrics'),
                soup.find('div', class_='lyric-body'),
                soup.find('div', {'class': lambda x: x and 'lyrics' in x.lower()}),
                soup.find('pre'),
            ]
            
            for container in lyrics_containers:
                if container:
                    text = container.get_text(separator='\n', strip=True)
                    if len(text) > 100:  # Likely found lyrics
                        return text
            
            # More aggressive fallback for Musixmatch
            # Look for the main content area and skip navigation
            main_content = soup.find('main') or soup.find('div', {'role': 'main'}) or soup.body
            if main_content:
                # Remove navigation, headers, footers
                for element in main_content.find_all(['nav', 'header', 'footer', 'aside']):
                    element.decompose()
                
                text = main_content.get_text(separator='\n', strip=True)
                lines = text.split('\n')
                
                # Filter out common non-lyric lines
                filtered = []
                skip_patterns = ['Login', 'Search', 'Discover', 'Contribute', 'Musixmatch', 
                                'cookies', 'Cookie', 'Privacy', 'Terms', 'Copyright', '©',
                                'Are you an artist', 'Go to Pro', 'Advertisement']
                
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 1:  # Skip empty and single char lines
                        # Skip if line contains navigation/UI text
                        if not any(pattern in line for pattern in skip_patterns):
                            filtered.append(line)
                
                # Try to find where lyrics likely start and end
                # Usually after the song title and before footer content
                lyrics_text = '\n'.join(filtered)
                
                # If we still have too much content, try to extract a reasonable chunk
                if len(filtered) > 100:  # Too many lines for lyrics
                    # Look for a continuous block of text that looks like lyrics
                    # (not too short, not containing obvious UI elements)
                    possible_lyrics = []
                    for line in filtered:
                        if len(line) > 5 and len(line) < 100:  # Reasonable line length for lyrics
                            possible_lyrics.append(line)
                    lyrics_text = '\n'.join(possible_lyrics)
                
                return lyrics_text
            
            # Last resort fallback
            return "Could not extract lyrics from this URL. Try a different lyrics website."
            
        except Exception as e:
            print(f"Error fetching lyrics from URL: {e}")
            sys.exit(1)
    else:
        # It's a file path
        with open(lyrics_source, 'r', encoding='utf-8') as f:
            return f.read()

def extract_pitch_contour(vocal_pitch_data, duration=None, segment_ms=1000):
    """Extract simplified pitch contour from vocal_pitch data.

    Args:
        vocal_pitch_data: Dict with 'quant_data', 'sample_rate_hz', etc.
        duration: Song duration in seconds (for better formatting)
        segment_ms: Segment size in milliseconds (default 1000 = 1 second)

    Returns:
        String representation of pitch contour
    """
    if not vocal_pitch_data or 'quant_data' not in vocal_pitch_data:
        return None

    quant_data = vocal_pitch_data['quant_data']
    sample_rate = vocal_pitch_data.get('sample_rate_hz', 25)

    # Calculate samples per segment (convert ms to seconds)
    segment_size_sec = segment_ms / 1000.0
    samples_per_segment = int(sample_rate * segment_size_sec)

    # MIDI note to note name conversion
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    contour_lines = []

    for seg_idx in range(0, len(quant_data), samples_per_segment):
        seg_start = seg_idx / sample_rate
        seg_end = min((seg_idx + samples_per_segment) / sample_rate, duration or float('inf'))

        # Format timing based on segment size for readability
        if segment_ms < 1000:
            # Show as 0.5s, 1.0s, 1.5s for sub-second resolution
            time_format = f"{seg_start:.1f}-{seg_end:.1f}s"
        else:
            # Show as 0-1s, 1-2s for second+ resolution
            time_format = f"{seg_start:.0f}-{seg_end:.0f}s"

        # Get segment data
        segment = quant_data[seg_idx:seg_idx + samples_per_segment]

        # Extract non-zero pitches
        pitches = [v[0] for v in segment if v[0] > 0]

        if not pitches:
            contour_lines.append(f"{time_format}: silence")
        else:
            # Calculate pitch statistics
            min_pitch = min(pitches)
            max_pitch = max(pitches)

            # Convert to note names
            min_note = note_names[min_pitch % 12] + str(min_pitch // 12)
            max_note = note_names[max_pitch % 12] + str(max_pitch // 12)

            # Determine movement pattern
            if len(pitches) >= 2:
                first_third = pitches[:len(pitches)//3] if len(pitches) > 3 else [pitches[0]]
                last_third = pitches[-len(pitches)//3:] if len(pitches) > 3 else [pitches[-1]]

                avg_first = sum(first_third) / len(first_third)
                avg_last = sum(last_third) / len(last_third)

                if avg_last > avg_first + 2:
                    movement = "rising"
                elif avg_last < avg_first - 2:
                    movement = "falling"
                else:
                    movement = "steady"
            else:
                movement = "brief"

            # Determine intensity based on range
            pitch_range = max_pitch - min_pitch
            if pitch_range > 12:  # More than an octave
                intensity = "/dramatic"
            elif pitch_range < 3:
                intensity = "/narrow"
            else:
                intensity = ""

            if min_note == max_note:
                contour_lines.append(f"{time_format}: {min_note} monotone")
            else:
                contour_lines.append(f"{time_format}: {min_note}-{max_note} {movement}{intensity}")

    return "\n".join(contour_lines)

def create_prompt(transcribed_lines, correct_lyrics, song_data=None):
    """Create prompt for LLM to fix lyrics."""
    # Simplify to just line text and timing
    simple_lines = []
    for i, line in enumerate(transcribed_lines):
        simple_lines.append({
            "line_num": i + 1,
            "start": line.get('start', 0),
            "end": line.get('end', 0),
            "text": line.get('text', '')
        })
    
    # Build initial prompt
    prompt = f"""TRANSCRIPTION ERROR CORRECTION TASK - READ ALL INSTRUCTIONS CAREFULLY

YOUR TASK: Fix ONLY obvious transcription errors. DO NOT REWRITE LYRICS.
"""

    # Add vocal pitch contour if available
    if song_data and 'vocal_pitch' in song_data:
        duration = song_data.get('song', {}).get('duration_sec')
        segment_ms = 1000  # Default 1-second segments, could be made configurable
        pitch_contour = extract_pitch_contour(song_data['vocal_pitch'], duration, segment_ms)
        if pitch_contour:
            segment_desc = f"{segment_ms}ms" if segment_ms < 1000 else f"{segment_ms//1000}-second"
            prompt += f"""
VOCAL PITCH CONTOUR ({segment_desc} segments):
{pitch_contour}

Key: narrow=<3 semitones, dramatic=>12 semitones (octave+)
This shows vocal activity and delivery patterns. Use for identifying gaps where vocals exist but no transcription.
"""

    prompt += f"""
REFERENCE LYRICS (FOR CONTEXT ONLY - DO NOT COPY FROM THIS):
{correct_lyrics}

TRANSCRIBED LINES TO FIX:
{json.dumps(simple_lines, indent=2)}

!!!!! CRITICAL RULES - FOLLOW EXACTLY !!!!!

1. YOU ARE FIXING TRANSCRIPTION ERRORS, NOT REWRITING LYRICS
2. DO NOT REPLACE ENTIRE PHRASES WITH DIFFERENT LYRICS FROM THE SONG
3. DO NOT SUBSTITUTE LYRICS FROM OTHER PARTS OF THE REFERENCE
4. ONLY FIX OBVIOUS PHONETIC MISHEARINGS WHERE TRANSCRIPTION IS CLEARLY WRONG
5. AT LEAST 80% OF ORIGINAL WORDS MUST REMAIN IN ANY CORRECTION

EXAMPLES OF VALID CORRECTIONS (small phonetic fixes):
- "foamy" → "for me" (obvious mishearing)
- "say the way" → "sail away" (clear phonetic error)
- "Sancti" → "sanity" (cut-off word)
- "be me" → "believe me" (missing syllable)

!!!!! EXAMPLES OF FORBIDDEN CORRECTIONS !!!!!
- "You'll find the joy you've heard it mean" → "Just a dream and the wind to carry me" (WHOLESALE SUBSTITUTION - NEVER DO THIS)
- "I will wait" → "I've always heard it could be" (DIFFERENT LYRICS - FORBIDDEN)
- "and" → "in" (minor word changes - leave alone)
- Any correction that replaces the entire meaning or most words (FORBIDDEN)

!!!!! DOUBLE CHECK EVERY CORRECTION !!!!!
Before suggesting ANY correction:
1. Am I fixing a transcription error or rewriting lyrics? (Only fix errors)
2. Do at least 80% of the original words remain? (If not, reject the correction)
3. Is this an obvious phonetic mishearing? (If not, leave it alone)
4. Could the original be reasonably correct? (If yes, don't change it)

!!!!! FORBIDDEN ACTIONS !!!!!
- DO NOT replace transcribed text with lyrics from elsewhere in the reference
- DO NOT make creative improvements to match the "correct" lyrics
- DO NOT substitute entire phrases even if they're "wrong"
- DO NOT change words that could reasonably be correct
- DO NOT rewrite to make lyrics "better" or more accurate

!!!!! ADDITIONAL CONSTRAINTS !!!!!
- NEVER change timing fields - IGNORE THEM COMPLETELY
- When in doubt, DO NOT fix - leave the line unchanged
- Be consistent - if you fix a phrase once, fix it the same way every time
- If a line could be correct as transcribed, leave it alone

REMEMBER: YOU ARE NOT A LYRIC EDITOR. YOU ARE A TRANSCRIPTION ERROR FIXER.
Your job is to fix obvious mishearings, not to make lyrics match the reference perfectly.

!!!!! CRITICAL: RESPONSE FORMAT !!!!!
YOU MUST RESPOND WITH VALID JSON ONLY. NO MARKDOWN, NO EXPLANATIONS, NO ```json``` BLOCKS.
JUST PURE JSON STARTING WITH {{ AND ENDING WITH }}.

REQUIRED JSON FORMAT:
{{
  "corrections": [{{"line_num": 1, "old_text": "original", "new_text": "corrected"}}, ...],
  "missing_lines": [
    {{
      "suggested_text": "Text of missing line based on reference and pitch activity",
      "start": 15.5,
      "end": 19.5,
      "confidence": "high|medium|low",
      "reason": "Why this line is likely missing (e.g., 'Vocals detected but no transcription', 'Gap in timing matches chorus in reference')"
    }}
  ],
  "description": "Brief factual description of the song if you can identify it from the lyrics, or null if unknown"
}}

!!!!! JSON VALIDATION REQUIREMENTS !!!!!
- Start response with {{ (opening brace)
- End response with }} (closing brace) 
- All strings must be in double quotes
- Escape any quotes in text with \"
- Use valid JSON syntax only
- Do not include markdown formatting
- Do not wrap in code blocks

IMPORTANT ABOUT MISSING LINES:
- ONLY suggest missing lines if you have strong evidence from:
  1. The vocal pitch contour showing activity where there's no transcription
  2. The reference lyrics having content that clearly fits in gaps
  3. Large timing gaps between transcribed lines (>4 seconds)
- Set confidence based on evidence strength:
  - "high": Pitch shows vocals AND reference has matching text for this timing
  - "medium": Either pitch activity OR reference suggests missing content
  - "low": Just a timing gap that might have content
- DO NOT invent lyrics - only use what's in the reference

CRITICAL: Only include lines that actually need correction in the corrections array.
CRITICAL: Only suggest missing lines where you have evidence from pitch/reference/timing.
CRITICAL: Return ONLY valid JSON, no explanations, no markdown blocks, no additional text.

JSON OUTPUT:"""
    
    return prompt

def fix_lyrics_in_chunks(transcribed_lines, correct_lyrics, api_key=None, llm_config=None, chunk_size=10, song_data=None, kai_file_path=None):
    """Process lyrics in smaller chunks to avoid token limits"""
    if len(transcribed_lines) <= chunk_size:
        # Small enough to process in one go
        return fix_lyrics_with_llm(transcribed_lines, correct_lyrics, api_key, llm_config, song_data=song_data, kai_file_path=kai_file_path)
    
    print(f"Processing {len(transcribed_lines)} lines in chunks of {chunk_size}...")
    
    # Process in chunks
    corrected_lines = []
    all_rejections = []
    for i in range(0, len(transcribed_lines), chunk_size):
        chunk = transcribed_lines[i:i+chunk_size]
        chunk_end = min(i+chunk_size, len(transcribed_lines))
        print(f"\n=== Processing chunk: lines {i+1}-{chunk_end} ===")
        
        # Show what's in this chunk
        for j, line in enumerate(chunk):
            print(f"  Line {i+j+1}: {line.get('text', '')[:50]}...")
        
        correction_result = fix_lyrics_with_llm(chunk, correct_lyrics, api_key, llm_config, song_data=song_data, kai_file_path=kai_file_path)
        if correction_result and len(correction_result) == 3:
            corrected_chunk, chunk_rejections, chunk_missing = correction_result
            if corrected_chunk is not None:
                corrected_lines.extend(corrected_chunk)
                all_rejections.extend(chunk_rejections)
                # Note: We don't aggregate missing lines from chunks - they're per-song level
            else:
                # If correction fails, keep original
                print(f"  WARNING: Chunk correction returned None, keeping original")
                corrected_lines.extend(chunk)
        else:
            # If correction fails, keep original
            print(f"  WARNING: Chunk correction failed, keeping original")
            corrected_lines.extend(chunk)
    
    return corrected_lines, all_rejections, []

def fix_lyrics_with_llm(transcribed_lines, correct_lyrics, api_key=None, llm_config=None, song_data=None, kai_file_path=None):
    """Send to LLM API to fix lyrics."""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from llm_providers import get_llm_provider, get_default_model
        
        # Use new config format or fall back to legacy api_key
        if llm_config:
            provider_type = llm_config.get('provider', 'auto')
            model = llm_config.get('model')
            provider_kwargs = {}
            
            if llm_config.get('base_url'):
                provider_kwargs['base_url'] = llm_config['base_url']
            if llm_config.get('api_key'):
                provider_kwargs['api_key'] = llm_config['api_key']
                
            # Handle 'auto' by passing None to get_llm_provider for auto-detection
            if provider_type == 'auto':
                provider = get_llm_provider(None, **provider_kwargs)
            else:
                provider = get_llm_provider(provider_type, **provider_kwargs)
            
            # Get actual provider type if auto-detected
            if provider_type == 'auto':
                if hasattr(provider, '__class__'):
                    class_name = provider.__class__.__name__
                    if 'OpenAI' in class_name:
                        provider_type = 'openai'
                    elif 'LMStudio' in class_name:
                        provider_type = 'lmstudio'
                    elif 'Anthropic' in class_name:
                        provider_type = 'anthropic'
                    elif 'Gemini' in class_name:
                        provider_type = 'gemini'
                    else:
                        provider_type = 'unknown'
                        
            if not model:
                model = get_default_model(provider_type)
        else:
            # Legacy OpenAI mode
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("Error: No LLM configuration provided and OPENAI_API_KEY environment variable not set")
                return None, []
                
            provider = get_llm_provider('openai', api_key=api_key)
            provider_type = 'openai'
            model = 'gpt-4o'
        
        prompt = create_prompt(transcribed_lines, correct_lyrics, song_data)
        
        # Log the transcribed lines being sent
        print(f"=== TRANSCRIBED LINES BEING SENT TO {provider_type.upper()} ===")
        for i, line in enumerate(transcribed_lines[:5]):  # Show first 5
            print(f"Line {i+1}: '{line.get('text', '')}'")
        print(f"... and {len(transcribed_lines)-5} more lines")
        print("=" * 50)
        
        print(f"Sending to {provider_type} ({model}) for correction (this may take 10-60 seconds)...")
        import time
        start_time = time.time()
        
        messages = [
            {"role": "system", "content": "You are a precise JSON editor that fixes transcription errors while preserving timing data."},
            {"role": "user", "content": prompt}
        ]
        
        response_text = provider.complete_chat(messages, model=model, temperature=0.1)
        elapsed = time.time() - start_time
        print(f"Received response from {provider_type} in {elapsed:.1f} seconds")
        
        # Log response preview
        print(f"Response length: {len(response_text)} characters")
        if len(response_text) > 200:
            print(f"Response preview: {response_text[:100]}...{response_text[-100:]}")
        
        # Clean up response if needed (remove markdown blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        # Try to extract just the JSON object from the response
        response_text = response_text.strip()
        start_idx = response_text.find('{')
        if start_idx != -1:
            # Find the matching closing brace
            brace_count = 0
            end_idx = start_idx
            for i, char in enumerate(response_text[start_idx:], start_idx):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            response_text = response_text[start_idx:end_idx+1]
        
        # Try to parse JSON
        try:
            response_data = json.loads(response_text)
            
            # Log what the LLM actually returned
            logger.info(f"LLM returned: {len(response_data.get('corrections', []))} corrections, {len(response_data.get('missing_lines', []))} missing lines")
            
            # Handle both old format (list) and new format (dict with corrections/description)
            if isinstance(response_data, list):
                # Old format - just corrections
                corrections = response_data
                missing_lines = []
                description = None
            else:
                # New format - dict with corrections and description
                corrections = response_data.get('corrections', [])
                missing_lines = response_data.get('missing_lines', [])
                description = response_data.get('description')
            
            # Apply corrections back to full lines
            corrected_lines = transcribed_lines.copy()
            corrections_applied = 0
            rejections = []
            
            # Show description if available
            if description:
                print(f"=== SONG DESCRIPTION FROM {provider_type.upper()} ===")
                print(f"Description: {description}")
                print("=" * 40)
            
            print(f"Processing {len(corrections)} corrections from {provider_type.upper()}...")
            print(f"=== ALL CORRECTIONS FROM {provider_type.upper()} ===")
            for i, correction in enumerate(corrections):
                print(f"Correction {i+1}: Line {correction.get('line_num', '?')}")
                print(f"  OLD: '{correction.get('old_text', '')}'")
                print(f"  NEW: '{correction.get('new_text', '')}'")
            print("=" * 40)

            # Show missing lines suggestions if any
            if missing_lines:
                print(f"=== MISSING LINES SUGGESTED BY {provider_type.upper()} ===")
                for i, suggestion in enumerate(missing_lines):
                    start = suggestion.get('start', 0)
                    end = suggestion.get('end', 0)
                    text = suggestion.get('suggested_text', '')
                    confidence = suggestion.get('confidence', 'unknown')
                    reason = suggestion.get('reason', 'No reason given')
                    print(f"Suggestion {i+1}: [{start:.1f}s - {end:.1f}s] ({confidence} confidence)")
                    print(f"  Text: \"{text}\"")
                    print(f"  Reason: {reason}")
                print("=" * 40)
            
            for correction in corrections:
                line_num = correction.get('line_num', 0)
                old_text = correction.get('old_text', '')
                new_text = correction.get('new_text', '')
                
                line_idx = line_num - 1
                if 0 <= line_idx < len(corrected_lines):
                    original_line = corrected_lines[line_idx]
                    original_text = original_line.get('text', '')
                    
                    # CRITICAL: Only apply if old_text matches exactly (preserves timing integrity)
                    if old_text == original_text:
                        # Validation: reject obvious lyric substitutions but allow phonetic fixes
                        old_words = set(old_text.lower().replace(',', '').replace('.', '').split())
                        new_words = set(new_text.lower().replace(',', '').replace('.', '').split())
                        common_words = old_words & new_words
                        retention_rate = len(common_words) / len(old_words) if old_words else 0
                        
                        # More lenient for short lines, stricter for longer ones  
                        min_retention = 0.20 if len(old_words) <= 6 else 0.20
                        
                        if retention_rate < min_retention and len(old_words) > 2:
                            logger.info(f"REJECTED correction for line {line_num} (word retention {retention_rate:.1%})")
                            
                            # Track this rejection
                            rejections.append({
                                "line": line_num,
                                "start": original_line.get('start', 0),
                                "end": original_line.get('end', 0),
                                "old": original_text,
                                "new": new_text,
                                "reason": "word_retention",
                                "word_retention": round(retention_rate, 3)
                            })
                            continue
                        if new_text and new_text != original_text:
                            print(f"Line {line_num} correction:")
                            print(f"  OLD: {original_text}")
                            print(f"  NEW: {new_text}")
                            
                            corrected_lines[line_idx]['text'] = new_text
                            corrections_applied += 1
                            
                            # Also update word text if present
                            if 'words' in corrected_lines[line_idx]:
                                # Split new text into words and update
                                new_words = new_text.split()
                                old_words = corrected_lines[line_idx]['words']
                                
                                # Update word text while preserving timing
                                for i, word in enumerate(old_words):
                                    if i < len(new_words):
                                        old_word_text = word.get('t', '')
                                        if old_word_text != new_words[i]:
                                            print(f"    Word {i+1}: '{old_word_text}' → '{new_words[i]}'")
                                        word['t'] = new_words[i]
                        else:
                            print(f"Line {line_num}: No change needed (new text same as old)")
                    else:
                        logger.info(f"SKIPPED correction for line {line_num}: text mismatch")
                        
                        # Track this rejection
                        rejections.append({
                            "line": line_num,
                            "start": original_line.get('start', 0),
                            "end": original_line.get('end', 0),
                            "old": old_text,
                            "new": new_text,
                            "reason": "text_mismatch"
                        })
                else:
                    print(f"WARNING: Invalid line number {line_num} (max: {len(corrected_lines)})")
                    
                    # Track this rejection
                    rejections.append({
                        "line": line_num,
                        "start": 0,
                        "end": 0,
                        "old": old_text,
                        "new": new_text,
                        "reason": "invalid_line_number"
                    })
            
            print(f"Applied {corrections_applied} corrections out of {len(corrections)} lines")
            if rejections:
                print(f"Rejected {len(rejections)} corrections for manual review")
            
            return corrected_lines, rejections, missing_lines, corrections_applied
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.error(f"Raw LLM response (first 500 chars): {response_text[:500]}")
            logger.error(f"Response length: {len(response_text)} characters")
            logger.info("Attempting to fix common issues...")
            
            # Try to fix common JSON issues
            # Remove any trailing commas before closing brackets
            response_text = response_text.replace(',]', ']').replace(',}', '}')
            # Escape unescaped quotes
            response_text = response_text.replace('\\"', '"').replace('"', '\\"').replace('{\\"', '{"').replace('\\",', '",').replace('\\":', '":')
            
            try:
                corrected_lines = json.loads(response_text)
                logger.info("Successfully fixed JSON issues")
                return corrected_lines, [], []
            except Exception as fix_error:
                logger.error(f"Could not parse JSON response even after fixes: {fix_error}")
                logger.error(f"Fixed response (first 500 chars): {response_text[:500]}")
                return None, [], []
        
    except ImportError as e:
        print(f"Error importing LLM provider: {e}")
        print("Make sure to install required packages or check your configuration.")
        return None, [], []
    except Exception as e:
        print(f"Error calling LLM API: {e}")

        # Log lyrics fixing errors
        try:
            with open("lyric_errors.txt", "a", encoding="utf-8") as f:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n[{timestamp}] LLM API Error:\n")
                f.write(f"Error: {str(e)}\n")
                if kai_file_path:
                    f.write(f"KAI file: {kai_file_path}\n")
                if 'transcribed_lines' in locals() and transcribed_lines:
                    song_info = f"Lines: {len(transcribed_lines)}"
                    if transcribed_lines and 'text' in transcribed_lines[0]:
                        first_line = transcribed_lines[0]['text'][:50]
                        song_info += f", First line: \"{first_line}...\""
                    f.write(f"Song info: {song_info}\n")
                f.write("-" * 50 + "\n")
        except Exception as log_error:
            print(f"Failed to log error: {log_error}")

        return None, [], []

def update_kai_file(kai_path, output_path, corrected_lines, updated_song_data=None):
    """Update KAI file with corrected lyrics and optional song metadata."""
    # Create temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Extract KAI file
        with zipfile.ZipFile(kai_path, 'r') as z:
            z.extractall(temp_path)
        
        # Load and update song.json
        song_json_path = temp_path / 'song.json'
        with open(song_json_path, 'r') as f:
            data = json.load(f)
        
        # Use updated song data if provided, otherwise just update lines
        if updated_song_data:
            data = updated_song_data
        
        # Update lines with corrected lyrics
        data['lines'] = corrected_lines
        
        # Write updated song.json
        with open(song_json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Create new KAI file
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for file in temp_path.iterdir():
                z.write(file, file.name)
    
    print(f"Updated KAI file saved to: {output_path}")

def auto_fetch_lyrics(title, artist):
    """Automatically search and fetch lyrics, returns (lyrics, description)"""
    import re
    import urllib.parse
    
    print(f"Auto-searching for lyrics: {artist} - {title}")
    
    # Try Genius search with multiple query variations
    search_queries = [
        f"{artist} {title}",  # Original
        f"{title} {artist}",  # Reversed
        f"{title}",  # Title only
        f"{artist} {re.sub(r'\s*\([^)]*\)', '', title)}",  # Remove parentheses
        f"{re.sub(r'\s*\([^)]*\)', '', title)} {artist}",  # Reversed without parentheses
    ]
    
    for query in search_queries:
        query_encoded = urllib.parse.quote(query)
        search_url = f"https://genius.com/api/search/multi?q={query_encoded}"
        print(f"Searching Genius for: '{query}'")
        
        try:
            response = requests.get(search_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                data = response.json()
                if 'response' in data and 'sections' in data['response']:
                    for section in data['response']['sections']:
                        if section.get('type') == 'song' and section.get('hits'):
                            first_hit = section['hits'][0]
                            if 'result' in first_hit:
                                result = first_hit['result']
                                lyrics_path = result.get('path')
                                comment = result.get('song_art_image_thumbnail_url')  # We'll extract comment from result
                                
                                # Try to get description from various fields to store as comment
                                song_description = None
                                if 'description' in result:
                                    song_description = result['description']
                                elif 'annotation_count' in result and result['annotation_count'] > 0:
                                    song_description = f"Popular song with {result['annotation_count']} annotations on Genius"
                                elif 'primary_artist' in result:
                                    primary_artist = result['primary_artist'].get('name', artist)
                                    song_description = f"Song by {primary_artist}"
                                
                                if lyrics_path:
                                    genius_url = f"https://genius.com{lyrics_path}"
                                    print(f"Found on Genius: {genius_url}")
                                    lyrics = load_correct_lyrics(genius_url)
                                    if lyrics and len(lyrics) > 100:
                                        return lyrics, song_description
        except Exception as e:
            print(f"Genius search error for '{query}': {e}")
            continue
    
    # Try AZLyrics as fallback with multiple title variations
    artist_clean = re.sub(r'[^a-z0-9]', '', artist.lower())
    
    # Try different title variations
    title_variations = [
        title,  # Original
        re.sub(r'\s*\([^)]*\)', '', title),  # Remove parentheses
        title.replace(' (In Other Words)', ''),  # Remove specific parenthetical
        title.split('(')[0].strip(),  # Everything before first parenthesis
    ]
    
    for title_var in title_variations:
        song_clean = re.sub(r'[^a-z0-9]', '', title_var.lower())
        az_url = f"https://www.azlyrics.com/lyrics/{artist_clean}/{song_clean}.html"
        
        print(f"Trying AZLyrics: {az_url}")
        try:
            response = requests.get(az_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for div in soup.find_all('div'):
                    if div.get('class') is None and len(div.get_text()) > 500:
                        print(f"Found lyrics with title variation: '{title_var}'")
                        return div.get_text().strip(), None
        except:
            pass
    
    # If auto-fetch failed, prompt for URL
    print("\nAuto-fetch failed. Please find the song on Genius and paste the URL:")
    print(f"Search Google for: {artist} {title} site:genius.com")
    print("\nOr provide the Genius URL directly:")
    genius_url = input("Genius URL (or press Enter to skip): ").strip()
    
    if genius_url and genius_url.startswith('http'):
        print(f"Fetching from: {genius_url}")
        lyrics = load_correct_lyrics(genius_url)
        if lyrics and len(lyrics) > 100:
            return lyrics, None
    
    return None, None

@click.command()
@click.argument('kai_file', type=click.Path(exists=True, path_type=Path))
@click.option('--lyrics-source', '-l', type=str, help='Lyrics source file or URL (auto-fetch if not provided)')
@click.option('--output', '-o', type=click.Path(path_type=Path), help='Output KAI file (default: {input}_fixed.kai)')
@click.option('--llm-provider', default='auto', help='LLM provider: openai, lmstudio, anthropic, gemini, openai-compatible (default: auto)')
@click.option('--llm-model', help='Model name (uses provider default if not specified)')
@click.option('--llm-base-url', help='Base URL for LM Studio or OpenAI-compatible APIs (default: http://localhost:1234)')
@click.option('--llm-api-key', help='API key (overrides environment variables)')
def main(kai_file: Path, lyrics_source: str, output: Path, llm_provider: str, llm_model: str, llm_base_url: str, llm_api_key: str):
    """Fix transcribed lyrics in a KAI file using LLM providers for correction.
    
    Supports OpenAI, local LM Studio, Anthropic Claude, Google Gemini, and OpenAI-compatible APIs.
    Auto-detects provider based on available API keys or defaults to LM Studio.
    
    Examples:
      python3 fix_lyrics.py song.kai                                    # Auto-fetch lyrics (auto-detect provider)
      python3 fix_lyrics.py song.kai -l lyrics.txt                      # Use local file
      python3 fix_lyrics.py song.kai --llm-provider openai              # Use OpenAI
      python3 fix_lyrics.py song.kai --llm-provider lmstudio            # Use LM Studio (local)
      python3 fix_lyrics.py song.kai --llm-provider anthropic           # Use Claude
      python3 fix_lyrics.py song.kai --llm-provider gemini              # Use Google Gemini
      python3 fix_lyrics.py song.kai --llm-model llama-3.1-8b-instruct  # Custom model
      python3 fix_lyrics.py song.kai -l https://genius.com/... # Use URL
      python3 fix_lyrics.py song.kai -o corrected.kai          # Custom output name
    """
    # Set default output path if not provided
    if not output:
        # Create filename like "song_fixed.kai" from "song.kai"
        stem = kai_file.stem  # "song" from "song.kai"
        output = kai_file.parent / f"{stem}_fixed.kai"
    
    # Log the start of lyrics fixing
    logger.info(f"=== STARTING LYRICS FIXING ===")
    logger.info(f"Input KAI file: {kai_file}")
    logger.info(f"Output KAI file: {output}")
    logger.info(f"LLM Provider: {llm_provider}")
    
    try:
        # Load KAI data first
        print(f"Loading KAI file: {kai_file}")
        song_data = load_kai_lyrics(kai_file)
        transcribed_lines = song_data.get('lines', [])
        title = song_data['song'].get('title', '')
        artist = song_data['song'].get('artist', '')
        
        logger.info(f"Loaded song: {title} by {artist}")
        logger.info(f"Total lyric lines: {len(transcribed_lines)}")
        
        # Determine lyrics source
        if lyrics_source:
            # User provided lyrics source
            print(f"Loading correct lyrics from: {lyrics_source}")
            correct_lyrics = load_correct_lyrics(lyrics_source)
            song_description = None
        else:
            # Auto-fetch lyrics based on metadata
            fetch_result = auto_fetch_lyrics(title, artist)
            
            if not fetch_result or not fetch_result[0]:
                print("Failed to auto-fetch lyrics. Please provide a URL or text file.")
                sys.exit(1)
            
            correct_lyrics, song_description = fetch_result
        
        # If we got a description and there's no existing non-empty comment, store it as comment
        if song_description:
            existing_comment = song_data.get('song', {}).get('comment', '')
            if not existing_comment:
                print(f"=== SONG DESCRIPTION (storing as comment) ===")
                print(f"Description: {song_description}")
                print("=" * 40)
                
                # Store description as comment in song metadata
                if 'song' not in song_data:
                    song_data['song'] = {}
                song_data['song']['comment'] = song_description
            else:
                print(f"Existing comment found, skipping: {existing_comment}")
        
        print(f"Found {len(transcribed_lines)} transcribed lines")
        print(f"\n--- Fetched Lyrics Preview ---")
        preview_lines = correct_lyrics.split('\n')[:10]  # Show first 10 lines
        for line in preview_lines:
            if line.strip():
                print(f"  {line}")
        if len(correct_lyrics.split('\n')) > 10:
            print(f"  ... ({len(correct_lyrics.split('\n'))} total lines)")
        print("--- End Preview ---\n")
        
        # Fix lyrics with LLM 
        llm_config = {
            'provider': llm_provider,
            'model': llm_model,
            'base_url': llm_base_url,
            'api_key': llm_api_key
        }
        
        # Use smaller chunks for local LM Studio due to context limits
        if llm_provider == 'lmstudio' and len(transcribed_lines) > 10:
            result = fix_lyrics_in_chunks(transcribed_lines, correct_lyrics, llm_config=llm_config, chunk_size=8, song_data=song_data, kai_file_path=kai_file)
        else:
            result = fix_lyrics_with_llm(transcribed_lines, correct_lyrics, llm_config=llm_config, song_data=song_data, kai_file_path=kai_file)
        
        if result and len(result) == 4:
            corrected_lines, rejections, missing_lines_suggested, corrections_applied = result

            # Check if corrected_lines is valid
            if corrected_lines is None:
                logger.error("Failed to correct lyrics - no corrected lines returned")
                return
            
            # Add rejections and missing lines to song metadata if there are any
            if rejections or missing_lines_suggested:
                if 'meta' not in song_data:
                    song_data['meta'] = {}
                if 'corrections' not in song_data['meta']:
                    song_data['meta']['corrections'] = {}

                if rejections:
                    song_data['meta']['corrections']['rejected'] = rejections
                    print(f"\n=== SAVED {len(rejections)} REJECTIONS TO SONG METADATA ===\n")

                if missing_lines_suggested:
                    song_data['meta']['corrections']['missing_lines_suggested'] = missing_lines_suggested
                    print(f"\n=== SAVED {len(missing_lines_suggested)} MISSING LINE SUGGESTIONS TO SONG METADATA ===\n")
            
            # Show comparison
            print("\n--- Sample Corrections ---")
            for i in range(min(3, len(transcribed_lines))):
                old_text = transcribed_lines[i].get('text', '')
                new_text = corrected_lines[i].get('text', '')
                if old_text != new_text:
                    print(f"Line {i+1}:")
                    print(f"  OLD: {old_text}")
                    print(f"  NEW: {new_text}")
            
            # Use the actual count from the LLM function
            logger.info(f"Applied {corrections_applied} corrections")
            
            if rejections:
                logger.info(f"Rejected {len(rejections)} questionable corrections")
            
            if missing_lines_suggested:
                logger.info(f"Suggested {len(missing_lines_suggested)} missing lines")
            
            # Update KAI file
            update_kai_file(kai_file, output, corrected_lines, song_data)
            logger.info(f"SUCCESS! Corrected KAI file saved: {output}")
            logger.info("=== LYRICS FIXING COMPLETED SUCCESSFULLY ===")
        else:
            logger.error("Failed to correct lyrics - no result returned from LLM")
            logger.error("=== LYRICS FIXING FAILED ===")
    
    except Exception as e:
        logger.error(f"EXCEPTION during lyrics fixing: {e}")
        logger.error(f"KAI file: {kai_file}")
        logger.error("=== LYRICS FIXING FAILED WITH EXCEPTION ===")

if __name__ == "__main__":
    main()