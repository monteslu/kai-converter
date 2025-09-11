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
        
        print(f"Fetching lyrics from URL: {lyrics_source}")
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

def create_prompt(transcribed_lines, correct_lyrics):
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
    
    prompt = f"""TRANSCRIPTION ERROR CORRECTION TASK - READ ALL INSTRUCTIONS CAREFULLY

YOUR TASK: Fix ONLY obvious transcription errors. DO NOT REWRITE LYRICS.

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

Return format (MUST BE VALID JSON): 
{{
  "corrections": [{{"line_num": 1, "old_text": "original", "new_text": "corrected"}}, ...],
  "description": "Brief factual description of the song if you can identify it from the lyrics, or null if unknown"
}}

CRITICAL: Only include lines that actually need correction in the corrections array.
CRITICAL: Return ONLY valid JSON, no explanations, no markdown blocks, no additional text.

JSON OUTPUT:"""
    
    return prompt

def fix_lyrics_in_chunks(transcribed_lines, correct_lyrics, api_key=None, llm_config=None, chunk_size=10):
    """Process lyrics in smaller chunks to avoid token limits"""
    if len(transcribed_lines) <= chunk_size:
        # Small enough to process in one go
        return fix_lyrics_with_llm(transcribed_lines, correct_lyrics, api_key, llm_config)
    
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
        
        correction_result = fix_lyrics_with_llm(chunk, correct_lyrics, api_key, llm_config)
        if correction_result and len(correction_result) == 2:
            corrected_chunk, chunk_rejections = correction_result
            if corrected_chunk is not None:
                corrected_lines.extend(corrected_chunk)
                all_rejections.extend(chunk_rejections)
            else:
                # If correction fails, keep original
                print(f"  WARNING: Chunk correction returned None, keeping original")
                corrected_lines.extend(chunk)
        else:
            # If correction fails, keep original
            print(f"  WARNING: Chunk correction failed, keeping original")
            corrected_lines.extend(chunk)
    
    return corrected_lines, all_rejections

def fix_lyrics_with_llm(transcribed_lines, correct_lyrics, api_key=None, llm_config=None):
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
        
        prompt = create_prompt(transcribed_lines, correct_lyrics)
        
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
            
            # Handle both old format (list) and new format (dict with corrections/description)
            if isinstance(response_data, list):
                # Old format - just corrections
                corrections = response_data
                description = None
            else:
                # New format - dict with corrections and description
                corrections = response_data.get('corrections', [])
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
                            print(f"WARNING: Rejecting correction for line {line_num} (word retention {retention_rate:.1%}):")
                            print(f"  OLD: {original_text}")
                            print(f"  NEW: {new_text}")
                            print(f"  Common words: {common_words}")
                            
                            # Track this rejection
                            rejections.append({
                                "line_num": line_num,
                                "old_text": original_text,
                                "new_text": new_text,
                                "reason": "word_retention",
                                "retention_rate": round(retention_rate, 3),
                                "min_required": min_retention
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
                        print(f"WARNING: Skipping line {line_num} - text mismatch!")
                        print(f"  Expected: '{old_text}'")
                        print(f"  Actual:   '{original_text}'")
                        print(f"  Would change to: '{new_text}'")
                        
                        # Track this rejection
                        rejections.append({
                            "line_num": line_num,
                            "old_text": old_text,
                            "actual_text": original_text,
                            "new_text": new_text,
                            "reason": "text_mismatch"
                        })
                else:
                    print(f"WARNING: Invalid line number {line_num} (max: {len(corrected_lines)})")
                    
                    # Track this rejection
                    rejections.append({
                        "line_num": line_num,
                        "old_text": old_text,
                        "new_text": new_text,
                        "reason": "invalid_line_number",
                        "max_lines": len(corrected_lines)
                    })
            
            print(f"Applied {corrections_applied} corrections out of {len(corrections)} lines")
            if rejections:
                print(f"Rejected {len(rejections)} corrections for manual review")
            
            return corrected_lines, rejections
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Attempting to fix common issues...")
            
            # Try to fix common JSON issues
            # Remove any trailing commas before closing brackets
            response_text = response_text.replace(',]', ']').replace(',}', '}')
            # Escape unescaped quotes
            response_text = response_text.replace('\\"', '"').replace('"', '\\"').replace('{\\"', '{"').replace('\\",', '",').replace('\\":', '":')
            
            try:
                corrected_lines = json.loads(response_text)
                return corrected_lines
            except:
                print("Could not parse JSON response.")
                return None, []
        
    except ImportError as e:
        print(f"Error importing LLM provider: {e}")
        print("Make sure to install required packages or check your configuration.")
        return None, []
    except Exception as e:
        print(f"Error calling LLM API: {e}")
        return None, []

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
    
    # Load KAI data first
    print(f"Loading KAI file: {kai_file}")
    song_data = load_kai_lyrics(kai_file)
    transcribed_lines = song_data.get('lines', [])
    title = song_data['song'].get('title', '')
    artist = song_data['song'].get('artist', '')
    
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
        result = fix_lyrics_in_chunks(transcribed_lines, correct_lyrics, llm_config=llm_config, chunk_size=8)
    else:
        result = fix_lyrics_with_llm(transcribed_lines, correct_lyrics, llm_config=llm_config)
    
    if result and len(result) == 2:
        corrected_lines, rejections = result
        
        # Check if corrected_lines is valid
        if corrected_lines is None:
            print("Failed to correct lyrics - no corrected lines returned")
            return
        
        # Add rejections to song metadata if there are any
        if rejections:
            if 'song' not in song_data:
                song_data['song'] = {}
            song_data['song']['lyric_update_rejections'] = rejections
            print(f"\n=== SAVED {len(rejections)} REJECTIONS TO SONG METADATA ===\n")
        # Show comparison
        print("\n--- Sample Corrections ---")
        for i in range(min(3, len(transcribed_lines))):
            old_text = transcribed_lines[i].get('text', '')
            new_text = corrected_lines[i].get('text', '')
            if old_text != new_text:
                print(f"Line {i+1}:")
                print(f"  OLD: {old_text}")
                print(f"  NEW: {new_text}")
        
        # Update KAI file
        update_kai_file(kai_file, output, corrected_lines, song_data)
        print(f"\nSuccess! Corrected KAI file: {output}")
    else:
        print("Failed to correct lyrics")

if __name__ == "__main__":
    main()