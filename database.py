import sqlite3
import os

DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'results.db')

def get_connect():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connect()
    c = conn.cursor()
    # 创建文件分析结果表
    c.execute('''
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_hash TEXT UNIQUE NOT NULL,
        filename TEXT NOT NULL,
        language TEXT NOT NULL,
        analysis_result TEXT,
        status TEXT DEFAULT 'pending'
    )
    ''')
    conn.commit()
    conn.close()

def is_analyzed(hash):
    conn = get_connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM results WHERE file_hash = ?', (hash,))
        rows = cursor.fetchone()
        if rows is not None:
            records = dict(rows)
        else:
            records = None
    finally:
        cursor.close()
        conn.close()
    
    return records

def get_limited_results(limit=3):
    conn = get_connect()
    
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT file_hash, filename, language, status 
        FROM results 
        LIMIT ?
        """, (limit,))
    
    records = [dict(row) for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    return records

def db_start_analyze(hash, name, lang, status):
    conn = get_connect()
    conn.execute('''
        INSERT INTO results (file_hash, filename, language, status)
        VALUES (?, ?, ?, ?)
        ''', (hash, name, lang, status))
    conn.commit()
    conn.close()

def db_finish_analyze(hash, gcs_str):
    conn = get_connect()
    conn.execute('''
        UPDATE results
        SET status = ?, analysis_result = ?
        WHERE file_hash = ?
        ''', ('finished', gcs_str, hash))
    conn.commit()
    conn.close()

init_db()