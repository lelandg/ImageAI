#!/usr/bin/env python3
import json
import collections

# Load the project file
with open('/mnt/d/Documents/Code/GitHub/ImageAI/imageai_current_project.json', 'r') as f:
    data = json.load(f)

scenes = data.get('scenes', [])
print(f'Total scenes: {len(scenes)}')

# Extract durations
durations = [s.get('duration_sec', 0) for s in scenes]
print(f'Unique durations: {set(durations)}')

# Show distribution
print(f'\nDuration distribution:')
counter = collections.Counter(durations)
for dur, count in sorted(counter.items()):
    print(f'  {dur}s: {count} scenes')

# Show first few scenes with their text and duration
print(f'\nFirst 10 scenes:')
for i, scene in enumerate(scenes[:10], 1):
    print(f'{i:2}. Duration: {scene.get("duration_sec", 0):4.1f}s - Text: {scene.get("source", "")[:50]}')

# Check for timing metadata
print(f'\nTiming metadata check:')
for i, scene in enumerate(scenes[:5], 1):
    metadata = scene.get('metadata', {})
    llm_start = metadata.get('llm_start_time', 'N/A')
    llm_end = metadata.get('llm_end_time', 'N/A')
    print(f'{i}. LLM timing: {llm_start} - {llm_end}')