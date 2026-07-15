from __future__ import annotations

from datetime import datetime, timezone
from datetime import timedelta
import json
import sqlite3

import pandas as pd


class Journal:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    price REAL NOT NULL,
                    reason TEXT NOT NULL,
                    approved INTEGER NOT NULL,
                    risk_reason TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    notional_usd REAL NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_theses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    setup TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    approved INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    validation_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    setup TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS setup_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    setup TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    score REAL NOT NULL,
                    confidence REAL NOT NULL,
                    approved INTEGER NOT NULL,
                    volume_24h_usd REAL,
                    oi_change_24h_pct REAL,
                    relative_volume REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    exchange_id TEXT NOT NULL,
                    route_symbol TEXT NOT NULL,
                    setup TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    horizon_hours INTEGER NOT NULL,
                    entry REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    target REAL NOT NULL,
                    score REAL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    return_pct REAL,
                    exit_reason TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS active_setups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    setup TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    status TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    entry REAL,
                    stop_loss REAL,
                    target REAL,
                    score REAL,
                    confidence REAL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS candle_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    source TEXT NOT NULL,
                    candle_count INTEGER NOT NULL,
                    first_timestamp TEXT,
                    last_timestamp TEXT
                )
                """
            )

    def record_decision(
        self,
        symbol: str,
        action: str,
        confidence: float,
        price: float,
        reason: str,
        approved: bool,
        risk_reason: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO decisions (
                    created_at, symbol, action, confidence, price, reason, approved, risk_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    action,
                    confidence,
                    price,
                    reason,
                    int(approved),
                    risk_reason,
                ),
            )

    def record_fill(
        self,
        action: str,
        quantity: float,
        price: float,
        notional_usd: float,
        message: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO fills (
                    created_at, action, quantity, price, notional_usd, message
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    action,
                    quantity,
                    price,
                    notional_usd,
                    message,
                ),
            )

    def record_thesis(
        self,
        symbol: str,
        setup: str,
        signal: str,
        direction: str,
        confidence: float,
        approved: bool,
        payload_json: str,
        validation_json: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_theses (
                    created_at, symbol, setup, signal, direction, confidence,
                    approved, payload_json, validation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    setup,
                    signal,
                    direction,
                    confidence,
                    int(approved),
                    payload_json,
                    validation_json,
                ),
            )

    def recent_theses(self, limit: int = 25) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT created_at, symbol, setup, signal, direction, confidence,
                       approved, payload_json, validation_json
                FROM ai_theses
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        results = []
        for row in rows:
            results.append(
                {
                    "created_at": row[0],
                    "symbol": row[1],
                    "setup": row[2],
                    "signal": row[3],
                    "direction": row[4],
                    "confidence": row[5],
                    "approved": bool(row[6]),
                    "payload": json.loads(row[7]),
                    "validation": json.loads(row[8]),
                }
            )
        return results

    def alert_sent_recently(
        self,
        symbol: str,
        setup: str,
        signal: str,
        cooldown_minutes: int,
    ) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT created_at
                FROM telegram_alerts
                WHERE symbol = ? AND setup = ? AND signal = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (symbol, setup, signal),
            ).fetchone()
        if row is None:
            return False
        created_at = datetime.fromisoformat(row[0])
        elapsed = datetime.now(timezone.utc) - created_at
        return elapsed.total_seconds() < cooldown_minutes * 60

    def record_alert(self, symbol: str, setup: str, signal: str, message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telegram_alerts (created_at, symbol, setup, signal, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    setup,
                    signal,
                    message,
                ),
            )

    def record_signal_outcome_seed(
        self,
        symbol: str,
        exchange_id: str,
        route_symbol: str,
        setup: str,
        signal: str,
        direction: str,
        grade: str,
        entry: float,
        stop_loss: float,
        target: float,
        score: float | None,
        confidence: float,
        horizon_hours: int,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            duplicate = conn.execute(
                """
                SELECT id
                FROM signal_outcomes
                WHERE symbol = ? AND setup = ? AND signal = ? AND direction = ?
                  AND horizon_hours = ? AND status = 'pending'
                ORDER BY id DESC
                LIMIT 1
                """,
                (symbol, setup, signal, direction, horizon_hours),
            ).fetchone()
            if duplicate is not None:
                return
            conn.execute(
                """
                INSERT INTO signal_outcomes (
                    created_at, updated_at, symbol, exchange_id, route_symbol, setup,
                    signal, direction, grade, horizon_hours, entry, stop_loss, target,
                    score, confidence, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    now,
                    symbol,
                    exchange_id,
                    route_symbol,
                    setup,
                    signal,
                    direction,
                    grade,
                    horizon_hours,
                    entry,
                    stop_loss,
                    target,
                    score,
                    confidence,
                    "pending",
                ),
            )

    def record_active_setup(
        self,
        symbol: str,
        setup: str,
        direction: str,
        status: str,
        grade: str,
        entry: float | None,
        stop_loss: float | None,
        target: float | None,
        score: float | None,
        confidence: float,
        ttl_minutes: int = 180,
    ) -> None:
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        expires_at = (now_dt.replace(microsecond=0) + _minutes(ttl_minutes)).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM active_setups
                WHERE symbol = ? AND setup = ? AND direction = ?
                  AND status IN ('watch', 'confirmed')
                ORDER BY id DESC
                LIMIT 1
                """,
                (symbol, setup, direction),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO active_setups (
                        created_at, updated_at, symbol, setup, direction, status,
                        grade, entry, stop_loss, target, score, confidence, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now,
                        now,
                        symbol,
                        setup,
                        direction,
                        status,
                        grade,
                        entry,
                        stop_loss,
                        target,
                        score,
                        confidence,
                        expires_at,
                    ),
                )
                return
            conn.execute(
                """
                UPDATE active_setups
                SET updated_at = ?, status = ?, grade = ?, entry = ?,
                    stop_loss = ?, target = ?, score = ?, confidence = ?,
                    expires_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    status,
                    grade,
                    entry,
                    stop_loss,
                    target,
                    score,
                    confidence,
                    expires_at,
                    row[0],
                ),
            )

    def active_watch_exists(
        self,
        symbol: str,
        setup: str,
        direction: str,
        within_minutes: int = 240,
    ) -> bool:
        cutoff = (datetime.now(timezone.utc) - _minutes(within_minutes)).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM active_setups
                WHERE symbol = ? AND setup = ? AND direction = ?
                  AND status IN ('watch', 'confirmed')
                  AND updated_at >= ?
                  AND expires_at >= ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    symbol,
                    setup,
                    direction,
                    cutoff,
                    datetime.now(timezone.utc).isoformat(),
                ),
            ).fetchone()
        return row is not None

    def expire_active_setups(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE active_setups
                SET status = 'expired', updated_at = ?
                WHERE status IN ('watch', 'confirmed') AND expires_at < ?
                """,
                (now, now),
            )
            return cursor.rowcount

    def invalidate_active_setup(
        self,
        symbol: str,
        setup: str,
        direction: str,
        reason: str,
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM active_setups
                WHERE symbol = ? AND setup = ? AND direction = ?
                  AND status IN ('watch', 'confirmed')
                ORDER BY id DESC
                LIMIT 1
                """,
                (symbol, setup, direction),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                """
                UPDATE active_setups
                SET status = 'invalidated', updated_at = ?, grade = ?
                WHERE id = ?
                """,
                (now, reason[:24] or "invalidated", row[0]),
            )
            return True

    def recent_active_setups(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT created_at, updated_at, symbol, setup, direction, status,
                       grade, entry, stop_loss, target, score, confidence, expires_at
                FROM active_setups
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "created_at": row[0],
                "updated_at": row[1],
                "symbol": row[2],
                "setup": row[3],
                "direction": row[4],
                "status": row[5],
                "grade": row[6],
                "entry": row[7],
                "stop_loss": row[8],
                "target": row[9],
                "score": row[10],
                "confidence": row[11],
                "expires_at": row[12],
            }
            for row in rows
        ]

    def pending_signal_outcomes(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, symbol, exchange_id, route_symbol, setup,
                       signal, direction, grade, horizon_hours, entry, stop_loss,
                       target, score, confidence
                FROM signal_outcomes
                WHERE status = 'pending'
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "created_at": row[1],
                "symbol": row[2],
                "exchange_id": row[3],
                "route_symbol": row[4],
                "setup": row[5],
                "signal": row[6],
                "direction": row[7],
                "grade": row[8],
                "horizon_hours": row[9],
                "entry": row[10],
                "stop_loss": row[11],
                "target": row[12],
                "score": row[13],
                "confidence": row[14],
            }
            for row in rows
        ]

    def update_signal_outcome(
        self,
        outcome_id: int,
        status: str,
        return_pct: float,
        exit_reason: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE signal_outcomes
                SET updated_at = ?, status = ?, return_pct = ?, exit_reason = ?
                WHERE id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    status,
                    return_pct,
                    exit_reason,
                    outcome_id,
                ),
            )

    def recent_signal_outcomes(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT created_at, updated_at, symbol, setup, signal, direction,
                       grade, horizon_hours, entry, stop_loss, target, score,
                       confidence, status, return_pct, exit_reason
                FROM signal_outcomes
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "created_at": row[0],
                "updated_at": row[1],
                "symbol": row[2],
                "setup": row[3],
                "signal": row[4],
                "direction": row[5],
                "grade": row[6],
                "horizon_hours": row[7],
                "entry": row[8],
                "stop_loss": row[9],
                "target": row[10],
                "score": row[11],
                "confidence": row[12],
                "status": row[13],
                "return_pct": row[14],
                "exit_reason": row[15],
            }
            for row in rows
        ]

    def outcome_summary(self, limit: int = 500) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT setup, signal, direction, grade, horizon_hours, COUNT(*),
                       SUM(CASE WHEN return_pct > 0 THEN 1 ELSE 0 END),
                       AVG(return_pct)
                FROM (
                    SELECT setup, signal, direction, grade, horizon_hours, return_pct
                    FROM signal_outcomes
                    WHERE status != 'pending' AND return_pct IS NOT NULL
                    ORDER BY id DESC
                    LIMIT ?
                )
                GROUP BY setup, signal, direction, grade, horizon_hours
                ORDER BY AVG(return_pct) DESC
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "setup": row[0],
                "signal": row[1],
                "direction": row[2],
                "grade": row[3],
                "horizon_hours": row[4],
                "count": row[5],
                "wins": row[6],
                "win_rate": (row[6] / row[5]) if row[5] else 0.0,
                "avg_return_pct": row[7],
            }
            for row in rows
        ]

    def record_setup_score(
        self,
        symbol: str,
        setup: str,
        signal: str,
        rank: int,
        score: float,
        confidence: float,
        approved: bool,
        volume_24h_usd: float | None,
        oi_change_24h_pct: float | None,
        relative_volume: float | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO setup_scores (
                    created_at, symbol, setup, signal, rank, score, confidence,
                    approved, volume_24h_usd, oi_change_24h_pct, relative_volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    setup,
                    signal,
                    rank,
                    score,
                    confidence,
                    int(approved),
                    volume_24h_usd,
                    oi_change_24h_pct,
                    relative_volume,
                ),
            )

    def recent_alerts(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT created_at, symbol, setup, signal, message
                FROM telegram_alerts
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "created_at": row[0],
                "symbol": row[1],
                "setup": row[2],
                "signal": row[3],
                "message": row[4],
            }
            for row in rows
        ]

    def setup_calibration(self, limit: int = 500) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT setup, signal, COUNT(*), AVG(score), AVG(confidence),
                       SUM(approved), AVG(relative_volume), AVG(oi_change_24h_pct)
                FROM (
                    SELECT setup, signal, score, confidence, approved,
                           relative_volume, oi_change_24h_pct
                    FROM setup_scores
                    ORDER BY id DESC
                    LIMIT ?
                )
                GROUP BY setup, signal
                ORDER BY AVG(score) DESC
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "setup": row[0],
                "signal": row[1],
                "count": row[2],
                "avg_score": row[3],
                "avg_confidence": row[4],
                "approved_count": row[5],
                "avg_relative_volume": row[6],
                "avg_oi_change_24h_pct": row[7],
            }
            for row in rows
        ]

    def record_candle_sample(
        self,
        symbol: str,
        timeframe: str,
        candles: pd.DataFrame,
        source: str,
    ) -> None:
        first_timestamp = None
        last_timestamp = None
        if not candles.empty and "timestamp" in candles:
            first_timestamp = str(candles.iloc[0]["timestamp"])
            last_timestamp = str(candles.iloc[-1]["timestamp"])
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO candle_samples (
                    created_at, symbol, timeframe, source, candle_count,
                    first_timestamp, last_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    timeframe,
                    source,
                    len(candles),
                    first_timestamp,
                    last_timestamp,
                ),
            )

    def recent_candle_samples(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT created_at, symbol, timeframe, source, candle_count,
                       first_timestamp, last_timestamp
                FROM candle_samples
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "created_at": row[0],
                "symbol": row[1],
                "timeframe": row[2],
                "source": row[3],
                "candle_count": row[4],
                "first_timestamp": row[5],
                "last_timestamp": row[6],
            }
            for row in rows
        ]


def _minutes(value: int) -> timedelta:
    return timedelta(minutes=value)
