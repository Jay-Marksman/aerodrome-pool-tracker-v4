"""
pool_events_indexer.py

Indexes Aerodrome-style pools on Base into a local SQLite DB.

Tracks:
- Mint (liquidity added)
- Burn (liquidity removed)
- Swap (volume, direction)
- Claim (fee claims)

Run periodically (cron/systemd) or in a screen/tmux session:
    BASE_RPC_URL=<your_rpc> python pool_events_indexer.py
"""

import os
import sqlite3
from datetime import datetime
from typing import List, Optional

from web3 import Web3

# ---------- CONFIG ----------

BASE_RPC_URL = os.environ.get("BASE_RPC_URL", "https://mainnet.base.org")
w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))

DB_PATH = os.environ.get("POOL_EVENTS_DB", "pool_events.db")

# Pools to index (can be overridden by env var or file later)
DEFAULT_POOLS: List[str] = [
    "0x9Da64ed1b87b3d0d3d1E731dd3aAAAc08eb0f5C3",
    "0x80c394f8867e06704d39a5910666a3e71ca7f325",
    "0xdb6556a14976894a01085c2abf3c85c86d1c15c8",
]

# Minimal Aerodrome Pool ABI for events we care about [web:3]
POOL_EVENTS_ABI = [
    # Mint(address sender, uint256 amount0, uint256 amount1, address to, uint256 liquidity)
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount1", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "liquidity", "type": "uint256"},
        ],
        "name": "Mint",
        "type": "event",
    },
    # Burn(address sender, uint256 amount0, uint256 amount1, address to, uint256 liquidity)
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount1", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "liquidity", "type": "uint256"},
        ],
        "name": "Burn",
        "type": "event",
    },
    # Swap(address sender, address recipient, uint256 amount0In, uint256 amount1In, uint256 amount0Out, uint256 amount1Out)
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "recipient", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount0In", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount1In", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount0Out", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount1Out", "type": "uint256"},
        ],
        "name": "Swap",
        "type": "event",
    },
    # Claim(address sender, address recipient, uint256 amount0, uint256 amount1) [web:3]
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "recipient", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount1", "type": "uint256"},
        ],
        "name": "Claim",
        "type": "event",
    },
]

# ---------- DB SETUP ----------


