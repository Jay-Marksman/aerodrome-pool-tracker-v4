***

# Aerodrome Pool Tracker (Base)

A Streamlit dashboard and on‑chain indexer for tracking Aerodrome liquidity pools on the Base network.

The app combines:

- Live pool **snapshots** (price, liquidity, 24h volume, trades) from DexScreener. [docs.dexscreener](https://docs.dexscreener.com/api/reference)
- Historical **on‑chain events** (Mint/Burn/Swap/Claim) indexed from Aerodrome pool contracts on Base. [github](https://github.com/aerodrome-finance/contracts)
- User‑friendly charts for:
  - Liquidity over time  
  - Swap volume over time  
  - Recent pool activity (liquidity adds/removes, fee claims)  
  - Token price mini‑charts with drag‑and‑drop ordering  

***

## 1. Features

- **Multi‑pool overview**
  - Current USD liquidity, token balances, 24h volume and trades from DexScreener. [docs.dexscreener](https://docs.dexscreener.com/api/reference)
  - Default Aerodrome fee settings (stable/volatile) from the Factory contract on Base. [github](https://github.com/aerodrome-finance/contracts)

- **Per‑pool details**
  - Snapshot metrics (price, liquidity, volume, trades).  
  - Latest liquidity adds/removes and fee claims from on‑chain events.  
  - Liquidity‑over‑time chart reconstructed from Mint/Burn.  
  - Swap‑volume‑over‑time chart in real token units using each token’s `decimals()`.

- **Custom charts**
  - Adjustable on‑chain lookback window (e.g., 1–30 days).  
  - Log‑scale toggle for swap volume charts.  
  - Drag‑reorderable token price mini‑charts.

***

## 2. Project Structure

Key files:

- `Aerodrome_Base_v4.py`  
  Streamlit app: UI, DexScreener integration, and chart rendering.

- `pool_events_indexer.py`  
  Background script that reads on‑chain events from Base and stores them in `pool_events.db`.

- `pool_events_reader.py`  
  Read‑only helpers for the UI to query `pool_events.db` and compute time series.

- `requirements.txt`  
  Python dependencies for app and indexer.

- `pool_events.db` (generated)  
  SQLite database containing indexed events.

***

## 3. Prerequisites

- Python 3.10+ recommended.  
- A Base RPC endpoint (public or from a provider like Alchemy/QuickNode).  
  - Example format: `https://mainnet.base.org`. [docs.base](https://docs.base.org/base-chain/quickstart/connecting-to-base)
- Internet access to:
  - DexScreener API: `https://api.dexscreener.com`. [docs.dexscreener](https://docs.dexscreener.com/api/reference)
  - Base RPC endpoint for on‑chain logs.

***

## 4. Installation

1. **Clone or download this repository**

```bash
git clone https://github.com/Jay-Marksman/aerodrome-pool-tracker-v4.git
cd aerodrome-tracker
```

2. **Create and activate a virtual environment (recommended)**

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows (PowerShell)
```

3. **Install dependencies**

Make sure `requirements.txt` contains:

```text
streamlit>=1.32.0
pandas>=2.0.0
requests>=2.31.0
plotly>=5.18.0
web3>=6.11.0
typing_extensions>=4.9.0
```

Then install:

```bash
pip install -r requirements.txt
```

***

## 5. Configuration

### 5.1 Environment variables

At minimum, set your Base RPC endpoint:

```bash
export BASE_RPC_URL="https://mainnet.base.org"
```

Optional:

- `POOL_EVENTS_DB` – custom path for the SQLite DB (defaults to `pool_events.db`).

### 5.2 Default pools

`pool_events_indexer.py` contains a `DEFAULT_POOLS` list:

```python
DEFAULT_POOLS: List[str] = [
    "0x9Da64ed1b87b3d0d3d1E731dd3aAAAc08eb0f5C3",
    "0x80c394f8867e06704d39a5910666a3e71ca7f325",
    "0xdb6556a14976894a01085c2abf3c85c86d1c15c8",
]
```

You can:

- Edit this list directly, **and/or**  
- Paste any Aerodrome pool addresses into the Streamlit sidebar at runtime.

***

## 6. Running the Indexer

The indexer:

- Connects to Base via `BASE_RPC_URL`.  
- Reads `Mint`, `Burn`, `Swap`, and `Claim` events from each pool’s `Pool.sol` contract. [github](https://github.com/aerodrome-finance/contracts/blob/main/contracts/Pool.sol)
- Stores them in `pool_events.db` with an `indexer_state` table to track progress.

### 6.1 One‑time backfill

Run:

```bash
BASE_RPC_URL="https://mainnet.base.org" python pool_events_indexer.py
```

What it does:

- On first run, starts from `current_block - 200_000` (configurable in code).  
- Indexes in chunks (`5_000` blocks at a time).  
- Populates:
  - `pool_liquidity_events` (Mint/Burn).  
  - `pool_swaps` (Swap).  
  - `pool_fee_claims` (Claim).  

You can safely rerun this any time; it resumes from the last indexed block.

### 6.2 Continuous updates

To keep data fresh:

- Run the indexer regularly (e.g., via cron every few minutes), or  
- Keep it running in a long‑lived tmux/screen session.

The Streamlit app reads from the same DB and will show newly indexed events after page reload.

***

## 7. Running the Streamlit App

From the project root, with your virtual environment active:

```bash
streamlit run Aerodrome_Base_v4.py
```

### 7.1 Sidebar controls

- **Aerodrome pool addresses on Base**  
  Paste one pool address per line (0x…), or keep the default sample list.

- **Basescan API Key (optional)**  
  If provided, allows safer future extensions that call Basescan’s API; current version only uses it to cache fee defaults.

- **On-chain lookback (days)**  
  Controls how far back the app queries `pool_events.db` for liquidity and swap events.

- **Refresh Dex data (clear cache)**  
  Clears Streamlit’s cached DexScreener responses and reruns the app.

### 7.2 Main views

1. **Pools Overview**  
   - A sortable table with:
     - Pair name
     - Pool address
     - Token A/B symbols and balances
     - Total liquidity (USD)
     - 24h volume (USD)
     - 24h trades
     - Stable fee %

2. **Global metrics**  
   - Total liquidity (USD) across all pools.  
   - Aggregate 24h volume and trades.

3. **24h Volume by Pool / Liquidity by Pool**  
   - Bar charts using DexScreener snapshot data. [docs.dexscreener](https://docs.dexscreener.com/api/reference)

4. **Per‑Pool Details (with On‑Chain Activity)**  
   For each pool:

   - Snapshot metrics (price, liquidity, volume, trades).  
   - Recent Pool Activity:
     - Latest liquidity added/removed (Mint/Burn).
     - Latest fee claim (Claim).  
   - **Liquidity Over Time (events)**:
     - Line chart of token0/token1 balances reconstructed from Mint/Burn.  
   - **Swap Volume Over Time (events, token units)**:
     - Two lines: token0 volume and token1 volume per hour, scaled by each token’s `decimals()`.  
     - Log‑scale toggle for the y‑axis.

5. **Token Price Charts (Reorder)**  
   - One mini chart per unique token across all pools.  
   - 24h price trend from DexScreener’s token endpoint.  
   - Up/down buttons to reorder chart order.

***

## 8. Data Sources & Credits

This project stands on the work of many others:

- **DexScreener** [dexscreener](https://dexscreener.com)
  - Live pool and token data via `https://api.dexscreener.com`.  
  - Used for:
    - Pair snapshots (price, liquidity, volume, trades).  
    - Token price mini‑charts.  
  - Please review DexScreener’s API Terms & Conditions before heavy use. [docs.dexscreener](https://docs.dexscreener.com/api/api-terms-and-conditions)

- **Aerodrome Finance** [aerodrome](https://aerodrome.finance)
  - Smart contracts and specification:
    - `Pool.sol` (Mint/Burn/Swap/Claim events).  
    - Factory, Router, and related contracts.  
  - The on‑chain indexer is guided by Aerodrome’s public contract interfaces and deployment addresses on Base. [github](https://github.com/aerodrome-finance/contracts)

- **Velodrome & Aerodrome Envio Indexer** [github](https://github.com/velodrome-finance/indexer)
  - A production‑grade, multi‑chain indexer that tracks Velodrome & Aerodrome pools and inspired:
    - The choice of events to index.  
    - The entity-style schema (pools, swaps, liquidity events).

- **Base Network** [docs.base](https://docs.base.org/onchainkit/config/is-base)
  - L2 network on which Aerodrome runs.  
  - This project relies on a Base RPC endpoint for all on‑chain event logs.

- **Open‑source libraries**
  - `web3.py` — EVM RPC and contract calls. [web3py.readthedocs](https://web3py.readthedocs.io/en/v6.14.0/examples.html)
  - `Streamlit` — data app framework for the UI.  
  - `Plotly` — rich charting for time‑series and bar charts.  
  - `pandas` — tabular data manipulation.

Please consider supporting or starring these upstream projects if this dashboard is useful. Their work makes this app possible.

***

## 9. Troubleshooting

- **No events / empty on‑chain charts**
  - Ensure `pool_events_indexer.py` ran successfully at least once.
  - Confirm `POOL_EVENTS_DB` (if set) points to the same DB path for both indexer and app.
  - Check that the pools you track actually have on‑chain activity in the chosen lookback window.

- **Rate limits / API errors**
  - DexScreener has API rate limits; many pools or frequent refreshes may hit limits. [docs.dexscreener](https://docs.dexscreener.com/api/api-terms-and-conditions)
  - Consider caching results, reducing pool count, or spacing refreshes.

- **RPC issues**
  - If the indexer logs errors like “rate limit” or connection failures, switch to a more reliable Base RPC endpoint.

***

## 10. Roadmap Ideas

- Attach USD valuation to swap volumes and liquidity using token prices and decimals.  
- Compute fee‑derived APRs per pool and per LP address (if wallet tracking is added).  
- Integrate a GraphQL‑based indexer (like Envio’s Velodrome/Aerodrome indexer) for more scalable querying. [docs.envio](https://docs.envio.dev/docs/HyperIndex/example-aerodrome-dex-indexer)

If you share feedback or PRs, please also keep the acknowledgments and data source credits intact.
