# FDB Evaluation Preparation

Lightweight Python scripts and pre-generated manifest files for reproducibly creating French test directories compatible with 
[Full-Duplex-Bench (FDB)](https://github.com/DanielLin94144/Full-Duplex-Bench) from CALLFRIEND French Canadian telephone conversations (CALLFC) and MEDIA spoken dialogue evaluation datasets. 

## Overview

This repository provides the minimal tools needed to materialize FDB evaluation directories for model evaluation. It includes pre-generated manifests for two datasets (CALLFC and MEDIA) across four FDB tasks. The only external requirement is access to the original source audio datasets.

**Supported datasets:** CALLFC, MEDIA  
**Supported tasks:** `backchannel`, `pause_handling`, `smooth_turn_taking`, `user_interruption`  
**Supported splits:** dev, test

## Repository Structure

```
fdb-eval-prep/
├── README.md
├── requirements.txt                   # Python dependencies (numpy only)
├── data/                              # Source datasets (user provides — see Quick Start)
│   ├── callfc/                        # CALLFC dataset directory tree
│   └── media/                         # MEDIA dataset directory tree
├── manifests/                         # Pre-generated manifest JSONs (16 files)
│   ├── callfc_{task}_{split}_manifest.json
│   └── media_{task}_{split}_manifest.json
├── scripts/
│   ├── build_gt_distribution.py       # Build GT distribution from manifest (backchannel only)
│   ├── materialize_fdb.py             # Create FDB directories from manifest (all tasks)
│   └── csv_to_manifest.py             # Helper: regenerate manifests from scored CSVs
└── examples/
    └── reproduce_fdb.sh               # End-to-end example workflow
```

## Installation

### System Requirements

- **sox** (Sound eXchange): Required for audio extraction. Install via:
  ```bash
  # Linux (apt)
  sudo apt-get install sox
  
  # macOS (brew)
  brew install sox
  ```

### Python Dependencies

```bash
git clone <repo_url>
cd fdb-eval-prep
pip install -r requirements.txt
```

## Quick Start

### 1. Organize source data

The manifests reference audio files relative to the repository root under `data/callfc/` and `data/media/`. Create these directories by copying or symlinking the original datasets:

**CALLFC:**
The original dataset is CALLFRIEND Canadian French Second Edition, available from the Linguistic Data Consortium,  [LDC catalog no. LDC2019S18](https://catalog.ldc.upenn.edu/LDC2019S18).
```bash
mkdir -p data/
cp -r /path/to/callfriend_canfra-2 data/callfc
# or: ln -s /path/to/callfriend_canfra-2 data/callfc

ls data/callfc/data/fr_5403.wav  # verify
```

**MEDIA:**
The original dataset is MEDIA speech database for French, available from ELRA, [ID: ELRA-S0272](https://catalogue.elra.info/en-us/repository/browse/ELRA-S0272/).
```bash
mkdir -p data/
cp -r /path/to/MEDIA/S0272 data/media
# or: ln -s /path/to/MEDIA/S0272 data/media

ls data/media/MEDIA1FR_02/MEDIA1FR/BLOCK11/1350.wav  # verify
```

### 2. Materialize FDB directories

Run from the repository root. Dev and test splits are combined per task,
keeping the top-150 samples by quality score (matching the original export
pipeline):

```bash
# CALLFC — all 4 tasks, top-150 per task
bash examples/reproduce_fdb.sh callfc

# MEDIA — same
bash examples/reproduce_fdb.sh media

# Custom cap (e.g. 200 per task, or 0 for no limit)
bash examples/reproduce_fdb.sh callfc 200
bash examples/reproduce_fdb.sh callfc 0
```

This builds the GT distribution for backchannel and materializes all 4 tasks,
producing `fdb_[dataset]/` with one task-named subdirectory per task:

```
fdb_callfc/
├── gt_distribution.json
├── backchannel/
├── pause_handling/
├── smooth_turn_taking/
└── user_interruption/
```

### 3. Add model outputs

For each sample directory, place your model's audio and JSON response:

```bash
cp my_model_output.wav \
   fdb_callfc/backchannel/fr_5403_A_462-775_494-260/output.wav
cp my_model_output.json \
   fdb_callfc/backchannel/fr_5403_A_462-775_494-260/output.json
```

### 4. Evaluate

```bash
python $FDB_EVAL_ROOT/eval_backchannel.py \
  --root_dir fdb_callfc/backchannel
```

## Scripts Reference

### build_gt_distribution.py

Builds ground-truth temporal distribution for the backchannel task.
Accepts one or more manifest files (e.g. dev + test), merges and de-duplicates
samples, applies an optional top-N cap (matching `materialize_fdb.py`), then
bins each sample's backchannel events into 0.2s windows relative to the clip
origin.

```bash
# Combine dev+test, keep top-150 (default):
python scripts/build_gt_distribution.py \
  --manifests manifests/callfc_backchannel_dev_manifest.json \
             manifests/callfc_backchannel_test_manifest.json \
  --output_json fdb_callfc/gt_distribution.json

# Single manifest, no cap:
python scripts/build_gt_distribution.py \
  --manifests manifests/callfc_backchannel_dev_manifest.json \
  --top-n 0 \
  --output_json gt_distribution.json
```

**Arguments:**
- `--manifests` (required): One or more backchannel manifest JSON files
- `--output_json` (required): Output path for `gt_distribution.json`
- `--top-n`: Keep only N highest-scoring samples (default: 150; 0 = unlimited)
- `--window_size`: Bin width in seconds (default 0.2, matches evaluator)

**Output:** JSON mapping normalized sample IDs to lists of bin probabilities

### materialize_fdb.py

Creates FDB directory structure from one or more manifests for any task.
Merges splits, de-duplicates, applies top-N cap, and writes sample directories
under `<output_root>/<task>/`. **Run from repository root.**

```bash
# Combine dev+test for backchannel, top-150:
python scripts/materialize_fdb.py \
  --manifests manifests/callfc_backchannel_dev_manifest.json \
             manifests/callfc_backchannel_test_manifest.json \
  --gt_dist_path fdb_callfc/gt_distribution.json \
  --output_root fdb_callfc/

# Other tasks (no GT distribution needed):
python scripts/materialize_fdb.py \
  --manifests manifests/callfc_pause_handling_dev_manifest.json \
             manifests/callfc_pause_handling_test_manifest.json \
  --output_root fdb_callfc/
```

**Arguments:**
- `--manifests` (required): One or more manifest JSON files (same task+dataset)
- `--output_root` (required): Dataset-level output root; task subdir is created automatically
- `--top-n`: Keep only N highest-scoring samples (default: 150; 0 = unlimited)
- `--gt_dist_path`: Path to `gt_distribution.json` (backchannel only)

**Notes:**
- Audio paths in manifests are relative to repository root
- Duplicate sample IDs across splits are resolved by keeping the highest quality_score
- Output directory is named by task (e.g. `fdb_callfc/backchannel/`)
- **Audio extraction:** For each sample, `materialize_fdb.py` automatically extracts the audio segment from the source wavefile using sox:
  - Extracts mono channel (specified via manifest `src_channel` field or sample ID encoding for CALLFC)
  - Trims to exact start time and duration (specified in manifest)
  - Resamples to 16 kHz
  - Writes extracted audio to `input.wav` in the sample directory
  - This reproduces the original pipeline's segment extraction behavior

### csv_to_manifest.py

Helper script to convert scored CSVs to manifests. Filters by `req_ok=True` and optional quality threshold.

```bash
python scripts/csv_to_manifest.py \
  --csv save/callfc_csv/dev_backchannel_scored.csv \
  --task backchannel \
  --dataset callfc \
  --split dev \
  --output_json callfc_backchannel_dev_manifest.json \
  --quality_threshold 0.0
```

## FDB Output Directory Structure

After running `reproduce_fdb.sh callfc`, the output tree looks like:

```
fdb_callfc/
├── gt_distribution.json         # backchannel GT (used by evaluator, keys are integer indices)
├── backchannel/
│   ├── 0/                        # Integer-indexed sample directories (matching Full-Duplex-Bench)
│   │   ├── metadata.json         # Includes sample_index and original_id for traceability
│   │   └── input.wav             # 16 kHz mono, extracted segment from source
│   ├── 1/
│   │   ├── metadata.json
│   │   └── input.wav
│   └── ...
├── pause_handling/
│   ├── 0/
│   │   ├── metadata.json
│   │   └── input.wav
│   └── ...
├── smooth_turn_taking/
│   └── ...
└── user_interruption/
    └── ...
```

**Directory Naming:**
- Sample directories are named with integer indices (0, 1, 2, ...) in order of quality score (best first)
- This matches the Full-Duplex-Bench convention
- Original sample IDs are preserved in metadata.json for traceability

**metadata.json** contains task-specific fields plus traceability:

Backchannel:
```json
{
  "sample_index": 0,
  "original_id": "fr_5403#A#462.775_494.260",
  "id": "fr_5403_A_462-775_494-260",
  "bc_start": 482.234,
  "bc_end": 483.386,
  "quality_score": 0.8376
}
```

## Manifest Counts

Sample counts per manifest (req_ok=True, quality_score >= 0.0):

**CALLFC:**
- backchannel dev: 17, test: 20
- pause_handling dev: 772, test: 703
- smooth_turn_taking dev: 188, test: 150
- user_interruption dev: 79, test: 104

**MEDIA:**
- backchannel dev: 66, test: 0
- pause_handling dev: 1111, test: 1218
- smooth_turn_taking dev: 281, test: 245
- user_interruption dev: 21, test: 77

## Manifest Format

Manifests are lightweight JSON files containing the minimal information needed for FDB materialization. Paths in manifests are **relative to the repository root**.

### Example (backchannel)

```json
{
  "task": "backchannel",
  "dataset": "callfc",
  "split": "dev",
  "samples": [
    {
      "id": "fr_5403#A#462.775_494.260",
      "bc_start": 482.234,
      "bc_end": 483.386,
      "bc_events": "[[482.234, 482.754], [483.206, 483.386]]",
      "quality_score": 0.8376,
      "start": 462.775,
      "duration": 31.485,
      "source_wav": "data/callfc/data/fr_5403.wav"
    }
  ]
}
```

### Per-sample fields by task

**Common to all tasks:** `id`, `start`, `duration`, `quality_score`, `source_wav`

| Task | Task-specific fields |
|------|---------------------|
| `backchannel` | `bc_start`, `bc_end`, `bc_events` |
| `pause_handling` | `pause_start`, `pause_stop`, `num_pauses`, `pause_events` |
| `smooth_turn_taking` | `turn_start`, `turn_end`, `turn_events` |
| `user_interruption` | `interrupt_start`, `interrupt_end`, `interrupt_events` |

## Technical Details

### GT Distribution Calculation (Backchannel)

GT distribution uses relative times from clip origin (user turn start), with 0.2s bins:

1. Each backchannel event is converted from absolute time to relative time
2. Each event is mapped to one or more bins
3. All bins containing events are incremented by 1.0
4. Distribution is normalized with epsilon smoothing (1e-10)

This matches the evaluator's behavior exactly, ensuring fair JSD scoring.

### Sample ID Normalization

CSV uses format: `fr_5403#A#462.775_494.260`
FDB directories use: `fr_5403_A_462-775_494-260`

Conversion: Replace `#` with `_`, replace `.` with `-`

This ensures FDB directory names match GT distribution keys.

## Updating Manifests

To regenerate manifests with different quality thresholds or from new CSVs:

```bash
python scripts/csv_to_manifest.py \
  --csv /path/to/scored.csv \
  --task backchannel \
  --dataset callfc \
  --split dev \
  --output_json new_manifest.json \
  --quality_threshold 0.5  # Only include samples with quality >= 0.5
```

## Dependencies

- Python 3.6+
- numpy

## License

[Specify license if applicable]

## Contact

For issues or questions, refer to the Full-Duplex-Bench repository:
https://github.com/DanielLin94144/Full-Duplex-Bench
