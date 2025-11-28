import sqlite3
from datetime import datetime
import pandas as pd

DB_FILE = "sentinel_data.db"

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Tracked Stocks (Updated Schema for Custom Alerts)
    # We use ALTER TABLE to add columns if they don't exist (for existing DBs)
    c.execute('''CREATE TABLE IF NOT EXISTS tracked_stocks (
                    ticker TEXT PRIMARY KEY,
                    search_term TEXT,
                    sentiment_thresh REAL DEFAULT 0.2,
                    anomaly_thresh REAL DEFAULT 3.0
                )''')
    
    # Migration for existing DBs (Safe to run every time)
    try:
        c.execute("ALTER TABLE tracked_stocks ADD COLUMN sentiment_thresh REAL DEFAULT 0.2")
        c.execute("ALTER TABLE tracked_stocks ADD COLUMN anomaly_thresh REAL DEFAULT 3.0")
    except sqlite3.OperationalError:
        pass # Columns already exist

    # ... (Keep other tables same) ...
    c.execute('''CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    timestamp DATETIME,
                    price REAL,
                    volume INTEGER
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS sentiment_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    source TEXT,
                    content TEXT,
                    sentiment_score REAL,
                    timestamp DATETIME
                )''')
                
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    alert_type TEXT,
                    message TEXT,
                    timestamp DATETIME
                )''')
    
    conn.commit()
    conn.close()

# --- Data Access Objects (DAO) ---

def add_stock(ticker, term, sent_thresh=0.2, anom_thresh=3.0):
    conn = get_connection()
    # Updated to store thresholds
    conn.execute("""
        INSERT OR REPLACE INTO tracked_stocks (ticker, search_term, sentiment_thresh, anomaly_thresh) 
        VALUES (?, ?, ?, ?)
    """, (ticker.upper(), term, sent_thresh, anom_thresh))
    conn.commit()
    conn.close()

def update_stock_thresholds(ticker, sent_thresh, anom_thresh):
    """Updates alert thresholds for an existing stock."""
    conn = get_connection()
    conn.execute("""
        UPDATE tracked_stocks 
        SET sentiment_thresh = ?, anomaly_thresh = ? 
        WHERE ticker = ?
    """, (sent_thresh, anom_thresh, ticker))
    conn.commit()
    conn.close()

def get_tracked_stocks():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM tracked_stocks", conn)
    conn.close()
    return df.to_dict('records')

def remove_stock(ticker):
    conn = get_connection()
    conn.execute("DELETE FROM tracked_stocks WHERE ticker = ?", (ticker,))
    conn.commit()
    conn.close()

# ... (Keep logging functions same) ...
def log_market_data(ticker, price, volume):
    conn = get_connection()
    ts = datetime.now()
    conn.execute("INSERT INTO market_data (ticker, timestamp, price, volume) VALUES (?, ?, ?, ?)", 
                 (ticker, ts, price, volume))
    conn.commit()
    conn.close()

def log_sentiment(ticker, source, content, score):
    conn = get_connection()
    ts = datetime.now()
    conn.execute("INSERT INTO sentiment_data (ticker, source, content, sentiment_score, timestamp) VALUES (?, ?, ?, ?, ?)", 
                 (ticker, source, content, score, ts))
    conn.commit()
    conn.close()

def log_alert(ticker, alert_type, message):
    conn = get_connection()
    ts = datetime.now()
    conn.execute("INSERT INTO alerts (ticker, alert_type, message, timestamp) VALUES (?, ?, ?, ?)", 
                 (ticker, alert_type, message, ts))
    conn.commit()
    conn.close()

def fetch_recent_alerts(limit=10):
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM alerts ORDER BY id DESC LIMIT {limit}", conn)
    conn.close()
    return df

def fetch_chart_data(ticker, limit=50):
    conn = get_connection()
    df = pd.read_sql(f"SELECT timestamp, price FROM market_data WHERE ticker='{ticker}' ORDER BY id DESC LIMIT {limit}", conn)
    conn.close()
    return df