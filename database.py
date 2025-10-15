import sqlite3

conn = sqlite3.connect('results.db')
conn.row_factory = sqlite3.Row

def init_db():
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
    return conn.execute('SELECT * FROM analysis_results WHERE file_hash = ?', (hash,)).fetchone()

def db_start_analyze(hash, name, lang, status):
    conn.execute('''
        INSERT INTO analysis_results (file_hash, filename, language, status)
        VALUES (?, ?, ?, ?)
        ''', (hash, name, lang, status))
    conn.commit()

init_db()