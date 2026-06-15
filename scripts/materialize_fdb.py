#!/usr/bin/env python3
"""
Materialize FDB directory structure from one or more manifest JSONs.

Reads task-specific manifests (one per split, same task+dataset), merges
samples across splits, de-duplicates by sample ID (highest quality_score kept),
applies an optional top-N cap, then creates FDB sample directories under
  <output_root>/<task>/

Source audio paths in manifests are relative to the repository root.
Run this script from the repository root directory.

Usage:
    # Combine dev+test, keep top-150, name dir by task:
    python scripts/materialize_fdb.py \\
        --manifests manifests/callfc_backchannel_dev_manifest.json \\
                   manifests/callfc_backchannel_test_manifest.json \\
        --gt_dist_path fdb_callfc/gt_distribution.json \\
        --output_root fdb_callfc/

    # Single manifest, no cap:
    python scripts/materialize_fdb.py \\
        --manifests manifests/callfc_pause_handling_dev_manifest.json \\
        --top-n 0 \\
        --output_root fdb_callfc/
"""

import json
import argparse
import shutil
import sys
from pathlib import Path

from audio_extract import extract_segment, get_channel_from_sample_id, verify_extraction


# Task-specific metadata schemas (which manifest fields to include in metadata.json)
TASK_METADATA_SCHEMA = {
    "backchannel": ["id", "bc_start", "bc_end", "quality_score"],
    "pause_handling": ["id", "pause_start", "pause_stop", "num_pauses", "quality_score"],
    "smooth_turn_taking": ["id", "turn_start", "turn_end", "quality_score"],
    "user_interruption": ["id", "interrupt_start", "interrupt_end", "quality_score"],
}

DEFAULT_TOP_N = 150


def normalize_sample_id(csv_id):
    """Convert CSV format (fr_5403#A#462.775_494.260) to FDB format (fr_5403_A_462-775_494-260)."""
    return csv_id.replace("#", "_").replace(".", "-")


def load_manifest(manifest_path):
    """Load manifest JSON file."""
    with open(manifest_path) as f:
        return json.load(f)


def select_samples(manifest_paths, top_n=DEFAULT_TOP_N):
    """Load, merge, de-duplicate, and cap samples from one or more manifests.

    All manifests must share the same task and dataset.  When the same sample
    ID appears in multiple manifests (e.g. dev and test) the entry with the
    highest quality_score is kept.  Samples are then sorted descending by
    quality_score (ascending normalized ID as tie-breaker) and capped at top_n.

    Args:
        manifest_paths: iterable of paths to manifest JSON files
        top_n: maximum number of samples to return per task (0 or None = unlimited)

    Returns:
        (task, dataset, samples_list) where samples_list is ordered best-first
    """
    task = None
    dataset = None
    seen = {}  # normalized_id -> sample dict

    for path in manifest_paths:
        manifest = load_manifest(path)

        if task is None:
            task = manifest["task"]
            dataset = manifest["dataset"]
        else:
            if manifest["task"] != task:
                raise ValueError(
                    f"Manifest task mismatch: expected '{task}', got '{manifest['task']}' in {path}"
                )
            if manifest["dataset"] != dataset:
                raise ValueError(
                    f"Manifest dataset mismatch: expected '{dataset}', got '{manifest['dataset']}' in {path}"
                )

        for sample in manifest.get("samples", []):
            fdb_id = normalize_sample_id(sample["id"])
            quality = sample.get("quality_score") or 0.0
            if fdb_id not in seen or quality > (seen[fdb_id].get("quality_score") or 0.0):
                seen[fdb_id] = sample

    # Sort: best quality first, then alphabetical ID as tie-breaker
    ranked = sorted(
        seen.values(),
        key=lambda s: (-(s.get("quality_score") or 0.0), normalize_sample_id(s["id"])),
    )

    if top_n:
        ranked = ranked[:top_n]

    return task, dataset, ranked


def get_metadata_schema(task):
    """Get metadata schema for a task."""
    if task not in TASK_METADATA_SCHEMA:
        raise ValueError(f"Unknown task: {task}. Must be one of {list(TASK_METADATA_SCHEMA.keys())}")
    return TASK_METADATA_SCHEMA[task]


def build_metadata(sample, task):
    """Extract task-specific metadata fields from a sample."""
    schema = get_metadata_schema(task)
    return {field: sample[field] for field in schema if field in sample}


