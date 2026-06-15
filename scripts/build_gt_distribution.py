#!/usr/bin/env python3
"""
Build ground-truth distribution for backchannel task from one or more manifests.

Reads backchannel manifest JSON(s), merges and de-duplicates samples across
splits (same logic as materialize_fdb.py), bins each sample's events into 0.2s
windows relative to the clip origin, and writes gt_distribution.json.

The sample selection (merge + de-dup + top-N) is identical to materialize_fdb.py
so that GT distribution keys always match the materialized directory names.

Usage:
    # Combine dev+test, keep top-150 (default):
    python scripts/build_gt_distribution.py \\
        --manifests manifests/callfc_backchannel_dev_manifest.json \\
                   manifests/callfc_backchannel_test_manifest.json \\
        --output_json fdb_callfc/gt_distribution.json

    # Single manifest, no cap:
    python scripts/build_gt_distribution.py \\
        --manifests manifests/callfc_backchannel_dev_manifest.json \\
        --top-n 0 \\
        --output_json gt_distribution.json
"""

import json
import argparse
import sys
from pathlib import Path

import numpy as np

# Import shared sample-selection logic from materialize_fdb
sys.path.insert(0, str(Path(__file__).parent))
from materialize_fdb import select_samples, normalize_sample_id, DEFAULT_TOP_N


WINDOW_SIZE = 0.2  # seconds, matches eval_backchannel.py default
EPSILON = 1e-10    # matches evaluator's smoothing


def parse_events(events_str):
    """Parse events JSON string to list of [start, end] pairs."""
    if not events_str or not events_str.strip():
        return []
    try:
        events = json.loads(events_str)
        if isinstance(events, list):
            return events
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def compute_gt_distribution(manifest_paths, top_n=DEFAULT_TOP_N, window_size=WINDOW_SIZE):
    """Compute ground-truth distribution for a set of backchannel manifests.

    Uses the same select_samples() call as materialize_fdb.py so GT keys
    always match the materialized directory indices (0, 1, 2, ...).

    Args:
        manifest_paths: iterable of backchannel manifest paths
        top_n: top-N cap passed to select_samples (0 or None = unlimited)
        window_size: bin width in seconds

    Returns:
        Dict mapping integer index (as string) to list of bin probabilities
    """
    task, _dataset, samples = select_samples(manifest_paths, top_n=top_n)

    if task != "backchannel":
        raise ValueError(f"Manifest task is '{task}', expected 'backchannel'")

    gt_dist = {}

    for idx, sample in enumerate(samples):
        # Use integer index as key (matching directory naming in materialize_fdb.py)
        idx_key = str(idx)

        clip_origin = sample.get("start")
        clip_duration = sample.get("duration")

        # Fall back to deriving timing from events if fields missing
        events = parse_events(sample.get("bc_events", ""))
        if not events:
            bc_start = sample.get("bc_start")
            bc_end = sample.get("bc_end")
            if bc_start is not None and bc_end is not None:
                events = [[bc_start, bc_end]]

        if clip_origin is None or clip_duration is None:
            if not events:
                gt_dist[idx_key] = []
                continue
            clip_origin = min(e[0] for e in events)
            clip_duration = max(e[1] for e in events) - clip_origin

        if not events:
            gt_dist[idx_key] = []
            continue

        # Build bins
        n_bins = int(np.ceil(clip_duration / window_size)) + 1
        bins = [0.0] * n_bins

        for event_start, event_end in events:
            rel_start = event_start - clip_origin
            rel_end = event_end - clip_origin
            i_start = int(rel_start / window_size)
            i_end = int(rel_end / window_size)
            for i in range(max(0, i_start), min(n_bins, i_end + 1)):
                bins[i] += 1.0

        # Epsilon smoothing + normalise
        dist = [v + EPSILON for v in bins]
        total = sum(dist)
        gt_dist[idx_key] = [v / total for v in dist]

    return gt_dist


def main():
    parser = argparse.ArgumentParser(
        description="Build ground-truth distribution for backchannel from manifest(s)"
    )
    parser.add_argument(
        "--manifests", "--manifest",
        dest="manifests",
        nargs="+",
        required=True,
        metavar="MANIFEST",
        help="One or more backchannel manifest JSON files.",
    )
    parser.add_argument(
        "--output_json",
        required=True,
        help="Output gt_distribution.json path.",
    )
    parser.add_argument(
        "--window_size",
        type=float,
        default=WINDOW_SIZE,
        help=f"Binning window size in seconds (default {WINDOW_SIZE}).",
    )
    parser.add_argument(
        "--top-n",
        dest="top_n",
        type=int,
        default=DEFAULT_TOP_N,
        metavar="N",
        help=(
            f"Keep only the N highest-scoring samples after merging splits "
            f"(default: {DEFAULT_TOP_N}; 0 = unlimited). Must match the value "
            "used for materialize_fdb.py."
        ),
    )

    args = parser.parse_args()
    top_n = args.top_n if args.top_n and args.top_n > 0 else None

    gt_dist = compute_gt_distribution(
        manifest_paths=args.manifests,
        top_n=top_n,
        window_size=args.window_size,
    )

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(gt_dist, f, indent=2)

    print(f"✓ GT distribution: {len(gt_dist)} samples → {output_path}")


if __name__ == "__main__":
    main()

