"""
PostgreSQL database client using psycopg2.
Provides a connection pool and helper methods that mirror
the Supabase client API for easy migration.
"""

import psycopg2
import psycopg2.pool
import psycopg2.extras
import json
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from shared_config import settings

logger = logging.getLogger(__name__)

# Connection pool
_pool = None


def get_pool():
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=settings.DATABASE_URL,
        )
        logger.info("PostgreSQL connection pool created")
    return _pool


def get_conn():
    """Get a connection from the pool."""
    return get_pool().getconn()


def put_conn(conn):
    """Return a connection to the pool."""
    get_pool().putconn(conn)


class DBResult:
    """Wraps query results to provide a consistent interface."""
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count or len(self.data)


class QueryBuilder:
    """
    A fluent query builder that provides a Supabase-like interface
    on top of raw psycopg2. This minimizes changes to existing code.
    """

    def __init__(self, table_name: str):
        self._table = table_name
        self._select_cols = "*"
        self._filters = []
        self._filter_values = []
        self._order_col = None
        self._order_desc = False
        self._limit_val = None
        self._offset_val = None
        self._range_start = None
        self._range_end = None
        self._count_mode = False
        self._operation = None  # select, insert, update, delete, upsert
        self._data = None

    def select(self, columns: str = "*", count: str = None) -> "QueryBuilder":
        self._operation = "select"
        self._select_cols = columns
        if count == "exact":
            self._count_mode = True
        return self

    def insert(self, data: dict) -> "QueryBuilder":
        self._operation = "insert"
        self._data = data
        return self

    def update(self, data: dict) -> "QueryBuilder":
        self._operation = "update"
        self._data = data
        return self

    def upsert(self, data: dict) -> "QueryBuilder":
        self._operation = "upsert"
        self._data = data
        return self

    def delete(self) -> "QueryBuilder":
        self._operation = "delete"
        return self

    def eq(self, column: str, value) -> "QueryBuilder":
        self._filters.append(f"{column} = %s")
        self._filter_values.append(value)
        return self

    def order(self, column: str, desc: bool = False) -> "QueryBuilder":
        self._order_col = column
        self._order_desc = desc
        return self

    def limit(self, n: int) -> "QueryBuilder":
        self._limit_val = n
        return self

    def range(self, start: int, end: int) -> "QueryBuilder":
        self._offset_val = start
        self._limit_val = end - start + 1
        return self

    def execute(self) -> DBResult:
        """Execute the built query and return results."""
        conn = get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if self._operation == "select":
                    return self._exec_select(cur, conn)
                elif self._operation == "insert":
                    return self._exec_insert(cur, conn)
                elif self._operation == "update":
                    return self._exec_update(cur, conn)
                elif self._operation == "upsert":
                    return self._exec_upsert(cur, conn)
                elif self._operation == "delete":
                    return self._exec_delete(cur, conn)
                else:
                    raise ValueError(f"No operation set. Call select/insert/update/delete first.")
        except Exception as e:
            conn.rollback()
            logger.error(f"DB error on {self._table}: {e}")
            raise
        finally:
            put_conn(conn)

    def _where_clause(self):
        if self._filters:
            return " WHERE " + " AND ".join(self._filters)
        return ""

    def _exec_select(self, cur, conn):
        sql = f"SELECT {self._select_cols} FROM {self._table}"
        sql += self._where_clause()
        values = list(self._filter_values)

        if self._order_col:
            direction = "DESC" if self._order_desc else "ASC"
            sql += f" ORDER BY {self._order_col} {direction}"
        if self._limit_val:
            sql += f" LIMIT {self._limit_val}"
        if self._offset_val:
            sql += f" OFFSET {self._offset_val}"

        cur.execute(sql, values)
        rows = cur.fetchall()
        data = [dict(row) for row in rows]

        # Convert non-serializable types
        for row in data:
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()

        count = None
        if self._count_mode:
            count_sql = f"SELECT COUNT(*) FROM {self._table}" + self._where_clause()
            cur.execute(count_sql, list(self._filter_values))
            count = cur.fetchone()["count"]

        return DBResult(data=data, count=count)

    def _exec_insert(self, cur, conn):
        # Serialize dict/list values as JSON
        data = self._serialize_json_fields(self._data)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        values = list(data.values())

        sql = f"INSERT INTO {self._table} ({columns}) VALUES ({placeholders}) RETURNING *"
        cur.execute(sql, values)
        conn.commit()
        row = cur.fetchone()
        result = dict(row) if row else {}
        for k, v in result.items():
            if hasattr(v, 'isoformat'):
                result[k] = v.isoformat()
        return DBResult(data=[result])

    def _exec_update(self, cur, conn):
        data = self._serialize_json_fields(self._data)
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        values = list(data.values()) + list(self._filter_values)

        sql = f"UPDATE {self._table} SET {set_clause}{self._where_clause()} RETURNING *"
        cur.execute(sql, values)
        conn.commit()
        rows = cur.fetchall()
        result = [dict(row) for row in rows]
        for row in result:
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()
        return DBResult(data=result)

    def _exec_upsert(self, cur, conn):
        data = self._serialize_json_fields(self._data)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        values = list(data.values())

        # Determine primary key for ON CONFLICT
        pk_map = {
            "sessions": "session_id",
            "users": "(user_id, company_id)",
        }
        pk = pk_map.get(self._table, "id")

        update_cols = [f"{k} = EXCLUDED.{k}" for k in data.keys()]
        update_clause = ", ".join(update_cols)

        sql = (
            f"INSERT INTO {self._table} ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT ({pk}) DO UPDATE SET {update_clause} RETURNING *"
        )
        cur.execute(sql, values)
        conn.commit()
        row = cur.fetchone()
        result = dict(row) if row else {}
        for k, v in result.items():
            if hasattr(v, 'isoformat'):
                result[k] = v.isoformat()
        return DBResult(data=[result])

    def _exec_delete(self, cur, conn):
        sql = f"DELETE FROM {self._table}{self._where_clause()} RETURNING *"
        cur.execute(sql, list(self._filter_values))
        conn.commit()
        rows = cur.fetchall()
        return DBResult(data=[dict(r) for r in rows])

    def _serialize_json_fields(self, data: dict) -> dict:
        """Convert dict/list values to psycopg2 Json wrappers."""
        result = {}
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                result[k] = psycopg2.extras.Json(v)
            else:
                result[k] = v
        return result


class Database:
    """
    Drop-in replacement for the Supabase client.
    Usage:  db.table("events").select("*").eq("user_id", "123").execute()
    """

    def table(self, name: str) -> QueryBuilder:
        return QueryBuilder(name)


# Singleton
_db_instance = None


def get_db() -> Database:
    """Get the singleton Database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