def materialize_samples(manifest_paths, output_root, top_n=DEFAULT_TOP_N, gt_dist_path=None):
    """Create FDB directory structure from one or more manifests.

    Output is placed under <output_root>/<task>/ to match the original
    media_fdb_export.py naming convention.

    Args:
        manifest_paths: iterable of manifest JSON paths (same task/dataset)
        output_root: dataset-level output root (e.g. fdb_callfc/)
        top_n: keep only the N best-scoring samples (0 or None = unlimited)
        gt_dist_path: path to gt_distribution.json (backchannel only)
    """
    task, dataset, samples = select_samples(manifest_paths, top_n=top_n)

    task_dir = Path(output_root) / task
    task_dir.mkdir(parents=True, exist_ok=True)

    cap_note = f" (top-{top_n})" if top_n else ""
    print(f"Materializing {len(samples)} samples{cap_note} → {task_dir}")

    for i, sample in enumerate(samples):
        # Use integer index as directory name (matching Full-Duplex-Bench convention)
        sample_dir = task_dir / str(i)
        sample_dir.mkdir(parents=True, exist_ok=True)

        # Write metadata.json (include original sample ID for reference)
        metadata_path = sample_dir / "metadata.json"
        metadata = build_metadata(sample, task)
        # Add sample_index and original_id for traceability
        metadata["sample_index"] = i
        metadata["original_id"] = sample["id"]
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Extract audio segment from source WAV
        source_wav_path = sample.get("source_wav")
        if source_wav_path:
            source_wav = Path(source_wav_path)
            if not source_wav.exists():
                print(f"  ⚠ {sample['id']}: source wav not found at {source_wav.resolve()}")
            else:
                try:
                    # Get channel from multiple sources
                    channel = None
                    
                    # First, check if channel is in the manifest
                    if "src_channel" in sample and sample["src_channel"]:
                        channel = sample["src_channel"]
                    # Otherwise, try to parse from sample ID (e.g., "fr_5403#A#...")
                    else:
                        try:
                            channel = get_channel_from_sample_id(sample["id"])
                        except ValueError:
                            # If parsing fails, channel will remain None (defaults to 1)
                            pass
                    
                    start_sec = sample.get("start")
                    duration_sec = sample.get("duration")

                    if start_sec is None or duration_sec is None:
                        print(f"  ⚠ {sample['id']}: missing start or duration metadata")
                    else:
                        input_wav = sample_dir / "input.wav"
                        extract_segment(
                            str(source_wav),
                            channel,
                            start_sec,
                            duration_sec,
                            str(input_wav),
                            sample_rate=16000,
                        )

                        # Verify extraction succeeded
                        verify_extraction(str(input_wav), expected_duration_sec=duration_sec)

                except Exception as e:
                    print(f"  ⚠ {sample['id']}: extraction failed: {e}", file=sys.stderr)

        if (i + 1) % max(1, len(samples) // 10) == 0:
            print(f"  ✓ {i + 1}/{len(samples)}")

    # Copy GT distribution for backchannel
    if task == "backchannel" and gt_dist_path:
        gt_dist_path = Path(gt_dist_path)
        if gt_dist_path.exists():
            dst = task_dir / "gt_distribution.json"
            shutil.copy(gt_dist_path, dst)
            print(f"✓ GT distribution → {dst}")
        else:
            print(f"⚠ GT distribution not found at {gt_dist_path}")

    print(f"✓ Done: {task_dir}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Materialize FDB directory structure from manifest JSON(s). "
            "Run from repository root."
        )
    )
    # Accept --manifests (canonical) or --manifest (singular, backward compat)
    parser.add_argument(
        "--manifests", "--manifest",
        dest="manifests",
        nargs="+",
        required=True,
        metavar="MANIFEST",
        help="One or more manifest JSON files (same task+dataset, one per split).",
    )
    parser.add_argument(
        "--output_root",
        required=True,
        help="Dataset-level output root (e.g. fdb_callfc/). Task subdir is created automatically.",
    )
    parser.add_argument(
        "--gt_dist_path",
        help="Path to gt_distribution.json (backchannel only).",
    )
    parser.add_argument(
        "--top-n",
        dest="top_n",
        type=int,
        default=DEFAULT_TOP_N,
        metavar="N",
        help=(
            f"Keep only the N highest-scoring samples after merging splits "
            f"(default: {DEFAULT_TOP_N}; 0 = unlimited)."
        ),
    )

    args = parser.parse_args()

    top_n = args.top_n if args.top_n and args.top_n > 0 else None

    materialize_samples(
        manifest_paths=args.manifests,
        output_root=args.output_root,
        top_n=top_n,
        gt_dist_path=args.gt_dist_path,
    )


if __name__ == "__main__":
    main()

