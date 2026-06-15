#!/bin/bash
# FDB Reproduction: Full End-to-End Workflow
#
# Creates FDB evaluation directories by combining dev and test splits,
# keeping the top-150 best-scoring samples per task (matching the
# original media_fdb_export.py --top-n 150 behaviour).
#
# Prerequisites:
#   - Source datasets organised under data/callfc/ and data/media/
#     (relative to repository root — see README for setup)
#   - Run from the repository root
#
# Usage:
#   bash examples/reproduce_fdb.sh [dataset] [top_n]
#
#   dataset : callfc | media  (default: callfc)
#   top_n   : integer cap per task (default: 150; 0 = unlimited)
#
# Examples:
#   bash examples/reproduce_fdb.sh callfc        # top-150
#   bash examples/reproduce_fdb.sh media 200     # top-200
#   bash examples/reproduce_fdb.sh callfc 0      # no cap

set -e

DATASET="${1:-callfc}"
TOP_N="${2:-150}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${REPO_ROOT}/scripts"
MANIFESTS_DIR="${REPO_ROOT}/manifests"

case "$DATASET" in
  callfc) DATA_DIR="${REPO_ROOT}/data/callfc" ;;
  media)  DATA_DIR="${REPO_ROOT}/data/media"  ;;
  *)
    echo "Error: unknown dataset '${DATASET}' (use callfc or media)"
    exit 1
    ;;
esac

if [ ! -d "$DATA_DIR" ]; then
  echo "Error: data directory not found: $DATA_DIR"
  echo "Please download the dataset and place it at:"
  echo "  data/callfc/   — original CALLFC directory tree"
  echo "  data/media/    — original MEDIA directory tree"
  exit 1
fi

OUTPUT_ROOT="${REPO_ROOT}/fdb_${DATASET}"
TOP_N_ARG="--top-n ${TOP_N}"

echo "============================================================"
echo "FDB Reproduction: ${DATASET}  (top-n=${TOP_N})"
echo "Output root: ${OUTPUT_ROOT}"
echo "============================================================"
echo ""

# ── Step 1: Build GT distribution for backchannel ──────────────
echo "Step 1: Build GT distribution (backchannel)"
echo "----"
GT_JSON="${OUTPUT_ROOT}/gt_distribution.json"
mkdir -p "${OUTPUT_ROOT}"

python "${SCRIPTS_DIR}/build_gt_distribution.py" \
  --manifests \
    "${MANIFESTS_DIR}/${DATASET}_backchannel_dev_manifest.json" \
    "${MANIFESTS_DIR}/${DATASET}_backchannel_test_manifest.json" \
  --output_json "${GT_JSON}" \
  ${TOP_N_ARG}
echo ""

# ── Step 2: Materialize all 4 tasks ───────────────────────────
echo "Step 2: Materialize all 4 tasks"
echo "----"

for task in backchannel pause_handling smooth_turn_taking user_interruption; do
  dev_manifest="${MANIFESTS_DIR}/${DATASET}_${task}_dev_manifest.json"
  test_manifest="${MANIFESTS_DIR}/${DATASET}_${task}_test_manifest.json"

  manifests=""
  [ -f "$dev_manifest" ]  && manifests="$manifests $dev_manifest"
  [ -f "$test_manifest" ] && manifests="$manifests $test_manifest"

  if [ -z "$manifests" ]; then
    echo "⊘ No manifests found for ${task}, skipping"
    continue
  fi

  gt_arg=""
  [ "$task" = "backchannel" ] && gt_arg="--gt_dist_path ${GT_JSON}"

  echo "Materializing ${task}..."
  python "${SCRIPTS_DIR}/materialize_fdb.py" \
    --manifests ${manifests} \
    --output_root "${OUTPUT_ROOT}" \
    ${TOP_N_ARG} \
    ${gt_arg}
  echo ""
done

# ── Step 3: Summary ────────────────────────────────────────────
echo "============================================================"
echo "Done!  FDB directories: ${OUTPUT_ROOT}/"
echo ""
echo "Next steps:"
echo "  1. Populate output.wav and output.json in each sample dir"
echo "  2. Evaluate:"
echo ""
echo "     python \$FDB_EVAL_ROOT/eval_backchannel.py \\"
echo "       --root_dir ${OUTPUT_ROOT}/backchannel"
echo ""
echo "     python \$FDB_EVAL_ROOT/eval_pause_handling.py \\"
echo "       --root_dir ${OUTPUT_ROOT}/pause_handling"
echo ""
echo "     python \$FDB_EVAL_ROOT/eval_smooth_turn_taking.py \\"
echo "       --root_dir ${OUTPUT_ROOT}/smooth_turn_taking"
echo ""
echo "     python \$FDB_EVAL_ROOT/eval_user_interruption.py \\"
echo "       --root_dir ${OUTPUT_ROOT}/user_interruption"
echo ""
