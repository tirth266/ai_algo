"""
Paper Trading Persistence Store
================================

Provides a SQLite-backed persistence layer for the paper trading engine.
All positions and trades survive restarts.

The Store is intentionally self-contained (stdlib only — no SQLAlchemy
dependency) so it works even when the main application DB is not reachable.

Schema
──────
paper_positions
  id            INTEGER PRIMARY KEY AUTOINCREMENT
  symbol        TEXT    NOT NULL UNIQUE      ← one row per instrument
  side          TEXT    NOT NULL             'LONG' or 'SHORT'
  quantity      INTEGER NOT NULL DEFAULT 0
  entry_price   REAL    NOT NULL             ← average entry (VWAP)
  stop_loss     REAL                         from signal metadata
  take_profit   REAL
  strategy_name TEXT
  signal_price  REAL                         original signal price
  slippage_pct  REAL                         actual fill slippage %
  opened_at     TEXT    NOT NULL             ISO-8601 UTC
  updated_at    TEXT    NOT NULL             ISO-8601 UTC

paper_trades
  id            INTEGER PRIMARY KEY AUTOINCREMENT
  symbol        TEXT    NOT NULL
  side          TEXT    NOT NULL             'BUY' or 'SELL'  (entry leg)
  quantity      INTEGER NOT NULL
  signal_price  REAL    NOT NULL
  executed_price REAL   NOT NULL             fill price after slippage
  slippage_pct  REAL                         slippage as fraction
  slippage_inr  REAL                         ₹ slippage cost
  exit_price    REAL                         NULL while open
  pnl           REAL    DEFAULT 0            realised on close
  status        TEXT    NOT NULL DEFAULT 'open'  'open' | 'closed'
  exit_reason   TEXT
  strategy_name TEXT
  order_id      TEXT                         PAPER-XXXXXX from PaperBroker
  opened_at     TEXT    NOT NULL
  closed_at     TEXT

paper_account
  id            INTEGER PRIMARY KEY CHECK (id = 1)
  cash          REAL    NOT NULL
  initial_capital REAL  NOT NULL
  updated_at    TEXT    NOT NULL

Usage
─────
    from trading.paper_trading_store import PaperTradingStore

    store = PaperTradingStore("paper_trading.db")
    store.initialise()

    # Save a position after a fill
    store.save_position(
        symbol        = "RELIANCE",
        side          = "LONG",
        quantity      = 100,
        entry_price   = 2962.10,
        stop_loss     = 2900.00,
        take_profit   = 3050.00,
        signal_price  = 2960.50,
        slippage_pct  = 0.000541,
        strategy_name = "CombinedPower",
    )

    # Restore state on startup
    state = store.load_state()
    for sym, pos in state["positions"].items():
        print(sym, pos["quantity"], pos["entry_price"])

    # Record a trade (entry)
    trade_id = store.save_trade(
        symbol         = "RELIANCE",
        side           = "BUY",
        quantity       = 100,
        signal_price   = 2960.50,
        executed_price = 2962.10,
        slippage_pct   = 0.000541,
        slippage_inr   = 160.0,
        order_id       = "PAPER-000001",
    )

    # Close the trade
    store.close_trade(trade_id, exit_price=3010.00, pnl=4790.0, reason="take_profit")
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# ─── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict using column names."""
    return {col[0]: row[col[0]] for col in cursor.description}


