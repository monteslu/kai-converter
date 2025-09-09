#!/usr/bin/env python3
"""
Simple lyrics fetcher that tries multiple sources
"""

import sys
import requests
from bs4 import BeautifulSoup
import json
import re

def get_lyrics_azlyrics(artist, song):
    """Try AZLyrics (usually works well)"""
    # Format for AZLyrics URL
    artist_clean = re.sub(r'[^a-z0-9]', '', artist.lower())
    song_clean = re.sub(r'[^a-z0-9]', '', song.lower())
    
    url = f"https://www.azlyrics.com/lyrics/{artist_clean}/{song_clean}.html"
    print(f"Trying AZLyrics: {url}")
    
    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # AZLyrics puts lyrics in a div with no class/id, but after a specific comment
            lyrics_div = None
            for div in soup.find_all('div'):
                if div.get('class') is None and len(div.get_text()) > 500:
                    lyrics_div = div
                    break
            
            if lyrics_div:
                lyrics = lyrics_div.get_text().strip()
                return lyrics
    except:
        pass
    
    return None

def get_lyrics_genius_search(artist, song):
    """Use Genius search (no API key needed for search)"""
    search_url = f"https://genius.com/api/search/multi?q={artist}+{song}"
    print(f"Searching Genius for: {artist} - {song}")
    
    try:
        response = requests.get(search_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code == 200:
            data = response.json()
            # Find the first song result
            if 'response' in data and 'sections' in data['response']:
                for section in data['response']['sections']:
                    if section.get('type') == 'song' and section.get('hits'):
                        first_hit = section['hits'][0]
                        if 'result' in first_hit:
                            lyrics_path = first_hit['result'].get('path')
                            if lyrics_path:
                                genius_url = f"https://genius.com{lyrics_path}"
                                print(f"Found on Genius: {genius_url}")
                                return get_lyrics_from_genius_url(genius_url)
    except Exception as e:
        print(f"Genius search error: {e}")
    
    return None

def get_lyrics_from_genius_url(url):
    """Extract lyrics from a Genius URL"""
    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all divs that contain lyrics
            lyrics_divs = soup.find_all('div', {'data-lyrics-container': 'true'})
            
            if lyrics_divs:
                lyrics = []
                for div in lyrics_divs:
                    # Get text preserving line breaks
                    text = div.get_text(separator='\n').strip()
                    lyrics.append(text)
                
                return '\n\n'.join(lyrics)
    except:
        pass
    
    return None

def auto_get_lyrics(kai_file):
    """Extract artist and title from KAI file and fetch lyrics"""
    import zipfile
    
    # Extract metadata from KAI file
    with zipfile.ZipFile(kai_file, 'r') as z:
        with z.open('song.json') as f:
            data = json.load(f)
    
    title = data['song'].get('title', '')
    artist = data['song'].get('artist', '')
    
    if not title or not artist:
        print("Could not extract title/artist from KAI file")
        return None
    
    print(f"Looking for lyrics: {artist} - {title}")
    
    # Try different sources
    lyrics = get_lyrics_genius_search(artist, title)
    
    if not lyrics:
        lyrics = get_lyrics_azlyrics(artist, title)
    
    if lyrics:
        # Save to file
        output_file = f"{title.replace(' ', '_')}_lyrics.txt"
        with open(output_file, 'w') as f:
            f.write(lyrics)
        print(f"Lyrics saved to: {output_file}")
        return output_file
    else:
        print("Could not find lyrics automatically")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 get_lyrics.py <kai_file>")
        print("Automatically fetches lyrics based on song metadata")
        sys.exit(1)
    
    kai_file = sys.argv[1]
    lyrics_file = auto_get_lyrics(kai_file)
    
    if lyrics_file:
        print(f"\nNow you can run:")
        print(f"python3 fix_lyrics.py {kai_file} {lyrics_file}")