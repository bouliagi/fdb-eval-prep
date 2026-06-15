#!/usr/bin/env python3
"""
Audio extraction utilities for FDB sample materialization.

Extracts mono audio segments from stereo wavefiles using sox,
matching the original media_fdb_prepare.py pipeline behavior.
"""

import re
import subprocess
import sys


def get_channel_from_sample_id(sample_id):
    """
    Parse channel identifier from sample ID.

    Sample IDs have format: <recorder_id>#<channel>#<start_time>_<end_time>
    e.g., "fr_5374#A#1620.241_1627.213" → "A"

    Args:
        sample_id: Sample ID string

    Returns:
        Channel label ("A" or "B")

    Raises:
        ValueError: If channel cannot be parsed
    """
    match = re.match(r"^[^#]+#([AB])#", sample_id)
    if not match:
        raise ValueError(f"Cannot parse channel from sample ID: {sample_id}")
    return match.group(1)


def channel_label_to_index(label):
    """Convert channel label (A/B) to sox remix index (1/2)."""
    return 1 if label.upper() == "A" else 2


def extract_segment(src_wav, channel, start_sec, duration_sec, output_wav, sample_rate=16000):
    """
    Extract a mono segment from a stereo WAV file using sox.

    Extracts the specified channel from the source stereo WAV, windows to
    [start_sec, start_sec + duration_sec], and resamples to sample_rate Hz.

    Args:
        src_wav: Path to source stereo WAV file
        channel: Channel label ("A", "B", "L", "R") or index (1, 2). Can be None for default.
        start_sec: Start time in seconds (absolute in source wav)
        duration_sec: Segment duration in seconds
        output_wav: Path to write extracted mono segment
        sample_rate: Target sample rate in Hz (default: 16000)

    Raises:
        FileNotFoundError: If source WAV not found
        RuntimeError: If sox extraction fails
    """
    # Convert channel label to sox remix index if needed
    if channel is None or channel == '':
        channel_idx = 1  # Default to left/first channel
    elif isinstance(channel, str):
        channel_idx = channel_label_to_index(channel)
    else:
        channel_idx = channel

    try:
        cmd = [
            "sox", src_wav,
            "-r", str(sample_rate),
            "-c", "1",
            output_wav,
            "remix", str(channel_idx),
            "trim", f"{start_sec:.6f}", f"{duration_sec:.6f}",
            "pad", "0", f"{duration_sec:.6f}",
            "trim", "0", f"{duration_sec:.6f}",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            stderr = result.stderr or "(no error message)"
            raise RuntimeError(f"sox extraction failed: {stderr}")

    except FileNotFoundError:
        raise RuntimeError(
            f"sox command not found. Please install sox: "
            f"https://sox.sourceforge.net/sox.html"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"sox extraction timed out after 60 seconds")
    except Exception as e:
        raise RuntimeError(f"sox extraction failed: {e}")


def verify_extraction(output_wav, expected_duration_sec=None, sample_rate=16000):
    """
    Verify extracted audio file using soxi.

    Args:
        output_wav: Path to extracted WAV file
        expected_duration_sec: Expected duration in seconds (optional, for validation)
        sample_rate: Expected sample rate in Hz (default: 16000)

    Returns:
        dict with keys: duration_sec, actual_sample_rate, channels

    Raises:
        RuntimeError: If verification fails
    """
    try:
        # Get duration
        result_dur = subprocess.run(
            ["soxi", "-D", output_wav],
            capture_output=True, text=True, timeout=10
        )
        if result_dur.returncode != 0:
            raise RuntimeError(f"soxi -D failed: {result_dur.stderr}")
        duration = float(result_dur.stdout.strip())

        # Get sample rate
        result_rate = subprocess.run(
            ["soxi", "-r", output_wav],
            capture_output=True, text=True, timeout=10
        )
        if result_rate.returncode != 0:
            raise RuntimeError(f"soxi -r failed: {result_rate.stderr}")
        actual_rate = int(result_rate.stdout.strip())

        # Get channel count
        result_ch = subprocess.run(
            ["soxi", "-c", output_wav],
            capture_output=True, text=True, timeout=10
        )
        if result_ch.returncode != 0:
            raise RuntimeError(f"soxi -c failed: {result_ch.stderr}")
        channels = int(result_ch.stdout.strip())

        info = {
            "duration_sec": duration,
            "actual_sample_rate": actual_rate,
            "channels": channels,
        }

        # Validate if expected values provided
        if expected_duration_sec is not None:
            tol = 0.01  # 10ms tolerance
            if abs(duration - expected_duration_sec) > tol:
                raise RuntimeError(
                    f"Extracted duration {duration:.3f}s does not match "
                    f"expected {expected_duration_sec:.3f}s (tolerance: {tol}s)"
                )

        if actual_rate != sample_rate:
            raise RuntimeError(
                f"Sample rate {actual_rate} does not match expected {sample_rate}"
            )

        if channels != 1:
            raise RuntimeError(f"Expected mono (1 channel), got {channels}")

        return info

    except FileNotFoundError:
        raise RuntimeError(
            f"soxi command not found. Please install sox: "
            f"https://sox.sourceforge.net/sox.html"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("soxi verification timed out after 10 seconds")
    except Exception as e:
        raise RuntimeError(f"soxi verification failed: {e}")
