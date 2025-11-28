import os
import numpy as np
import yfinance as yf
import praw
from datetime import datetime, timezone
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from dotenv import load_dotenv
from database import save_price, save_social, log_alert, get_recent_prices, get_recent_social

load_dotenv()

# --- CONFIG ---
analyzer = SentimentIntensityAnalyzer()
REDDIT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")

def get_market_data(ticker):
    """Fetch 1-minute interval price data"""
    try:
        t = yf.Ticker(ticker)
        # Get 1 day of data at 1m interval
        hist = t.history(period="1d", interval="1m")
        if not hist.empty:
            row = hist.iloc[-1]
            # Format Timestamp
            ts = row.name.isoformat()
            return {"ts": ts, "close": row["Close"], "volume": int(row["Volume"])}
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
    return None

def get_reddit_data(ticker, keyword):
    """Fetch recent posts from Reddit"""
    if not REDDIT_ID:
        print("Reddit keys missing!")
        return []
    
    reddit = praw.Reddit(
        client_id=REDDIT_ID,
        client_secret=REDDIT_SECRET,
        user_agent="Sentinel_App_v1"
    )
    
    posts_found = []
    # Search mostly Indian focused subreddits + generic ones
    subs = ["IndianStreetBets", "DalalStreetTalks", "stocks"]
    
    print(f"Scanning Reddit for {keyword}...")
    try:
        for sub in subs:
            for post in reddit.subreddit(sub).search(keyword, sort='new', time_filter='day', limit=5):
                text = f"{post.title} {post.selftext}"[:500]
                sentiment = analyzer.polarity_scores(text)['compound']
                
                # Check if we should save (simple dedup check could go here)
                ts = datetime.fromtimestamp(post.created_utc).isoformat()
                save_social(ticker, f"Reddit (r/{sub})", post.title, ts, sentiment)
                posts_found.append(sentiment)
    except Exception as e:
        print(f"Reddit Error: {e}")
        
    return posts_found

def analyze_ticker(ticker, keyword):
    """Run the full analysis pipeline for one stock"""
    print(f"--- Analyzing {ticker} ---")
    
    # 1. Price Check
    data = get_market_data(ticker)
    if data:
        save_price(ticker, data['ts'], data['close'], data['volume'])
        
        # 2. Volume Anomaly Check
        history = get_recent_prices(ticker, limit=20)
        if len(history) > 10:
            vols = [r[2] for r in history] # Volume is index 2
            mean_vol = np.mean(vols)
            std_vol = np.std(vols)
            current_vol = data['volume']
            
            # Avoid divide by zero
            if std_vol > 0:
                z_score = (current_vol - mean_vol) / std_vol
                if z_score > 3: # 3 Sigma Event
                    log_alert(ticker, f"Volume Spike (Z={z_score:.2f})", z_score)
                    print(f"🚨 ALERT: Volume Spike for {ticker}")

    # 3. Sentiment Check
    sentiments = get_reddit_data(ticker, keyword)
    if sentiments:
        avg_sent = np.mean(sentiments)
        if abs(avg_sent) > 0.4: # Strong Sentiment
            log_alert(ticker, f"High Social Sentiment ({avg_sent:.2f})", avg_sent)
            print(f"🚨 ALERT: Sentiment Spike for {ticker}")
            
    return "Done"