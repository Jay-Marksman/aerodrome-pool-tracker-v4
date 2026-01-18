"""
pool_events_reader.py

Read-only helpers on top of pool_events.db for Streamlit.
"""

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import pandas as pd

from web3 import Web3  # new import

BASE_RPC_URL = os.environ.get("BASE_RPC_URL", "https://mainnet.base.org")
w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    }
]

_decimals_cache: Dict[str, int] = {}


DB_PATH = os.environ.get("POOL_EVENTS_DB", "pool_events.db")

def get_token_decimals(token_address: str) -> int:
    """
    Fetch token decimals once and cache them.
    Falls back to 18 if the call fails.
    """
    addr = w3.to_checksum_address(token_address)
    if addr in _decimals_cache:
        return _decimals_cache[addr]
    try:
        contract = w3.eth.contract(address=addr, abi=ERC20_ABI)
        decimals = contract.functions.decimals().call()
        _decimals_cache[addr] = int(decimals)
        return int(decimals)
    except Exception:
        _decimals_cache[addr] = 18
        return 18



def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


@dataclass
class RecentActivity:
    pool_address: str
    latest_add: Optional[str]
    latest_remove: Optional[str]
    latest_claim: Optional[str]


def get_recent_activity(pool_address: str, lookback_hours: int = 48) -> RecentActivity:
    conn = _conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    since_ts = int((datetime.utcnow() - timedelta(hours=lookback_hours)).timestamp())
    pool_lower = pool_address.lower()

    # Latest ADD
    cur.execute(
        """
        SELECT token0_amount, token1_amount, provider_address, block_time
        FROM pool_liquidity_events
        WHERE pool_address = ? AND event_type = 'ADD' AND block_time >= ?
        ORDER BY block_time DESC LIMIT 1
        """,
        (pool_lower, since_ts),
    )
    add_row = cur.fetchone()

    # Latest REMOVE
    cur.execute(
        """
        SELECT token0_amount, token1_amount, provider_address, block_time
        FROM pool_liquidity_events
        WHERE pool_address = ? AND event_type = 'REMOVE' AND block_time >= ?
        ORDER BY block_time DESC LIMIT 1
        """,
        (pool_lower, since_ts),
    )
    remove_row = cur.fetchone()

    # Latest Claim
    cur.execute(
        """
        SELECT token0_fee, token1_fee, sender, block_time
        FROM pool_fee_claims
        WHERE pool_address = ? AND block_time >= ?
        ORDER BY block_time DESC LIMIT 1
        """,
        (pool_lower, since_ts),
    )
    claim_row = cur.fetchone()

    def fmt(row, label: str, token0_key: str, token1_key: str, who_key: str) -> Optional[str]:
        if not row:
            return None
        t0 = row[token0_key]
        t1 = row[token1_key]
        who = row[who_key]
        age = datetime.utcnow() - datetime.utcfromtimestamp(row["block_time"])
        hours_ago = int(age.total_seconds() // 3600)
        return f"{label}: token0 {t0} / token1 {t1} by {who} ({hours_ago}h ago)"

    activity = RecentActivity(
        pool_address=pool_address,
        latest_add=fmt(add_row, "Liquidity Added", "token0_amount", "token1_amount", "provider_address"),
        latest_remove=fmt(
            remove_row, "Liquidity Removed", "token0_amount", "token1_amount", "provider_address"
        ),
        latest_claim=fmt(claim_row, "Fees Claimed", "token0_fee", "token1_fee", "sender"),
    )

    conn.close()
    return activity


def get_liquidity_timeseries(pool_address: str, lookback_days: int = 7) -> pd.DataFrame:
    """
    Reconstruct cumulative balances for token0/token1 from Mint/Burn.
    """
    conn = _conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    since_ts = int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())
    pool_lower = pool_address.lower()

    cur.execute(
        """
        SELECT event_type, token0_amount, token1_amount, block_time
        FROM pool_liquidity_events
        WHERE pool_address = ? AND block_time >= ?
        ORDER BY block_time ASC
        """,
        (pool_lower, since_ts),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame(columns=["time", "token0_balance", "token1_balance"])

    t0 = 0
    t1 = 0
    out: List[Dict] = []
    for r in rows:
        amt0 = int(r["token0_amount"])
        amt1 = int(r["token1_amount"])
        if r["event_type"] == "ADD":
            t0 += amt0
            t1 += amt1
        else:
            t0 -= amt0
            t1 -= amt1
        out.append(
            {
                "time": datetime.utcfromtimestamp(r["block_time"]),
                "token0_balance": t0,
                "token1_balance": t1,
            }
        )
    return pd.DataFrame(out)


def get_swap_volume_timeseries(
    pool_address: str,
    token0_address: str,
    token1_address: str,
    lookback_days: int = 7,
) -> pd.DataFrame:
    """
    Aggregate swap amounts by hour in *token units* for token0 and token1,
    using real decimals per token.
    """
    conn = _conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    since_ts = int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())
    pool_lower = pool_address.lower()

    cur.execute(
        """
        SELECT amount0_in, amount1_in, amount0_out, amount1_out, block_time
        FROM pool_swaps
        WHERE pool_address = ? AND block_time >= ?
        ORDER BY block_time ASC
        """,
        (pool_lower, since_ts),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame(columns=["time", "token0_volume", "token1_volume"])

    # get decimals per token
    dec0 = get_token_decimals(token0_address)
    dec1 = get_token_decimals(token1_address)
    scale0 = 10**dec0
    scale1 = 10**dec1

    records: List[Dict] = []
    for r in rows:
        t = datetime.utcfromtimestamp(r["block_time"]).replace(
            minute=0, second=0, microsecond=0
        )
        token0 = (int(r["amount0_in"]) + int(r["amount0_out"])) / scale0
        token1 = (int(r["amount1_in"]) + int(r["amount1_out"])) / scale1
        records.append({"time": t, "token0_volume": token0, "token1_volume": token1})

    df = pd.DataFrame(records)
    df = df.groupby("time", as_index=False)[["token0_volume", "token1_volume"]].sum()
    return df

