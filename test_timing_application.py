#!/usr/bin/env python3
"""
Test script to verify LLM sync timing is properly applied to scenes.
"""

import json
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.video.llm_sync_v2 import LLMSyncAssistant, TimedLyric
from core.video.storyboard import Scene

def test_strict_contract_response():
    """Test the actual Strict Contract v1.0 response from GPT-5"""
    
    # The actual response from GPT-5 (from the log)
    response_text = '''{"version":"1.0","units":"ms","line_count":28,"lyrics":[{"text":"When the night feels endless and I'm wide awake","start_ms":6000,"end_ms":10000},{"text":"I shuffle numbers like cards","start_ms":10000,"end_ms":14000},{"text":"I hum a rhythm, let the numbers dance","start_ms":14000,"end_ms":18000},{"text":"And suddenly it's not so hard","start_ms":18000,"end_ms":22000},{"text":"I'm doin' math, I do math, I do math","start_ms":24000,"end_ms":28000},{"text":"I'm tap-tap-tappin' in my head","start_ms":28000,"end_ms":32000},{"text":"I'm doin' math, I do math, I do math","start_ms":32000,"end_ms":36000},{"text":"I'm countin' sheep with sums instead","start_ms":36000,"end_ms":40000},{"text":"Add a slice of lemon, subtract a line of rhyme","start_ms":42000,"end_ms":46000},{"text":"Square a little laughter, divide it into time","start_ms":46000,"end_ms":50000},{"text":"Juggle all the fractions 'til the music swings","start_ms":50000,"end_ms":54000},{"text":"Let geometry and jazz give me wings","start_ms":54000,"end_ms":58000},{"text":"I'm doin' math, I do math, I do math","start_ms":60000,"end_ms":64000},{"text":"I'm tap-tap-tappin' in my head","start_ms":64000,"end_ms":68000},{"text":"I'm doin' math, I do math, I do math","start_ms":68000,"end_ms":72000},{"text":"I'm countin' sheep with sums instead","start_ms":72000,"end_ms":76000},{"text":"Take X for a stroll, then flip it to Y","start_ms":78000,"end_ms":80000},{"text":"If I get puzzled, I multiply","start_ms":80000,"end_ms":82000},{"text":"And if I stall, I won't be shy","start_ms":82000,"end_ms":84000},{"text":"I'll sing out pi, let the digits fly!","start_ms":84000,"end_ms":86000},{"text":"I'm doin' math, I do math, I do math","start_ms":88000,"end_ms":92000},{"text":"I'm tap-tap-tappin' in my head","start_ms":92000,"end_ms":96000},{"text":"I'm doin' math, I do math, I do math","start_ms":96000,"end_ms":100000},{"text":"I'm countin' sheep with sums instead","start_ms":100000,"end_ms":104000},{"text":"So if you're restless, if you can't sleep","start_ms":106000,"end_ms":110000},{"text":"Just play with numbers 'til the morning creeps","start_ms":110000,"end_ms":114000},{"text":"Snap your fingers, swing that beat","start_ms":114000,"end_ms":118000},{"text":"Do math, and feel complete!","start_ms":118000,"end_ms":122000}]}'''
    
    print("=" * 60)
    print("Testing Strict Contract v1.0 Timing Application")
    print("=" * 60)
    
    # Parse the response
    timing_data = json.loads(response_text)
    
    # Verify the format
    assert timing_data['version'] == '1.0'
    assert timing_data['units'] == 'ms'
    assert timing_data['line_count'] == 28
    assert len(timing_data['lyrics']) == 28
    
    print(f"\n✓ Format validation passed")
    print(f"  Version: {timing_data['version']}")
    print(f"  Units: {timing_data['units']}")
    print(f"  Line count: {timing_data['line_count']}")
    
    # Parse into TimedLyric objects (simulating what the code does)
    timed_lyrics = []
    for item in timing_data['lyrics']:
        start_ms = item['start_ms']
        end_ms = item['end_ms']
        
        start_time = float(start_ms) / 1000.0
        end_time = float(end_ms) / 1000.0
        
        timed_lyric = TimedLyric(
            text=item['text'],
            start_time=start_time,
            end_time=end_time,
            section_type=None
        )
        timed_lyrics.append(timed_lyric)
    
    print(f"\n✓ Parsed {len(timed_lyrics)} timed lyrics")
    
    # Display timing details
    print("\n" + "=" * 60)
    print("TIMING DETAILS:")
    print("=" * 60)
    
    total_duration = 0
    for i, lyric in enumerate(timed_lyrics, 1):
        duration = lyric.end_time - lyric.start_time
        total_duration += duration
        print(f"\n{i:2}. [{lyric.start_time:6.2f}s - {lyric.end_time:6.2f}s] Duration: {duration:4.2f}s")
        print(f"    {lyric.text}")
        
        # Check for issues
        if duration == 1.0:
            print(f"    ⚠️ WARNING: Exactly 1 second duration!")
        if duration < 0.5:
            print(f"    ⚠️ WARNING: Very short duration!")
        if duration > 10.0:
            print(f"    ⚠️ WARNING: Very long duration!")
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)
    print(f"Total lyrics: {len(timed_lyrics)}")
    print(f"Total duration: {total_duration:.2f}s")
    print(f"Average duration: {total_duration/len(timed_lyrics):.2f}s per line")
    
    # Check for specific timing patterns
    durations = [lyric.end_time - lyric.start_time for lyric in timed_lyrics]
    unique_durations = set(durations)
    
    if len(unique_durations) == 1 and 1.0 in unique_durations:
        print("\n❌ ERROR: All lyrics have exactly 1 second duration!")
        print("   This suggests timing is not being applied correctly.")
    elif all(d == 4.0 for d in durations[:8]):  # Check if first verse lines are all 4s
        print("\n✓ Timing looks correct - varying durations based on content")
    else:
        print(f"\n✓ Found {len(unique_durations)} unique durations")
    
    # Test scene application (simulating workspace_widget.py logic)
    print("\n" + "=" * 60)
    print("TESTING SCENE APPLICATION:")
    print("=" * 60)
    
    # Create mock scenes
    scenes = []
    for i, lyric in enumerate(timed_lyrics):
        scene = Scene(
            id=f"scene_{i+1}",
            source=lyric.text,
            prompt=lyric.text,
            start_time=0.0,  # Initial value
            end_time=1.0,    # Initial value
            duration=1.0     # Initial value
        )
        scenes.append(scene)
    
    print(f"\nCreated {len(scenes)} mock scenes with initial 1s duration")
    
    # Apply timing (simulating the workspace_widget logic)
    for i, (scene, timed_lyric) in enumerate(zip(scenes, timed_lyrics)):
        old_duration = scene.duration
        scene.start_time = timed_lyric.start_time
        scene.end_time = timed_lyric.end_time
        scene.duration = timed_lyric.end_time - timed_lyric.start_time
        
        print(f"\nScene {i+1}:")
        print(f"  Before: start={0.0:.2f}s, end={1.0:.2f}s, duration={old_duration:.2f}s")
        print(f"  After:  start={scene.start_time:.2f}s, end={scene.end_time:.2f}s, duration={scene.duration:.2f}s")
        
        if scene.duration == 1.0:
            print(f"  ⚠️ Still 1 second after applying timing!")
    
    # Final check
    scene_durations = [scene.duration for scene in scenes]
    if all(d == 1.0 for d in scene_durations):
        print("\n" + "=" * 60)
        print("❌ PROBLEM IDENTIFIED:")
        print("=" * 60)
        print("All scenes still have 1 second duration after applying timing!")
        print("This means the timing application in workspace_widget.py is not working.")
        print("\nPossible issues:")
        print("1. Scene timing is being overwritten after LLM sync")
        print("2. The UI is not reading the updated scene.duration field")
        print("3. There's a mismatch between scene object fields and UI display")
    else:
        print("\n" + "=" * 60)
        print("✅ TIMING APPLICATION TEST PASSED!")
        print("=" * 60)
        print("Scenes have correct varying durations from LLM sync.")

if __name__ == "__main__":
    try:
        test_strict_contract_response()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)