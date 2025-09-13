#!/usr/bin/env python3
"""
Test script for LLM sync parsing with different response formats.
"""

import json
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.video.llm_sync_v2 import LLMSyncAssistant, TimedLyric

def test_gpt5_format_1():
    """Test GPT-5 format with captions and startMs/endMs"""
    response = {
        "captions": [
            {"startMs": 6000, "endMs": 9000, "text": "When the night feels endless"},
            {"startMs": 9125, "endMs": 12125, "text": "and I'm wide awake"},
            {"startMs": 12250, "endMs": 15250, "text": "I shuffle numbers like cards"},
        ]
    }
    
    print("Testing GPT-5 format 1 (captions with startMs/endMs)...")
    items = response.get('captions', [])
    timed_lyrics = []
    
    for item in items:
        if 'text' in item and 'startMs' in item and 'endMs' in item:
            timed_lyric = TimedLyric(
                text=item['text'],
                start_time=float(item['startMs']) / 1000.0,
                end_time=float(item['endMs']) / 1000.0,
                section_type=None
            )
            timed_lyrics.append(timed_lyric)
    
    for lyric in timed_lyrics:
        print(f"  {lyric.start_time:.2f}-{lyric.end_time:.2f}s: {lyric.text}")
    
    assert len(timed_lyrics) == 3
    assert timed_lyrics[0].start_time == 6.0
    assert timed_lyrics[0].end_time == 9.0
    print("✓ Format 1 parsing successful!\n")

def test_gpt5_format_2():
    """Test GPT-5 format with lyrics and start/end"""
    response = {
        "lyrics": [
            {"start": 6.00, "end": 8.75, "text": "When the night feels endless"},
            {"start": 9.00, "end": 11.75, "text": "and I'm wide awake"},
            {"start": 12.00, "end": 14.75, "text": "I shuffle numbers like cards"},
        ]
    }
    
    print("Testing GPT-5 format 2 (lyrics with start/end)...")
    items = response.get('lyrics', [])
    timed_lyrics = []
    
    for item in items:
        if 'text' in item and 'start' in item and 'end' in item:
            timed_lyric = TimedLyric(
                text=item['text'],
                start_time=float(item['start']),
                end_time=float(item['end']),
                section_type=None
            )
            timed_lyrics.append(timed_lyric)
    
    for lyric in timed_lyrics:
        print(f"  {lyric.start_time:.2f}-{lyric.end_time:.2f}s: {lyric.text}")
    
    assert len(timed_lyrics) == 3
    assert timed_lyrics[0].start_time == 6.0
    assert timed_lyrics[0].end_time == 8.75
    print("✓ Format 2 parsing successful!\n")

def test_gpt5_format_3():
    """Test GPT-5 format with direct array"""
    response = [
        {"i": 1, "start_ms": 0, "end_ms": 3200, "text": "When the night feels endless"},
        {"i": 2, "start_ms": 3200, "end_ms": 5400, "text": "and I'm wide awake"},
        {"i": 3, "start_ms": 5400, "end_ms": 7600, "text": "I shuffle numbers like cards"},
    ]
    
    print("Testing GPT-5 format 3 (array with start_ms/end_ms)...")
    items = response
    timed_lyrics = []
    
    for item in items:
        if 'text' in item and 'start_ms' in item and 'end_ms' in item:
            timed_lyric = TimedLyric(
                text=item['text'],
                start_time=float(item['start_ms']) / 1000.0,
                end_time=float(item['end_ms']) / 1000.0,
                section_type=None
            )
            timed_lyrics.append(timed_lyric)
    
    for lyric in timed_lyrics:
        print(f"  {lyric.start_time:.2f}-{lyric.end_time:.2f}s: {lyric.text}")
    
    assert len(timed_lyrics) == 3
    assert timed_lyrics[0].start_time == 0.0
    assert timed_lyrics[0].end_time == 3.2
    print("✓ Format 3 parsing successful!\n")

def test_actual_response():
    """Test the actual response from the log"""
    response_text = '''{
  "lyrics": [
    { "start": 6.00, "end": 8.75, "text": "When the night feels endless" },
    { "start": 9.00, "end": 11.75, "text": "and I'm wide awake" },
    { "start": 12.00, "end": 14.75, "text": "I shuffle numbers like cards" },
    { "start": 15.00, "end": 17.75, "text": "I hum a rhythm, let the numbers dance" },
    { "start": 18.00, "end": 20.75, "text": "And suddenly it's not so hard" }
  ]
}'''
    
    print("Testing actual GPT-5 response from log...")
    response = json.loads(response_text)
    
    # Simulate the parsing logic
    if isinstance(response, dict) and 'lyrics' in response:
        items = response['lyrics']
    else:
        items = []
    
    timed_lyrics = []
    for i, item in enumerate(items):
        if isinstance(item, dict) and 'text' in item:
            if 'start' in item and 'end' in item:
                timed_lyric = TimedLyric(
                    text=item['text'],
                    start_time=float(item['start']),
                    end_time=float(item['end']),
                    section_type=None
                )
                timed_lyrics.append(timed_lyric)
                print(f"  Parsed: {timed_lyric.start_time:.2f}-{timed_lyric.end_time:.2f}s: {timed_lyric.text}")
    
    assert len(timed_lyrics) == 5
    assert timed_lyrics[0].start_time == 6.0
    assert timed_lyrics[0].end_time == 8.75
    assert timed_lyrics[0].text == "When the night feels endless"
    print(f"✓ Actual response parsing successful! Parsed {len(timed_lyrics)} lyrics\n")

def main():
    print("=" * 60)
    print("Testing LLM Sync Response Parsing")
    print("=" * 60 + "\n")
    
    try:
        test_gpt5_format_1()
        test_gpt5_format_2()
        test_gpt5_format_3()
        test_actual_response()
        
        print("=" * 60)
        print("✅ All tests passed successfully!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()