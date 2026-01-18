Copy the install.sh file to your home directory.

Make it executable and run:

    '''
    chmod +x install.sh
    ./install.sh
    '''

What it does (step by step):

 ✅ Checks Python 3 is installed.

 ✅ Creates directory aerodrome-tracker (or your INSTALL_DIR).

 ✅ Clones https://github.com/Jay-Marksman/aerodrome-pool-tracker-v4.

 ✅ Creates virtual environment .venv.

 ✅ Installs all dependencies from requirements.txt.

 ✅ Runs indexer to populate pool_events.db with on‑chain events.

 ✅ Shows clear next steps to launch the app.

Features:

   Error handling – exits cleanly on failures.

   Respectful – warns if directory exists, doesn't overwrite.

   Configurable – BASE_RPC_URL and INSTALL_DIR via env vars.

   Informative – shows progress and what to expect.

   Production ready – activates venv, upgrades pip first.

Optional environment variables:

    '''
    # Use a different Base RPC (Alchemy, QuickNode, etc.)
    export BASE_RPC_URL="https://base-mainnet.g.alchemy.com/v2/YOUR_KEY"

    # Use a different install directory
    export INSTALL_DIR="my-aerodrome-dashboard"

    ./install.sh
    '''

After rinning:

    '''
    cd aerodrome-tracker
    source .venv/bin/activate
    streamlit run Aerodrome_Base_v4.py
    '''
Everything will be ready – DexScreener snapshots + on‑chain charts with real token decimals and log scale!

Note: The script assumes the repo has all files (Aerodrome_Base_v4.py, pool_events_indexer.py, etc.). If you add more files later, git pull in the directory and rerun the indexer.
