import sqlite3
import os
from flask import current_app

def get_conn():
    cfg = current_app.config
    db_path = cfg["DB_NAME"]
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _prepare_sql(sql):
    # MySQL uses %s, SQLite uses ?
    return sql.replace('%s', '?')

def query_one(sql, params=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        sql = _prepare_sql(sql)
        cur.execute(sql, params or ())
        row = cur.fetchone()
        conn.commit()
        if row:
            return dict(row)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass

def query_all(sql, params=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        sql = _prepare_sql(sql)
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        conn.commit()
        return [dict(row) for row in rows]
    finally:
        try:
            conn.close()
        except Exception:
            pass

def execute(sql, params=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        sql = _prepare_sql(sql)
        cur.execute(sql, params or ())
        conn.commit()
        return cur.rowcount
    finally:
        try:
            conn.close()
        except Exception:
            pass

def executemany(sql, seq_params):
    conn = get_conn()
    try:
        cur = conn.cursor()
        sql = _prepare_sql(sql)
        cur.executemany(sql, seq_params)
        conn.commit()
        return cur.rowcount
    finally:
        try:
            conn.close()
        except Exception:
            pass
