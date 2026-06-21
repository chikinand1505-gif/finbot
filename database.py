import os
import asyncpg
from datetime import datetime
from typing import Optional, List, Dict


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def init(self):
        self.pool = await asyncpg.create_pool(
            dsn=os.getenv("DATABASE_URL"),
            min_size=2,
            max_size=10,
            ssl="require"
        )
        await self._create_tables()

    async def _create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    name TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                    type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                    category TEXT NOT NULL,
                    amount NUMERIC(12, 2) NOT NULL,
                    currency TEXT DEFAULT 'RUB',
                    description TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS goals (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    target_amount NUMERIC(12, 2) NOT NULL,
                    current_amount NUMERIC(12, 2) DEFAULT 0,
                    deadline DATE,
                    is_completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS assets (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                    asset_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    amount NUMERIC(16, 2) NOT NULL,
                    currency TEXT DEFAULT 'RUB',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
                CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
                CREATE INDEX IF NOT EXISTS idx_assets_user_id ON assets(user_id);

                CREATE TABLE IF NOT EXISTS crypto_assets (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                    coin_id TEXT NOT NULL,
                    coin_symbol TEXT NOT NULL,
                    coin_name TEXT NOT NULL,
                    amount NUMERIC(20, 8) NOT NULL,
                    is_stablecoin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_crypto_assets_user_id ON crypto_assets(user_id);
            """)
            # Migration: add currency column to transactions if not exists
            await conn.execute("""
                ALTER TABLE transactions ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'RUB';
            """)
            # Migration: add is_stablecoin if column doesn't exist yet
            await conn.execute("""
                ALTER TABLE crypto_assets ADD COLUMN IF NOT EXISTS is_stablecoin BOOLEAN DEFAULT FALSE;
            """)

    async def create_user(self, user_id: int, name: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (id, name) VALUES ($1, $2)
                ON CONFLICT (id) DO UPDATE SET name = $2
            """, user_id, name)

    async def get_all_users(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users")
            return [dict(r) for r in rows]

    async def add_transaction(self, user_id: int, t_type: str, category: str,
                               amount: float, description: str = None, currency: str = "RUB") -> Dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO transactions (user_id, type, category, amount, description, currency)
                VALUES ($1, $2, $3, $4, $5, $6) RETURNING *
            """, user_id, t_type, category, amount, description, currency)
            return dict(row)

    async def delete_transaction(self, tx_id: int, user_id: int) -> bool:
        """Delete transaction only if it belongs to the user."""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM transactions WHERE id = $1 AND user_id = $2
            """, tx_id, user_id)
            return result == "DELETE 1"

    async def get_recent_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM transactions WHERE user_id = $1
                ORDER BY created_at DESC LIMIT $2
            """, user_id, limit)
            return [dict(r) for r in rows]

    async def get_monthly_stats(self, user_id: int, usdt_rate: float = 77.0) -> Dict:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT type, currency, SUM(amount) as total FROM transactions
                WHERE user_id = $1
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
                GROUP BY type, currency
            """, user_id)
            result = {"income": 0, "expense": 0, "income_usdt": 0, "expense_usdt": 0}
            for row in rows:
                amt = float(row["total"])
                cur = row["currency"] or "RUB"
                amt_rub = amt if cur == "RUB" else amt * usdt_rate
                amt_usdt = amt if cur == "USDT" else amt / usdt_rate
                if row["type"] == "income":
                    result["income"] += amt_rub
                    result["income_usdt"] += amt_usdt
                else:
                    result["expense"] += amt_rub
                    result["expense_usdt"] += amt_usdt
            return result

    async def get_last_30_days_stats(self, user_id: int, usdt_rate: float = 77.0) -> Dict:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT type, currency, SUM(amount) as total FROM transactions
                WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '30 days'
                GROUP BY type, currency
            """, user_id)
            result = {"income": 0, "expense": 0, "income_usdt": 0, "expense_usdt": 0, "categories": {}}
            for row in rows:
                amt = float(row["total"])
                cur = row["currency"] or "RUB"
                amt_rub = amt if cur == "RUB" else amt * usdt_rate
                amt_usdt = amt if cur == "USDT" else amt / usdt_rate
                if row["type"] == "income":
                    result["income"] += amt_rub
                    result["income_usdt"] += amt_usdt
                else:
                    result["expense"] += amt_rub
                    result["expense_usdt"] += amt_usdt
            cat_rows = await conn.fetch("""
                SELECT category, currency, SUM(amount) as total FROM transactions
                WHERE user_id = $1 AND type = 'expense'
                  AND created_at >= NOW() - INTERVAL '30 days'
                GROUP BY category, currency ORDER BY total DESC
            """, user_id)
            for row in cat_rows:
                amt = float(row["total"])
                cur = row["currency"] or "RUB"
                amt_rub = amt if cur == "RUB" else amt * usdt_rate
                cat = row["category"]
                result["categories"][cat] = result["categories"].get(cat, 0) + amt_rub
            return result

    async def get_total_balance(self, user_id: int) -> float:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END), 0) as balance
                FROM transactions WHERE user_id = $1
            """, user_id)
            return float(row["balance"])

    async def get_category_total(self, user_id: int, category: str, period: str) -> float:
        async with self.pool.acquire() as conn:
            period_filter = _build_period_filter(period)
            row = await conn.fetchrow(f"""
                SELECT COALESCE(SUM(amount), 0) as total FROM transactions
                WHERE user_id = $1 AND category = $2 {period_filter}
            """, user_id, category)
            return float(row["total"])

    async def get_expenses_by_period(self, user_id: int, period: str) -> List[Dict]:
        async with self.pool.acquire() as conn:
            period_filter = _build_period_filter(period)
            rows = await conn.fetch(f"""
                SELECT category, SUM(amount) as total FROM transactions
                WHERE user_id = $1 AND type = 'expense' {period_filter}
                GROUP BY category ORDER BY total DESC
            """, user_id)
            return [{"category": r["category"], "total": float(r["total"])} for r in rows]

    async def get_income_by_period(self, user_id: int, period: str) -> List[Dict]:
        async with self.pool.acquire() as conn:
            period_filter = _build_period_filter(period)
            rows = await conn.fetch(f"""
                SELECT category, SUM(amount) as total FROM transactions
                WHERE user_id = $1 AND type = 'income' {period_filter}
                GROUP BY category ORDER BY total DESC
            """, user_id)
            return [{"category": r["category"], "total": float(r["total"])} for r in rows]

    async def get_category_breakdown(self, user_id: int, t_type: str) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT category, SUM(amount) as total FROM transactions
                WHERE user_id = $1 AND type = $2
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
                GROUP BY category ORDER BY total DESC
            """, user_id, t_type)
            return [{"category": r["category"], "total": float(r["total"])} for r in rows]

    async def get_monthly_history(self, user_id: int) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    TO_CHAR(DATE_TRUNC('month', created_at), 'MM.YYYY') as month,
                    DATE_TRUNC('month', created_at) as month_date,
                    SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
                FROM transactions
                WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '6 months'
                GROUP BY DATE_TRUNC('month', created_at) ORDER BY month_date ASC
            """, user_id)
            return [{"month": r["month"], "income": float(r["income"]), "expense": float(r["expense"])} for r in rows]

    async def add_goal(self, user_id: int, name: str, target_amount: float,
                       current_amount: float = 0, deadline=None) -> Dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO goals (user_id, name, target_amount, current_amount, deadline)
                VALUES ($1, $2, $3, $4, $5) RETURNING *
            """, user_id, name, target_amount, current_amount, deadline)
            return dict(row)

    async def get_goals(self, user_id: int) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM goals WHERE user_id = $1 AND is_completed = FALSE
                ORDER BY created_at DESC
            """, user_id)
            return [dict(r) for r in rows]

    async def update_goal_progress(self, goal_id: int, amount: float) -> Dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE goals
                SET current_amount = current_amount + $2,
                    is_completed = (current_amount + $2 >= target_amount)
                WHERE id = $1 RETURNING *
            """, goal_id, amount)
            return dict(row)

    async def add_asset(self, user_id: int, asset_type: str, name: str,
                        amount: float, currency: str = "RUB") -> Dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO assets (user_id, asset_type, name, amount, currency)
                VALUES ($1, $2, $3, $4, $5) RETURNING *
            """, user_id, asset_type, name, amount, currency)
            return dict(row)

    async def get_assets(self, user_id: int) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM assets WHERE user_id = $1
                ORDER BY asset_type, created_at DESC
            """, user_id)
            return [dict(r) for r in rows]

    async def update_asset(self, asset_id: int, amount: float) -> Dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE assets SET amount = $2, updated_at = NOW()
                WHERE id = $1 RETURNING *
            """, asset_id, amount)
            return dict(row)

    async def add_crypto_asset(self, user_id: int, coin_id: str, coin_symbol: str,
                                coin_name: str, amount: float, is_stablecoin: bool = False) -> Dict:
        async with self.pool.acquire() as conn:
            existing = await conn.fetchrow("""
                SELECT id, amount FROM crypto_assets
                WHERE user_id = $1 AND coin_id = $2
            """, user_id, coin_id)
            if existing:
                row = await conn.fetchrow("""
                    UPDATE crypto_assets SET amount = amount + $2, updated_at = NOW()
                    WHERE id = $1 RETURNING *
                """, existing["id"], amount)
            else:
                row = await conn.fetchrow("""
                    INSERT INTO crypto_assets (user_id, coin_id, coin_symbol, coin_name, amount, is_stablecoin)
                    VALUES ($1, $2, $3, $4, $5, $6) RETURNING *
                """, user_id, coin_id, coin_symbol, coin_name, amount, is_stablecoin)
            return dict(row)

    async def get_crypto_assets(self, user_id: int) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM crypto_assets WHERE user_id = $1
                ORDER BY created_at DESC
            """, user_id)
            return [dict(r) for r in rows]

    async def update_crypto_asset(self, crypto_id: int, amount: float) -> Dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE crypto_assets SET amount = $2, updated_at = NOW()
                WHERE id = $1 RETURNING *
            """, crypto_id, amount)
            return dict(row)

    async def delete_crypto_asset(self, crypto_id: int, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM crypto_assets WHERE id = $1 AND user_id = $2
            """, crypto_id, user_id)
            return result == "DELETE 1"

    async def delete_asset(self, asset_id: int, user_id: int = None) -> bool:
        async with self.pool.acquire() as conn:
            if user_id:
                result = await conn.execute(
                    "DELETE FROM assets WHERE id = $1 AND user_id = $2", asset_id, user_id
                )
            else:
                result = await conn.execute("DELETE FROM assets WHERE id = $1", asset_id)
            return result == "DELETE 1"


def _build_period_filter(period: str) -> str:
    month_map = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12
    }
    if period == "month":
        return "AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())"
    elif period == "year":
        return "AND DATE_TRUNC('year', created_at) = DATE_TRUNC('year', NOW())"
    elif period == "week":
        return "AND created_at >= NOW() - INTERVAL '7 days'"
    elif period in month_map:
        m = month_map[period]
        return f"AND EXTRACT(MONTH FROM created_at) = {m} AND EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM NOW())"
    else:
        return ""


db = Database()
