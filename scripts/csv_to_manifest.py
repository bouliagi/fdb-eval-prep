#!/usr/bin/env python3
"""
Convert scored CSV to manifest JSON.

Reads a scored CSV file, filters by req_ok=True and quality_score threshold,
extracts task-specific fields, and outputs a lightweight manifest JSON file.

Usage:
    python csv_to_manifest.py \
        --csv dev_backchannel_scored.csv \
        --task backchannel \
        --dataset callfc \
        --split dev \
        --output_json callfc_backchannel_dev_manifest.json \
        --quality_threshold 0.5
"""

import csv
import json
import argparse
from pathlib import Path


# CSV field names for each task
TASK_FIELDS = {
    "backchannel": {
        "required": ["ID", "bc_start", "bc_end", "bc_events", "quality_score", "req_ok", "src_wav"],
        "optional": [],
    },
    "pause_handling": {
        "required": ["ID", "pause_start", "pause_stop", "quality_score", "req_ok", "src_wav"],
        "optional": ["num_pauses", "pause_events"],
    },
    "smooth_turn_taking": {
        "required": ["ID", "quality_score", "req_ok", "src_wav"],
        "optional": ["turn_events"],  # May need to determine start/end from elsewhere
    },
    "user_interruption": {
        "required": ["ID", "quality_score", "req_ok", "src_wav"],
        "optional": ["interrupt_events"],
    },
}

# For tasks without explicit start/end, use the sample start/stop times
FALLBACK_START_STOP = {
    "smooth_turn_taking": ("start", "stop"),  # Use start/stop from CSV
    "user_interruption": ("start", "stop"),   # Use start/stop from CSV
}


def parse_float(value):
    """Parse a string to float, returning None if invalid."""
    if not value or value.strip() == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def csv_dict_reader(csv_path):
    """Read CSV and yield rows as dicts."""
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def extract_sample(row, task):
    """Extract sample data from CSV row for a task.
    
    Args:
        row: CSV row as dict
        task: Task name
    
    Returns:
        Dict with sample data, or None if required fields missing
    """
    sample = {
        "id": row.get("ID", "").strip(),
        "quality_score": parse_float(row.get("quality_score")),
        "source_wav": row.get("src_wav", "").strip() if row.get("src_wav") else None,
    }
    
    if not sample["id"]:
        return None
    
    if task == "backchannel":
        sample.update({
            "bc_start": parse_float(row.get("bc_start")),
            "bc_end": parse_float(row.get("bc_end")),
            "bc_events": row.get("bc_events", "").strip(),
            "start": parse_float(row.get("start")),  # Clip origin
            "duration": parse_float(row.get("duration")),  # Clip duration
            "src_channel": row.get("src_channel", "").strip(),  # Channel for extraction
        })
    
    elif task == "pause_handling":
        sample.update({
            "pause_start": parse_float(row.get("pause_start")),
            "pause_stop": parse_float(row.get("pause_stop")),
            "num_pauses": int(row.get("num_pauses", 0)) if row.get("num_pauses") else 0,
            "pause_events": row.get("pause_events", "").strip() if row.get("pause_events") else "",
            "start": parse_float(row.get("start")),
            "duration": parse_float(row.get("duration")),
        })
    
    elif task == "smooth_turn_taking":
        sample.update({
            "turn_start": parse_float(row.get("start")),
            "turn_end": parse_float(row.get("stop")),
            "turn_events": row.get("turn_events", "").strip() if row.get("turn_events") else "",
            "start": parse_float(row.get("start")),
            "duration": parse_float(row.get("duration")),
        })
    
    elif task == "user_interruption":
        sample.update({
            "interrupt_start": parse_float(row.get("start")),
            "interrupt_end": parse_float(row.get("stop")),
            "interrupt_events": row.get("interrupt_events", "").strip() if row.get("interrupt_events") else "",
            "start": parse_float(row.get("start")),
            "duration": parse_float(row.get("duration")),
        })
    
    return sample


def csv_to_manifest(csv_path, task, dataset, split, quality_threshold=0.0):
    """Convert CSV to manifest format.
    
    Args:
        csv_path: Path to scored CSV
        task: Task name
        dataset: Dataset name (callfc, media, etc.)
        split: Split name (dev, test)
        quality_threshold: Minimum quality_score to include (0.0 = all)
    
    Returns:
        Manifest dict
    """
    if task not in TASK_FIELDS:
        raise ValueError(f"Unknown task: {task}")
    
    samples = []
    skipped_no_req = 0
    skipped_quality = 0
    skipped_no_wav = 0
    
    for row in csv_dict_reader(csv_path):
        # Check req_ok
        req_ok = row.get("req_ok", "").lower().strip() in ("true", "1", "yes")
        if not req_ok:
            skipped_no_req += 1
            continue
        
        # Extract sample
        sample = extract_sample(row, task)
        if not sample:
            continue
        
        # Check quality score
        if sample["quality_score"] is not None and sample["quality_score"] < quality_threshold:
            skipped_quality += 1
            continue
        
        # Check source wav
        if not sample["source_wav"]:
            skipped_no_wav += 1
            continue
        
        samples.append(sample)
    
    manifest = {
        "task": task,
        "dataset": dataset,
        "split": split,
        "samples": samples,
    }
    
    print(f"Converted {csv_path}")
    print(f"  ✓ {len(samples)} samples passed filters")
    print(f"  ⊘ {skipped_no_req} samples had req_ok=False")
    print(f"  ⊘ {skipped_quality} samples below quality threshold ({quality_threshold})")
    print(f"  ⊘ {skipped_no_wav} samples missing source_wav")
    
    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Convert scored CSV to manifest JSON"
    )
    parser.add_argument("--csv", required=True, help="Path to scored CSV")
    parser.add_argument("--task", required=True, 
                        choices=list(TASK_FIELDS.keys()),
                        help="Task name")
    parser.add_argument("--dataset", required=True, help="Dataset name (callfc, media, etc.)")
    parser.add_argument("--split", required=True, help="Split name (dev, test, etc.)")
    parser.add_argument("--output_json", required=True, help="Output manifest JSON path")
    parser.add_argument("--quality_threshold", type=float, default=0.0,
                        help="Minimum quality_score to include (default 0.0 = all)")
    
    args = parser.parse_args()
    
    # Convert
    manifest = csv_to_manifest(
        args.csv,
        args.task,
        args.dataset,
        args.split,
        quality_threshold=args.quality_threshold
    )
    
    # Write output
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✓ Manifest written to: {args.output_json}")


if __name__ == "__main__":
    main()