# ─── DDL ──────────────────────────────────────────────────────────────────────

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS paper_positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT    NOT NULL UNIQUE,
    side            TEXT    NOT NULL CHECK (side IN ('LONG','SHORT')),
    quantity        INTEGER NOT NULL DEFAULT 0,
    entry_price     REAL    NOT NULL,
    stop_loss       REAL,
    take_profit     REAL,
    strategy_name   TEXT,
    signal_price    REAL,
    slippage_pct    REAL,
    opened_at       TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT    NOT NULL,
    side            TEXT    NOT NULL CHECK (side IN ('BUY','SELL')),
    quantity        INTEGER NOT NULL,
    signal_price    REAL    NOT NULL,
    executed_price  REAL    NOT NULL,
    slippage_pct    REAL,
    slippage_inr    REAL,
    exit_price      REAL,
    pnl             REAL    DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open','closed')),
    exit_reason     TEXT,
    strategy_name   TEXT,
    order_id        TEXT,
    opened_at       TEXT    NOT NULL,
    closed_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol  ON paper_trades (symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trades_status  ON paper_trades (status);
CREATE INDEX IF NOT EXISTS idx_paper_trades_opened  ON paper_trades (opened_at);

CREATE TABLE IF NOT EXISTS paper_account (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    cash            REAL    NOT NULL,
    initial_capital REAL    NOT NULL,
    updated_at      TEXT    NOT NULL
);
"""


# ─── Store ─────────────────────────────────────────────────────────────────────

class PaperTradingStore:
    """
    SQLite persistence layer for paper trading positions and trades.

    Thread-safety: SQLite WAL mode is safe for multi-reader / single-writer
    access.  For concurrent writes, acquire an external lock before calls.

    Parameters
    ----------
    db_path : str
        Path to the SQLite file.  Relative paths are resolved from the
        current working directory.  Defaults to ``paper_trading.db`` in the
        same directory as this file.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "paper_trading.db",
            )
        self.db_path = db_path
        self._initialised = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def initialise(self, initial_capital: float = 100_000.0) -> None:
        """
        Create tables (idempotent) and seed the account row if missing.

        Safe to call on every startup — existing data is never overwritten.

        Parameters
        ----------
        initial_capital : float
            Starting virtual cash.  Only used when creating a *new* account
            row; existing balances are not changed.
        """
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        with self._connect() as conn:
            conn.executescript(_DDL)

            # Seed account row (id=1) only if it doesn't exist yet
            conn.execute(
                """
                INSERT OR IGNORE INTO paper_account (id, cash, initial_capital, updated_at)
                VALUES (1, ?, ?, ?)
                """,
                (initial_capital, initial_capital, _now_iso()),
            )
            conn.commit()

        self._initialised = True
        logger.info(
            f"PaperTradingStore initialised | db={self.db_path}"
        )

    def _ensure_initialised(self):
        if not self._initialised:
            self.initialise()

    # ── Connection context manager ─────────────────────────────────────────────

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a thread-local connection with row_factory set."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=10,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Positions ──────────────────────────────────────────────────────────────

    def save_position(
        self,
        symbol:        str,
        side:          str,
        quantity:      int,
        entry_price:   float,
        stop_loss:     Optional[float] = None,
        take_profit:   Optional[float] = None,
        signal_price:  Optional[float] = None,
        slippage_pct:  Optional[float] = None,
        strategy_name: Optional[str]   = None,
    ) -> int:
        """
        Upsert an open position.

        If a record for ``symbol`` already exists it is updated in place;
        otherwise a new row is inserted — preventing duplicates on restart.

        Parameters
        ----------
        symbol : str
            Instrument symbol (e.g. ``"RELIANCE"``).
        side : str
            ``"LONG"`` (BUY entry) or ``"SHORT"`` (SELL entry).
        quantity : int
            Current net open quantity.  Pass 0 to effectively close (but
            prefer ``close_position()`` for clarity).
        entry_price : float
            Average executed fill price (VWAP if accumulated).
        stop_loss, take_profit : float | None
            Risk level prices from the strategy signal.
        signal_price : float | None
            Original signal price before slippage.
        slippage_pct : float | None
            Slippage fraction actually applied on the fill.
        strategy_name : str | None
            Name of the generating strategy.

        Returns
        -------
        int
            Row ID of the upserted position.
        """
        self._ensure_initialised()
        side = side.upper()

        now = _now_iso()
        with self._connect() as conn:
            try:
                with conn:     # auto BEGIN / COMMIT / ROLLBACK
                    cursor = conn.execute(
                        """
                        INSERT INTO paper_positions
                            (symbol, side, quantity, entry_price,
                             stop_loss, take_profit, strategy_name,
                             signal_price, slippage_pct,
                             opened_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(symbol) DO UPDATE SET
                            side          = excluded.side,
                            quantity      = excluded.quantity,
                            entry_price   = excluded.entry_price,
                            stop_loss     = COALESCE(excluded.stop_loss,  paper_positions.stop_loss),
                            take_profit   = COALESCE(excluded.take_profit, paper_positions.take_profit),
                            strategy_name = COALESCE(excluded.strategy_name, paper_positions.strategy_name),
                            signal_price  = COALESCE(excluded.signal_price, paper_positions.signal_price),
                            slippage_pct  = COALESCE(excluded.slippage_pct, paper_positions.slippage_pct),
                            updated_at    = excluded.updated_at
                        """,
                        (symbol, side, quantity, entry_price,
                         stop_loss, take_profit, strategy_name,
                         signal_price, slippage_pct,
                         now, now),
                    )
                    row_id = cursor.lastrowid or conn.execute(
                        "SELECT id FROM paper_positions WHERE symbol = ?", (symbol,)
                    ).fetchone()["id"]

            except sqlite3.Error as exc:
                logger.error(f"save_position failed for {symbol}: {exc}")
                raise

        logger.debug(
            f"save_position | {symbol} {side} qty={quantity} "
            f"@ ₹{entry_price:.2f} | row_id={row_id}"
        )
        return row_id

    def close_position(self, symbol: str) -> bool:
        """
        Mark a position as closed (set quantity = 0).

        A closed position row remains in the DB for audit but is excluded
        from ``load_positions()`` since ``quantity = 0``.

        Returns True if a row was updated, False if symbol not found.
        """
        self._ensure_initialised()
        with self._connect() as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE paper_positions
                       SET quantity   = 0,
                           updated_at = ?
                     WHERE symbol = ? AND quantity > 0
                    """,
                    (_now_iso(), symbol),
                )
        closed = cursor.rowcount > 0
        if closed:
            logger.info(f"close_position | {symbol} → quantity set to 0")
        return closed

    def load_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all **open** positions (quantity > 0) from the database.

        Returns a dict keyed by symbol, suitable for direct assignment to
        ``PaperBroker.positions``.

        Returns
        -------
        dict
            ``{ "RELIANCE": { "symbol": ..., "quantity": ..., ... }, ... }``
        """
        self._ensure_initialised()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT symbol, side, quantity, entry_price,
                       stop_loss, take_profit, strategy_name,
                       signal_price, slippage_pct,
                       opened_at, updated_at
                  FROM paper_positions
                 WHERE quantity > 0
                 ORDER BY opened_at
                """
            ).fetchall()

        result: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            result[r["symbol"]] = {
                "symbol":        r["symbol"],
                "side":          r["side"],
                "quantity":      r["quantity"],
                "average_price": r["entry_price"],   # alias for PaperBroker
                "entry_price":   r["entry_price"],
                "stop_loss":     r["stop_loss"],
                "take_profit":   r["take_profit"],
                "strategy_name": r["strategy_name"],
                "signal_price":  r["signal_price"],
                "slippage_pct":  r["slippage_pct"],
                "realized_pnl":  0.0,               # loaded from trades later
                "opened_at":     r["opened_at"],
                "updated_at":    r["updated_at"],
            }

        logger.info(f"load_positions | {len(result)} open position(s) restored")
        return result

    # ── Trades ─────────────────────────────────────────────────────────────────

    def save_trade(
        self,
        symbol:         str,
        side:           str,
        quantity:       int,
        signal_price:   float,
        executed_price: float,
        slippage_pct:   float = 0.0,
        slippage_inr:   float = 0.0,
        strategy_name:  Optional[str] = None,
        order_id:       Optional[str] = None,
    ) -> int:
        """
        Insert a new trade record (status = 'open').

        Parameters
        ----------
        symbol : str
            Instrument symbol.
        side : str
            ``"BUY"`` or ``"SELL"``.
        quantity : int
            Filled quantity.
        signal_price : float
            Price at signal generation.
        executed_price : float
            Actual fill price after slippage.
        slippage_pct : float
            Slippage fraction (e.g. 0.000541).
        slippage_inr : float
            Rupee slippage cost.
        strategy_name : str | None
            Generating strategy.
        order_id : str | None
            Paper order reference (e.g. ``"PAPER-000001"``).

        Returns
        -------
        int
            Newly created trade row ID.
        """
        self._ensure_initialised()
        side = side.upper()

        with self._connect() as conn:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO paper_trades
                        (symbol, side, quantity, signal_price, executed_price,
                         slippage_pct, slippage_inr,
                         strategy_name, order_id, opened_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (symbol, side, quantity, signal_price, executed_price,
                     slippage_pct, slippage_inr,
                     strategy_name, order_id, _now_iso()),
                )
                trade_id = cursor.lastrowid

        logger.debug(
            f"save_trade | #{trade_id} {side} {quantity}×{symbol} "
            f"signal=₹{signal_price:.2f} exec=₹{executed_price:.2f}"
        )
        return trade_id

    def close_trade(
        self,
        trade_id:   int,
        exit_price: float,
        pnl:        float,
        reason:     Optional[str] = None,
    ) -> bool:
        """
        Close an open trade with its final P&L.

        Parameters
        ----------
        trade_id : int
            Row ID from ``save_trade()``.
        exit_price : float
            Executed exit price.
        pnl : float
            Realised profit / loss in ₹ (positive = profit).
        reason : str | None
            Exit reason (e.g. ``"stop_loss"``, ``"take_profit"``, ``"manual"``).

        Returns
        -------
        bool
            True if the row was updated, False if trade_id not found.
        """
        self._ensure_initialised()
        with self._connect() as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE paper_trades
                       SET exit_price  = ?,
                           pnl         = ?,
                           status      = 'closed',
                           exit_reason = ?,
                           closed_at   = ?
                     WHERE id = ? AND status = 'open'
                    """,
                    (exit_price, pnl, reason, _now_iso(), trade_id),
                )
        closed = cursor.rowcount > 0
        if closed:
            logger.info(
                f"close_trade | #{trade_id} exit=₹{exit_price:.2f} "
                f"pnl=₹{pnl:+,.2f} reason={reason}"
            )
        return closed

    def load_trades(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit:  int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Load trades with optional filters.

        Parameters
        ----------
        symbol : str | None
            Filter by instrument (``None`` = all symbols).
        status : str | None
            ``"open"``, ``"closed"``, or ``None`` for both.
        limit : int
            Maximum rows returned (most recent first).

        Returns
        -------
        list[dict]
            List of trade records as plain dicts.
        """
        self._ensure_initialised()
        params: list = []
        where_clauses: list = []

        if symbol:
            where_clauses.append("symbol = ?")
            params.append(symbol)
        if status:
            where_clauses.append("status = ?")
            params.append(status)

        where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, symbol, side, quantity,
                       signal_price, executed_price,
                       slippage_pct, slippage_inr,
                       exit_price, pnl, status, exit_reason,
                       strategy_name, order_id,
                       opened_at, closed_at
                  FROM paper_trades
                 {where}
                 ORDER BY opened_at DESC
                 LIMIT ?
                """,
                params,
            ).fetchall()

        result = []
        for r in rows:
            result.append({
                "id":             r["id"],
                "symbol":         r["symbol"],
                "side":           r["side"],
                "quantity":       r["quantity"],
                "signal_price":   r["signal_price"],
                "executed_price": r["executed_price"],
                "slippage_pct":   r["slippage_pct"],
                "slippage_inr":   r["slippage_inr"],
                "exit_price":     r["exit_price"],
                "pnl":            r["pnl"],
                "status":         r["status"],
                "exit_reason":    r["exit_reason"],
                "strategy_name":  r["strategy_name"],
                "order_id":       r["order_id"],
                "opened_at":      r["opened_at"],
                "closed_at":      r["closed_at"],
            })

        return result

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Return all open (unfilled exit) trades."""
        return self.load_trades(status="open")

    def get_realized_pnl(
        self,
        symbol: Optional[str] = None
    ) -> float:
        """Sum of realised P&L from all closed trades."""
        self._ensure_initialised()
        params = []
        sym_filter = ""
        if symbol:
            sym_filter = "AND symbol = ?"
            params.append(symbol)

        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COALESCE(SUM(pnl), 0) FROM paper_trades WHERE status='closed' {sym_filter}",
                params,
            ).fetchone()
        return float(row[0])

    # ── Account (virtual cash) ─────────────────────────────────────────────────

    def save_cash(self, cash: float) -> None:
        """Persist current virtual cash balance."""
        self._ensure_initialised()
        with self._connect() as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE paper_account SET cash = ?, updated_at = ? WHERE id = 1
                    """,
                    (cash, _now_iso()),
                )
        logger.debug(f"save_cash | ₹{cash:,.2f}")

    def load_cash(self) -> float:
        """Restore virtual cash balance from DB."""
        self._ensure_initialised()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cash FROM paper_account WHERE id = 1"
            ).fetchone()
        cash = float(row["cash"]) if row else 0.0
        logger.debug(f"load_cash | ₹{cash:,.2f}")
        return cash

    # ── Full state hydration ───────────────────────────────────────────────────

    def load_state(self) -> Dict[str, Any]:
        """
        Load the complete paper trading state in one call.

        Returns a dict that can be applied directly to ``PaperBroker``::

            state = store.load_state()
            broker.cash      = state["cash"]
            broker.positions = state["positions"]
            # open_trades     = state["open_trades"]   (for monitoring)

        Returns
        -------
        dict
            Keys:

            - ``cash``         — current virtual cash (float)
            - ``positions``    — {symbol: pos_dict}  (open only)
            - ``open_trades``  — list of open trade dicts
            - ``closed_trades``— list of recently closed trade dicts (last 200)
            - ``realized_pnl`` — total realised P&L from closed trades
        """
        self._ensure_initialised()

        cash          = self.load_cash()
        positions     = self.load_positions()
        open_trades   = self.load_trades(status="open")
        closed_trades = self.load_trades(status="closed", limit=200)
        realized_pnl  = self.get_realized_pnl()

        logger.info(
            f"load_state | "
            f"cash=₹{cash:,.2f} | "
            f"positions={len(positions)} | "
            f"open_trades={len(open_trades)} | "
            f"realized_pnl=₹{realized_pnl:+,.2f}"
        )

        return {
            "cash":          cash,
            "positions":     positions,
            "open_trades":   open_trades,
            "closed_trades": closed_trades,
            "realized_pnl":  realized_pnl,
        }

    # ── Admin helpers ──────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Return a quick status summary (useful for dashboards)."""
        self._ensure_initialised()
        with self._connect() as conn:
            n_open_pos   = conn.execute(
                "SELECT COUNT(*) FROM paper_positions WHERE quantity > 0"
            ).fetchone()[0]
            n_open_trades = conn.execute(
                "SELECT COUNT(*) FROM paper_trades WHERE status = 'open'"
            ).fetchone()[0]
            n_closed      = conn.execute(
                "SELECT COUNT(*) FROM paper_trades WHERE status = 'closed'"
            ).fetchone()[0]
            realized_pnl  = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) FROM paper_trades WHERE status='closed'"
            ).fetchone()[0]
            cash          = conn.execute(
                "SELECT cash FROM paper_account WHERE id = 1"
            ).fetchone()

        return {
            "db_path":         self.db_path,
            "open_positions":  n_open_pos,
            "open_trades":     n_open_trades,
            "closed_trades":   n_closed,
            "realized_pnl":    round(float(realized_pnl), 2),
            "cash":            round(float(cash["cash"]) if cash else 0, 2),
        }

    def reset(self, confirm: bool = False) -> None:
        """
        ⚠ Delete ALL paper trading data (positions, trades, account).

        Only executes if ``confirm=True`` is explicitly passed.
        """
        if not confirm:
            raise ValueError("Pass confirm=True to wipe all paper trading data")
        with self._connect() as conn:
            with conn:
                conn.executescript("""
                    DELETE FROM paper_trades;
                    DELETE FROM paper_positions;
                    DELETE FROM paper_account;
                """)
        self._initialised = False
        logger.warning("PaperTradingStore RESET — all data deleted")


