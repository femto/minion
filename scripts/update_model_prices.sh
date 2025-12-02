#!/bin/bash
#
# Download latest model pricing data from litellm
#
# Usage:
#     ./scripts/update_model_prices.sh
#

set -e

# litellm pricing data URL
URL="https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TARGET_PATH="$PROJECT_ROOT/minion/utils/model_prices_and_context_window.json"

echo "=================================================="
echo "Updating model pricing data from litellm"
echo "=================================================="
echo ""
echo "Source: $URL"
echo "Target: $TARGET_PATH"
echo ""

# Create directory if needed
mkdir -p "$(dirname "$TARGET_PATH")"

# Download with curl or wget (30s timeout)
if command -v curl &> /dev/null; then
    curl -fSL --connect-timeout 10 --max-time 30 "$URL" -o "$TARGET_PATH"
elif command -v wget &> /dev/null; then
    wget -q --timeout=30 "$URL" -O "$TARGET_PATH"
else
    echo "Error: curl or wget required"
    exit 1
fi

# Print stats
MODEL_COUNT=$(grep -c '"input_cost_per_token"' "$TARGET_PATH" 2>/dev/null || echo "?")
echo ""
echo "Done! Downloaded ~$MODEL_COUNT models"
echo ""