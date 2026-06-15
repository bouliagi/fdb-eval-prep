# Migration to Relative Paths: Summary of Changes

## Overview

Updated the FDB evaluation repository to use relative paths instead of absolute server paths. This enables users to independently download and organize datasets in a `data/` directory without requiring access to specific server locations.

## Changes Made

### 1. Updated All 16 Manifest Files

**What changed:**
- CALLFC paths: `/misc/data4/reco/Audio/callfriend_canfra-2/` → `data/callfc/`
- MEDIA paths: `/misc/data28-brs/ZS-MEDIA/speechbrain/recipes/MEDIA/S0272/` → `data/media/`

**Example:**
```
Before: "source_wav": "/misc/data4/reco/Audio/callfriend_canfra-2/data/fr_5403.wav"
After:  "source_wav": "data/callfc/data/fr_5403.wav"
```

**Files affected:**
- callfc_backchannel_dev/test_manifest.json
- callfc_pause_handling_dev/test_manifest.json
- callfc_smooth_turn_taking_dev/test_manifest.json
- callfc_user_interruption_dev/test_manifest.json
- media_backchannel_dev_manifest.json
- media_pause_handling_dev/test_manifest.json
- media_smooth_turn_taking_dev/test_manifest.json
- media_user_interruption_dev/test_manifest.json

### 2. Updated `scripts/materialize_fdb.py`

**Key changes:**
- Updated docstring to clarify paths are relative to repository root
- Removed `--source_wav_root` argument from `argparse` (no longer needed)
- Made `source_wav_root` parameter optional in `materialize_samples()` for backward compatibility
- Added note in error messages showing resolved path for debugging
- Improved documentation: "Run from repository root"

**Path resolution logic:**
- Paths in manifests are treated as relative to current working directory
- Users must run scripts from repository root
- Symlinks are created with resolved absolute paths

### 3. Updated `examples/reproduce_fdb.sh`

**Key changes:**
- Removed hardcoded `SOURCE_WAV_ROOT` paths
- Added validation that `data/callfc/` or `data/media/` exists before running
- Clear error message if data directories missing
- Removed `--source_wav_root` argument from `materialize_fdb.py` calls
- Updated usage documentation

**New behavior:**
```bash
# Old way: Set SOURCE_WAV_ROOT manually
export SOURCE_WAV_ROOT="/misc/data4/..."

# New way: data/ directories auto-discovered
bash examples/reproduce_fdb.sh callfc dev
# Checks for data/callfc/ and fails with clear error if missing
```

### 4. Updated `README.md`

**New sections added:**
- "Setup: Obtaining and Organizing Source Data" with detailed instructions for:
  - CALLFC dataset download and placement
  - MEDIA dataset download and placement
  - Symlink vs. copy options
  - Verification commands

**Updated Quick Start:**
- Step 1: Download and organize source data (new)
- Step 2: Run end-to-end workflow (updated to reflect new path handling)
- Step 3-4: Unchanged

**Updated Scripts Reference:**
- `materialize_fdb.py`: Clarified relative path behavior, removed `--source_wav_root` docs
- Added note: "Run from repository root"

**Updated Manifest Example:**
- Shows new relative path: `"source_wav": "data/callfc/data/fr_5403.wav"`

## Expected Directory Structure

Users should organize their downloads as:

```
fdb-eval-prep/
├── data/
│   ├── callfc/               ← User downloads and copies here
│   │   ├── data/
│   │   │   ├── fr_5403.wav
│   │   │   ├── fr_5404.wav
│   │   │   └── ...
│   │   └── ...
│   └── media/                ← User downloads and copies here
│       ├── MEDIA1FR_02/
│       ├── MEDIA1FR_01/
│       └── ...
├── manifests/
├── scripts/
├── examples/
└── README.md
```

## Backward Compatibility

- `materialize_fdb.py` still accepts `--source_wav_root` argument (kept for backward compatibility)
- Old scripts passing this argument will still work (it's just ignored)
- Manifest paths are always treated as relative to CWD

## Usage Impact

**Before:**
```bash
# Had to figure out absolute paths
python scripts/materialize_fdb.py \
  --manifest manifests/callfc_backchannel_dev_manifest.json \
  --source_wav_root /misc/data4/reco/Audio/callfriend_canfra-2/data \
  --output_root fdb_output/
```

**After:**
```bash
# Cleaner: just run from repo root
bash examples/reproduce_fdb.sh callfc dev

# Or manual control:
python scripts/materialize_fdb.py \
  --manifest manifests/callfc_backchannel_dev_manifest.json \
  --output_root fdb_output/
```

## Benefits

✓ **Portability**: Works on any machine with source datasets
✓ **Simplicity**: No path configuration needed
✓ **Clarity**: Manifest paths match user directory structure
✓ **Flexibility**: Users can use symlinks or copies
✓ **Error handling**: Clear error if data directories missing

## Testing Performed

- ✓ All 16 manifests updated and verified to use `data/callfc/` and `data/media/` paths
- ✓ Manifest structure validation: all samples have required fields
- ✓ Path normalization: Sample IDs correctly converted (e.g., `#` → `_`, `.` → `-`)
- ✓ Bash syntax validation: reproduce_fdb.sh syntax correct
- ✓ Python imports: manifest loading and path handling validated

## Next Steps for Users

1. Read updated README.md "Setup" section
2. Download CALLFC and/or MEDIA datasets
3. Organize in `data/callfc/` and/or `data/media/`
4. Run `bash examples/reproduce_fdb.sh [dataset] [split]`
5. Populate model outputs and evaluate

