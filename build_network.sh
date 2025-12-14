#!/bin/bash
#
# SUMO Network Build Script
#
# This script generates SUMO network file from node and edge definition files.
# Must be run before starting training.
#
# Usage:
#   chmod +x build_network.sh
#   ./build_network.sh
#

set -e  # Exit immediately on error

echo "========================================"
echo "  SUMO Network Build Script"
echo "========================================"

# Check if SUMO is installed
if ! command -v netconvert &> /dev/null; then
    echo "Error: netconvert command not found"
    echo "Please ensure SUMO is installed and SUMO_HOME environment variable is set"
    echo ""
    echo "Install SUMO:"
    echo "  Ubuntu: sudo apt-get install sumo sumo-tools"
    echo "  Set environment variable: export SUMO_HOME=/usr/share/sumo"
    exit 1
fi

echo "SUMO installed, version:"
netconvert --version

# Navigate to network directory
cd "$(dirname "$0")/networks"

echo ""
echo "Generating single intersection network..."

# Generate network file
netconvert \
    --node-files=single_intersection.nod.xml \
    --edge-files=single_intersection.edg.xml \
    --output-file=single_intersection.net.xml \
    --tls.guess=true \
    --tls.default-type=static \
    --no-internal-links=false \
    --no-turnarounds=true

if [ -f "single_intersection.net.xml" ]; then
    echo "✓ Network file generated successfully: single_intersection.net.xml"
else
    echo "✗ Network file generation failed"
    exit 1
fi

# Display network information
echo ""
echo "Network information:"
echo "----------------------------------------"
grep -c "<node" single_intersection.net.xml && echo " nodes" || true
grep -c "<edge" single_intersection.net.xml && echo " edges" || true

echo ""
echo "========================================"
echo "  Build Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Activate Python virtual environment"
echo "  2. Run training script:"
echo ""
echo "     python src/train.py \\"
echo "         --net_file networks/single_intersection.net.xml \\"
echo "         --route_file scenarios/morning_rush.rou.xml \\"
echo "         --num_episodes 500"
echo ""