def init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pool_liquidity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pool_address TEXT NOT NULL,
            event_type TEXT NOT NULL,        -- 'ADD' or 'REMOVE'
            token0_amount TEXT NOT NULL,     -- store as string for uint256
            token1_amount TEXT NOT NULL,
            provider_address TEXT NOT NULL,
            tx_hash TEXT NOT NULL,
            block_number INTEGER NOT NULL,
            block_time INTEGER NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pool_swaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pool_address TEXT NOT NULL,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            amount0_in TEXT NOT NULL,
            amount1_in TEXT NOT NULL,
            amount0_out TEXT NOT NULL,
            amount1_out TEXT NOT NULL,
            tx_hash TEXT NOT NULL,
            block_number INTEGER NOT NULL,
            block_time INTEGER NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pool_fee_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pool_address TEXT NOT NULL,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            token0_fee TEXT NOT NULL,
            token1_fee TEXT NOT NULL,
            tx_hash TEXT NOT NULL,
            block_number INTEGER NOT NULL,
            block_time INTEGER NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS indexer_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_block INTEGER NOT NULL
        )
        """
    )
    conn.commit()


def get_start_block(conn: sqlite3.Connection, default_lookback_blocks: int = 200_000) -> int:
    cur = conn.cursor()
    cur.execute("SELECT last_block FROM indexer_state WHERE id = 1")
    row = cur.fetchone()
    current_block = w3.eth.block_number
    if row is None:
        start_block = max(0, current_block - default_lookback_blocks)
        cur.execute(
            "INSERT OR REPLACE INTO indexer_state (id, last_block) VALUES (1, ?)",
            (start_block,),
        )
        conn.commit()
        return start_block
    return row[0]


def update_last_block(conn: sqlite3.Connection, last_block: int) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO indexer_state (id, last_block) VALUES (1, ?)",
        (last_block,),
    )
    conn.commit()


def get_block_timestamp(block_number: int) -> int:
    block = w3.eth.get_block(block_number)
    return int(block.timestamp)


# ---------- INDEXING ----------


def index_pool_events(
    conn: sqlite3.Connection,
    pool_address: str,
    from_block: int,
    to_block: int,
) -> None:
    pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=POOL_EVENTS_ABI)
    cur = conn.cursor()

    # Mint -> ADD liquidity
    mint_events = pool.events.Mint.get_logs(from_block=from_block, to_block=to_block)
    for ev in mint_events:
        block_number = ev["blockNumber"]
        ts = get_block_timestamp(block_number)
        args = ev["args"]
        cur.execute(
            """
            INSERT INTO pool_liquidity_events (
                pool_address, event_type, token0_amount, token1_amount,
                provider_address, tx_hash, block_number, block_time
            ) VALUES (?, 'ADD', ?, ?, ?, ?, ?, ?)
            """,
            (
                pool_address.lower(),
                str(args["amount0"]),
                str(args["amount1"]),
                args["sender"],
                ev["transactionHash"].hex(),
                block_number,
                ts,
            ),
        )

    # Burn -> REMOVE liquidity
    burn_events = pool.events.Burn.get_logs(from_block=from_block, to_block=to_block)
    for ev in burn_events:
        block_number = ev["blockNumber"]
        ts = get_block_timestamp(block_number)
        args = ev["args"]
        cur.execute(
            """
            INSERT INTO pool_liquidity_events (
                pool_address, event_type, token0_amount, token1_amount,
                provider_address, tx_hash, block_number, block_time
            ) VALUES (?, 'REMOVE', ?, ?, ?, ?, ?, ?)
            """,
            (
                pool_address.lower(),
                str(args["amount0"]),
                str(args["amount1"]),
                args["sender"],
                ev["transactionHash"].hex(),
                block_number,
                ts,
            ),
        )

    # Swap -> volume/trades
    swap_events = pool.events.Swap.get_logs(from_block=from_block, to_block=to_block)
    for ev in swap_events:
        block_number = ev["blockNumber"]
        ts = get_block_timestamp(block_number)
        args = ev["args"]
        cur.execute(
            """
            INSERT INTO pool_swaps (
                pool_address, sender, recipient,
                amount0_in, amount1_in, amount0_out, amount1_out,
                tx_hash, block_number, block_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pool_address.lower(),
                args["sender"],
                args["recipient"],
                str(args["amount0In"]),
                str(args["amount1In"]),
                str(args["amount0Out"]),
                str(args["amount1Out"]),
                ev["transactionHash"].hex(),
                block_number,
                ts,
            ),
        )

    # Claim -> fee claims
    claim_events = pool.events.Claim.get_logs(from_block=from_block, to_block=to_block)
    for ev in claim_events:
        block_number = ev["blockNumber"]
        ts = get_block_timestamp(block_number)
        args = ev["args"]
        cur.execute(
            """
            INSERT INTO pool_fee_claims (
                pool_address, sender, recipient, token0_fee, token1_fee,
                tx_hash, block_number, block_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pool_address.lower(),
                args["sender"],
                args["recipient"],
                str(args["amount0"]),
                str(args["amount1"]),
                ev["transactionHash"].hex(),
                block_number,
                ts,
            ),
        )

    conn.commit()


def main(pools: Optional[List[str]] = None) -> None:
    if pools is None:
        pools = DEFAULT_POOLS

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    current_block = w3.eth.block_number
    from_block = get_start_block(conn)
    if from_block >= current_block:
        print("No new blocks to index.")
        conn.close()
        return

    step = 5_000
    for start in range(from_block, current_block + 1, step):
        end = min(start + step - 1, current_block)
        print(f"Indexing blocks {start} -> {end}")
        for pool in pools:
            try:
                index_pool_events(conn, pool, start, end)
            except Exception as e:
                print(f"Error indexing pool {pool} in range {start}-{end}: {e}")
        update_last_block(conn, end)

    conn.close()


if __name__ == "__main__":
    main()

