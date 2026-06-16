# FDB Manifest JSON Schema

## Overview
Manifest files are lightweight JSON representations derived from scored CSVs. They contain only the minimal fields needed for FDB directory materialization and evaluation.

## Common Fields (All Tasks)
```
{
  "task": "backchannel|pause_handling|smooth_turn_taking|user_interruption",
  "dataset": "callfc|media",
  "split": "dev|test",
  "samples": [
    {
      "id": "fr_5403#A#462.775_494.260",      # Sample identifier from CSV ID column
      "quality_score": 0.8376,                 # From quality_score column
      "source_wav": "/misc/data4/reco/...",   # From src_wav column
      ...
    }
  ]
}
```

## Task-Specific Fields

### Backchannel
Per-sample fields:
- `bc_start`: float, start time of first backchannel event (seconds)
- `bc_end`: float, end time of first backchannel event (seconds)
- `bc_events`: string, JSON-encoded list of all backchannel events [[s1, e1], [s2, e2], ...]

Example:
```json
{
  "id": "fr_5403#A#462.775_494.260",
  "bc_start": 482.234,
  "bc_end": 483.386,
  "bc_events": "[[482.234, 482.754], [483.206, 483.386], ...]",
  "quality_score": 0.8376,
  "source_wav": "/misc/data4/reco/Audio/callfriend_canfra-2/data/fr_5403.wav"
}
```

### Pause Handling
Per-sample fields:
- `pause_start`: float, start of pause event (seconds)
- `pause_stop`: float, end of pause event (seconds)
- `num_pauses`: int, number of pauses in this sample
- `pause_events`: string (optional), JSON-encoded list of pause events if available

Example:
```json
{
  "id": "fr_5403#A#1166.514_1177.044",
  "pause_start": 5.36,
  "pause_stop": 6.096,
  "num_pauses": 1,
  "pause_events": "[[5.36, 6.096]]",
  "quality_score": 0.75,
  "source_wav": "/misc/data4/reco/Audio/callfriend_canfra-2/data/fr_5403.wav"
}
```

### Smooth Turn-Taking
Per-sample fields:
- `turn_start`: float, start of turn-taking moment (seconds)
- `turn_end`: float, end of turn-taking moment (seconds)
- `turn_events`: string (optional), JSON-encoded list of turn events if available

Example:
```json
{
  "id": "fr_5382#A#915.184_922.727",
  "turn_start": 915.184,
  "turn_end": 922.727,
  "turn_events": "[[915.184, 922.727]]",
  "quality_score": 0.72,
  "source_wav": "/misc/data4/reco/Audio/callfriend_canfra-2/data/fr_5382.wav"
}
```

### User Interruption
Per-sample fields:
- `interrupt_start`: float, start of interruption (seconds)
- `interrupt_end`: float, end of interruption (seconds)
- `interrupt_events`: string (optional), JSON-encoded list of interruption events if available

Example:
```json
{
  "id": "fr_5480#A#790.050_791.140",
  "interrupt_start": 790.050,
  "interrupt_end": 791.140,
  "interrupt_events": "[[790.050, 791.140]]",
  "quality_score": 0.68,
  "source_wav": "/misc/data4/reco/Audio/callfriend_canfra-2/data/fr_5480.wav"
}
```

## Notes
1. Event fields (bc_events, pause_events, etc.) are JSON-encoded strings to maintain compatibility with CSV format
2. start/stop fields match the time boundaries used in the CSV
3. quality_score is always included for potential filtering
4. source_wav paths are absolute paths to source wavefiles in the original dataset
5. All times are in seconds, matching the source audio sampling rate used in preparation