# ─── Singleton accessor ────────────────────────────────────────────────────────

_store_instance: Optional[PaperTradingStore] = None


def get_paper_store(
    db_path:         Optional[str] = None,
    initial_capital: float         = 100_000.0,
) -> PaperTradingStore:
    """
    Return the global ``PaperTradingStore`` singleton, initialising it on
    first call.

    Parameters
    ----------
    db_path : str | None
        SQLite file path.  Defaults to ``paper_trading.db`` in the
        same directory as this module.
    initial_capital : float
        Starting cash for a brand-new account.

    Returns
    -------
    PaperTradingStore
    """
    global _store_instance
    if _store_instance is None:
        _store_instance = PaperTradingStore(db_path)
        _store_instance.initialise(initial_capital=initial_capital)
    return _store_instance


# ─── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile
    import shutil

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Use a temp directory so the test is reproducible and leaves no artefacts
    tmp_dir = tempfile.mkdtemp(prefix="paper_store_test_")
    db_file = os.path.join(tmp_dir, "test_paper.db")

    W = 72
    print("\n" + "=" * W)
    print("  PaperTradingStore — Integration Test")
    print("=" * W)

    try:
        # ── 1. Initialise ──────────────────────────────────────────────────────
        store = PaperTradingStore(db_file)
        store.initialise(initial_capital=500_000)
        print("  [1] Initialise                              ✓")

        # ── 2. Save positions ──────────────────────────────────────────────────
        store.save_position("RELIANCE", "LONG",  100, 2962.10,
                            stop_loss=2900.00, take_profit=3050.00,
                            signal_price=2960.50, slippage_pct=0.000541,
                            strategy_name="CombinedPower")
        store.save_position("TCS",      "LONG",   10, 4108.20,
                            stop_loss=4000.00, take_profit=4300.00,
                            signal_price=4105.00, slippage_pct=0.000780)
        print("  [2] save_position (2 entries)               ✓")

        # ── 3. Upsert — no duplicate ──────────────────────────────────────────
        store.save_position("RELIANCE", "LONG", 150, 2970.00)  # update qty
        pos = store.load_positions()
        assert pos["RELIANCE"]["quantity"] == 150, "Upsert quantity mismatch"
        print("  [3] Upsert prevents duplicate               ✓")

        # ── 4. Save trades ─────────────────────────────────────────────────────
        t1 = store.save_trade("RELIANCE", "BUY",  100, 2960.50, 2962.10,
                              slippage_pct=0.000541, slippage_inr=160.0,
                              order_id="PAPER-000001")
        t2 = store.save_trade("TCS",      "BUY",   10, 4105.00, 4108.20,
                              slippage_pct=0.000780, slippage_inr=32.0,
                              order_id="PAPER-000002")
        print("  [4] save_trade (entry leg)                  ✓")

        # ── 5. Close one trade ─────────────────────────────────────────────────
        store.close_trade(t1, exit_price=3010.00, pnl=4790.0, reason="take_profit")
        print("  [5] close_trade                             ✓")

        # ── 6. Update cash ─────────────────────────────────────────────────────
        store.save_cash(495_000.0)
        print("  [6] save_cash                               ✓")

        # ── 7. Simulate restart — load full state ──────────────────────────────
        store2 = PaperTradingStore(db_file)   # new instance, same DB
        store2.initialise(initial_capital=999_999)  # initial_capital ignored (row exists)

        state = store2.load_state()

        assert abs(state["cash"] - 495_000.0) < 0.01, "Cash not restored"
        assert "TCS" in state["positions"],            "TCS position missing after restart"
        assert "RELIANCE" in state["positions"],       "RELIANCE position missing (qty still 150)"
        assert len(state["open_trades"]) == 1,         "Expected 1 open trade (TCS)"
        assert len(state["closed_trades"]) == 1,       "Expected 1 closed trade (RELIANCE)"
        assert abs(state["realized_pnl"] - 4790.0) < 0.01, "Realized PnL mismatch"
        print("  [7] load_state after restart                ✓")

        # ── 8. Close position (zero out) ───────────────────────────────────────
        store2.close_position("TCS")
        pos2 = store2.load_positions()
        assert "TCS" not in pos2, "TCS should be absent (qty=0)"
        print("  [8] close_position → excluded from load     ✓")

        # ── 9. Summary ─────────────────────────────────────────────────────────
        summary = store2.get_summary()
        print(f"\n  Summary: {summary}")
        print("  [9] get_summary                             ✓")

        print("\n" + "=" * W)
        print("  All assertions passed ✓")
        print("=" * W + "\n")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
