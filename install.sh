#!/bin/bash

# Aerodrome Pool Tracker - Automated Installation Script
# =====================================================
# Clones the repo, installs dependencies, runs indexer,
# and gets you ready to launch the Streamlit app.

set -e  # Exit on any error

echo "🚀 Aerodrome Pool Tracker - Automated Setup"
echo "=============================================="

# ---------- CONFIG ----------
BASE_RPC_URL="${BASE_RPC_URL:-https://mainnet.base.org}"
REPO_URL="https://github.com/Jay-Marksman/aerodrome-pool-tracker-v4.git"
INSTALL_DIR="${INSTALL_DIR:-aerodrome-tracker}"

# ---------- CHECK PYTHON ----------
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python found: $PYTHON_VERSION"

# ---------- CREATE DIRECTORY ----------
if [ -d "$INSTALL_DIR" ]; then
    echo "📁 Directory '$INSTALL_DIR' already exists. Remove it first or choose a different name."
    exit 1
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "📁 Created directory: $INSTALL_DIR"

# ---------- CLONE REPO ----------
echo "📥 Cloning repository..."
git clone "$REPO_URL" . || {
    echo "❌ Failed to clone repository. Check internet connection and repo URL."
    exit 1
}

echo "✅ Repository cloned successfully"

# ---------- PYTHON ENVIRONMENT ----------
echo "🐍 Setting up Python environment..."

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "✅ Dependencies installed"

# ---------- CONFIGURE ----------
echo "⚙️  Configuring environment..."
export BASE_RPC_URL="$BASE_RPC_URL"
echo "BASE_RPC_URL set to: $BASE_RPC_URL"

# ---------- RUN INDEXER ----------
echo ""
echo "🔍 Running pool events indexer (this may take a few minutes)..."
echo "Indexing recent events from Base chain..."

python pool_events_indexer.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Indexer completed successfully!"
    echo "📊 pool_events.db is now populated with on-chain events"
else
    echo "⚠️  Indexer encountered errors but app will still work with DexScreener data"
fi

# ---------- SUCCESS ----------
echo ""
echo "🎉 Installation complete!"
echo ""
echo "📋 To launch the app:"
echo ""
echo "   cd $INSTALL_DIR"
echo "   source .venv/bin/activate"
echo "   streamlit run Aerodrome_Base_v4.py"
echo ""
echo "🌐 Or open in browser:"
echo "   streamlit run Aerodrome_Base_v4.py --server.address 0.0.0.0 --server.port 8501"
echo ""
echo "📝 What you'll see:"
echo "   - ✅ DexScreener pool snapshots (price, liquidity, volume)"
echo "   - ✅ On-chain charts (liquidity changes, swaps, fee claims)"
echo "   - 📝 Sidebar: add any Aerodrome pool address"
echo ""
echo "🔄 To update data later:"
echo "   python pool_events_indexer.py"
echo ""
echo "💡 Pro tip: Run the indexer periodically via cron for fresh on-chain data"
