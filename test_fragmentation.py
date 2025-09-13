#!/usr/bin/env python3
"""
Test script for handling GPT-5 fragmented lyrics.
"""

import json
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.video.llm_sync_v2 import LLMSyncAssistant, TimedLyric

def test_actual_fragmentation():
    """Test the actual GPT-5 fragmented response from the log"""
    
    # The actual response from GPT-5 with 33 fragments
    response = {
        "lyrics": [
            {"startMs": 6000, "endMs": 9120, "text": "When the night feels endless and I'm"},
            {"startMs": 9220, "endMs": 12340, "text": "wide awake"},
            {"startMs": 12440, "endMs": 15560, "text": "I shuffle numbers like cards"},
            {"startMs": 15660, "endMs": 18780, "text": "I hum a rhythm, let the numbers dance"},
            {"startMs": 18880, "endMs": 22000, "text": "And suddenly it's not so hard"},
            
            {"startMs": 24000, "endMs": 27925, "text": "I'm doin' math, I do math, I do math"},
            {"startMs": 28025, "endMs": 31950, "text": "I'm tap-tap-tappin' in my head"},
            {"startMs": 32050, "endMs": 35975, "text": "I'm doin' math, I do math, I do math"},
            {"startMs": 36075, "endMs": 40000, "text": "I'm countin' sheep with sums instead"},
            
            {"startMs": 42000, "endMs": 44200, "text": "Add a slice of lemon,"},
            {"startMs": 44300, "endMs": 46500, "text": "subtract a line of rhyme"},
            {"startMs": 46600, "endMs": 48800, "text": "Square a little laughter,"},
            {"startMs": 48900, "endMs": 51100, "text": "divide it into time"},
            {"startMs": 51200, "endMs": 53400, "text": "Juggle all the fractions 'til the"},
            {"startMs": 53500, "endMs": 55700, "text": "music swings"},
            {"startMs": 55800, "endMs": 58000, "text": "Let geometry and jazz give me wings"},
            
            {"startMs": 60000, "endMs": 63925, "text": "I'm doin' math, I do math, I do math"},
            {"startMs": 64025, "endMs": 67950, "text": "I'm tap-tap-tappin' in my head"},
            {"startMs": 68050, "endMs": 71975, "text": "I'm doin' math, I do math, I do math"},
            {"startMs": 72075, "endMs": 76000, "text": "I'm countin' sheep with sums instead"},
            
            {"startMs": 78000, "endMs": 79520, "text": "So if you're restless, if you can't sleep"},
            {"startMs": 79620, "endMs": 81140, "text": "Just play with numbers 'til the"},
            {"startMs": 81240, "endMs": 82760, "text": "morning creeps"},
            {"startMs": 82860, "endMs": 84380, "text": "Snap your fingers, swing that beat"},
            {"startMs": 84480, "endMs": 86000, "text": "Do math, and feel complete!"},
            
            {"startMs": 88000, "endMs": 91925, "text": "Take X for a stroll, then flip it to Y"},
            {"startMs": 92025, "endMs": 95950, "text": "If I get puzzled, I multiply"},
            {"startMs": 96050, "endMs": 99975, "text": "And if I stall, I won't be shy"},
            {"startMs": 100075, "endMs": 104000, "text": "I'll sing out pi, let the digits fly!"},
            
            {"startMs": 106000, "endMs": 109925, "text": "I'm doin' math, I do math, I do math"},
            {"startMs": 110025, "endMs": 113950, "text": "I'm tap-tap-tappin' in my head"},
            {"startMs": 114050, "endMs": 117975, "text": "I'm doin' math, I do math, I do math"},
            {"startMs": 118075, "endMs": 122000, "text": "I'm countin' sheep with sums instead"}
        ]
    }
    
    # The original 28 lyric lines (from the log)
    original_lyrics = [
        "When the night feels endless and I'm wide awake",
        "I shuffle numbers like cards",
        "I hum a rhythm, let the numbers dance",
        "And suddenly it's not so hard",
        "I'm doin' math, I do math, I do math",
        "I'm tap-tap-tappin' in my head",
        "I'm doin' math, I do math, I do math",
        "I'm countin' sheep with sums instead",
        "Add a slice of lemon, subtract a line of rhyme",
        "Square a little laughter, divide it into time",
        "Juggle all the fractions 'til the music swings",
        "Let geometry and jazz give me wings",
        "I'm doin' math, I do math, I do math",
        "I'm tap-tap-tappin' in my head",
        "I'm doin' math, I do math, I do math",
        "I'm countin' sheep with sums instead",
        "Take X for a stroll, then flip it to Y",
        "If I get puzzled, I multiply",
        "And if I stall, I won't be shy",
        "I'll sing out pi, let the digits fly!",
        "I'm doin' math, I do math, I do math",
        "I'm tap-tap-tappin' in my head",
        "I'm doin' math, I do math, I do math",
        "I'm countin' sheep with sums instead",
        "So if you're restless, if you can't sleep",
        "Just play with numbers 'til the morning creeps",
        "Snap your fingers, swing that beat",
        "Do math, and feel complete!"
    ]
    
    print("=" * 60)
    print("Testing GPT-5 Fragmentation Handling")
    print("=" * 60)
    print(f"\nOriginal lyrics: {len(original_lyrics)} lines")
    print(f"GPT-5 fragments: {len(response['lyrics'])} fragments")
    
    # Parse the fragments
    timed_fragments = []
    for item in response['lyrics']:
        if 'text' in item and 'startMs' in item and 'endMs' in item:
            timed_lyric = TimedLyric(
                text=item['text'],
                start_time=float(item['startMs']) / 1000.0,
                end_time=float(item['endMs']) / 1000.0,
                section_type=None
            )
            timed_fragments.append(timed_lyric)
    
    print(f"\nParsed {len(timed_fragments)} timed fragments")
    
    # Create the assistant and test merging
    assistant = LLMSyncAssistant(provider="openai", model="gpt-5")
    merged_lyrics = assistant._merge_fragmented_lyrics(timed_fragments, original_lyrics)
    
    print(f"\nMerged into {len(merged_lyrics)} complete lyrics")
    
    # Display the results
    print("\n" + "=" * 60)
    print("MERGED RESULTS:")
    print("=" * 60)
    
    for i, lyric in enumerate(merged_lyrics, 1):
        print(f"\n{i}. [{lyric.start_time:.2f}s - {lyric.end_time:.2f}s]")
        print(f"   Original: {original_lyrics[i-1] if i <= len(original_lyrics) else 'N/A'}")
        print(f"   Merged:   {lyric.text}")
        if original_lyrics[i-1] != lyric.text:
            print(f"   ⚠️ Text mismatch!")
    
    # Verify the merge worked correctly
    assert len(merged_lyrics) == len(original_lyrics), f"Expected {len(original_lyrics)} lyrics, got {len(merged_lyrics)}"
    
    # Check some specific merges
    assert merged_lyrics[0].text == "When the night feels endless and I'm wide awake"
    assert merged_lyrics[0].start_time == 6.0
    assert merged_lyrics[0].end_time == 12.34  # End of "wide awake"
    
    assert merged_lyrics[8].text == "Add a slice of lemon, subtract a line of rhyme"
    assert merged_lyrics[9].text == "Square a little laughter, divide it into time"
    assert merged_lyrics[10].text == "Juggle all the fractions 'til the music swings"
    
    # The bridge section that was reordered in GPT-5's response
    assert merged_lyrics[24].text == "So if you're restless, if you can't sleep"
    assert merged_lyrics[25].text == "Just play with numbers 'til the morning creeps"
    
    print("\n" + "=" * 60)
    print("✅ Fragmentation merge test PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_actual_fragmentation()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)