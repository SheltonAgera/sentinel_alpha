import yfinance as yf
import feedparser
import numpy as np
import praw
import os
import requests
import re
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import database as db

# Load Environment Variables
load_dotenv()

# Initialize NLP Engine
analyzer = SentimentIntensityAnalyzer()

# Initialize Reddit
reddit = None
if os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"):
    try:
        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent="PBL_Project_3.0_Bot_v1"
        )
    except Exception as e:
        print(f"Reddit Auth Error: {e}")

# --- HELPER FUNCTIONS ---

def clean_html(raw_html):
    """Remove HTML tags from text."""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def fetch_market_price(ticker):
    """Fetches real-time price from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d", interval="1m")
        if not data.empty:
            latest = data.iloc[-1]
            return latest['Close'], int(latest['Volume'])
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
    return None, None

def fetch_historical_data(ticker, period="1mo"):
    """Fetches historical OHLC data for charting."""
    try:
        stock = yf.Ticker(ticker)
        # Adjust interval based on period for best chart appearance
        interval = "1d"
        if period in ["1d", "5d"]:
            interval = "15m" if period == "5d" else "5m"
            
        hist = stock.history(period=period, interval=interval)
        return hist
    except Exception as e:
        print(f"Error fetching history for {ticker}: {e}")
        return None

def fetch_fundamentals(ticker):
    """
    Fetches extended fundamental data including Valuation, Profitability, and Health.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            # Basic Info
            "longName": info.get("longName", ticker),
            "summary": info.get("longBusinessSummary", "No description available."),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            
            # Valuation
            "marketCap": info.get("marketCap", None),
            "trailingPE": info.get("trailingPE", None),
            "forwardPE": info.get("forwardPE", None),
            "pegRatio": info.get("pegRatio", None),
            "bookValue": info.get("bookValue", None),
            
            # Profitability
            "trailingEps": info.get("trailingEps", None),
            "dividendYield": info.get("dividendYield", None),
            "returnOnEquity": info.get("returnOnEquity", None),
            "returnOnAssets": info.get("returnOnAssets", None), # Proxy for ROCE
            
            # Financial Health
            "totalRevenue": info.get("totalRevenue", None),
            "debtToEquity": info.get("debtToEquity", None),
            "freeCashflow": info.get("freeCashflow", None),
            "totalCash": info.get("totalCash", None), # Proxy for Reserves
            
            # Price Stats
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh", None),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow", None),
        }
    except Exception as e:
        print(f"Error fetching fundamentals: {e}")
        return None

def fetch_analyst_data(ticker):
    """Fetches Analyst Ratings and Price Targets."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "targetHigh": info.get("targetHighPrice", None),
            "targetLow": info.get("targetLowPrice", None),
            "targetMean": info.get("targetMeanPrice", None),
            "recommendation": info.get("recommendationKey", "none").replace("_", " ").title(),
            "numberOfAnalysts": info.get("numberOfAnalystOpinions", 0)
        }
    except Exception:
        return None

# --- SOCIAL & NEWS SCRAPERS ---

def fetch_valuepickr_threads(search_term):
    """
    Fetches discussions from ValuePickr with STRICT FILTERING.
    """
    clean_term = search_term.split('.')[0].strip() # Remove ticker extension
    url = "https://forum.valuepickr.com/search/query.json"
    params = {"term": clean_term, "include_blurbs": "true"}
    headers = {"User-Agent": "Mozilla/5.0"}
    
    discussions = []
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json()
        
        if 'topics' in data:
            for topic in data['topics']:
                title = topic.get('title', 'No Title')
                # Strict Filter
                if clean_term.lower() not in title.lower(): continue 

                slug = topic.get('slug', '')
                topic_id = topic.get('id', '')
                post_url = f"https://forum.valuepickr.com/t/{slug}/{topic_id}"
                sentiment = analyzer.polarity_scores(title)['compound']
                
                discussions.append({
                    "source": "ValuePickr Forum",
                    "title": title,
                    "url": post_url,
                    "sentiment": sentiment,
                    "snippet": f"Active thread on ValuePickr..."
                })
    except Exception:
        pass
    return discussions[:10]

def fetch_reddit_posts(search_term, limit=15):
    """
    Fetches Reddit posts with STRICT FILTERING.
    """
    if not reddit: return None 
    clean_term = search_term.split('.')[0].strip()
    posts_data = []
    try:
        subreddits = ["IndianStreetBets", "DalalStreetTalks", "IndianStockMarket", "IndiaInvestments", "stocks"]
        query = f"{clean_term}"
        
        for post in reddit.subreddit("all").search(query, sort='relevance', time_filter='month', limit=limit):
            # Strict Filter
            if clean_term.lower() not in post.title.lower(): continue
            
            # Subreddit Filter
            is_relevant = post.subreddit.display_name in subreddits or "stock" in post.subreddit.display_name.lower() or "invest" in post.subreddit.display_name.lower()
            
            if is_relevant:
                sentiment = analyzer.polarity_scores(post.title)['compound']
                posts_data.append({
                    "source": f"r/{post.subreddit.display_name}",
                    "title": post.title,
                    "url": post.url,
                    "sentiment": sentiment,
                    "score": post.score,
                    "comments": post.num_comments
                })
    except Exception:
        pass
    return posts_data

def fetch_news_sentiment(ticker, search_term):
    """Fetches news from MULTIPLE RSS Sources."""
    clean_term = search_term.replace(" ", "%20")
    rss_sources = [
        f"https://news.google.com/rss/search?q={clean_term}&hl=en-IN&gl=IN&ceid=IN:en",
        f"https://news.google.com/rss/search?q={clean_term}+site:finance.yahoo.com&hl=en-IN&gl=IN&ceid=IN:en",
        f"https://news.google.com/rss/search?q={clean_term}+site:moneycontrol.com&hl=en-IN&gl=IN&ceid=IN:en",
        f"https://news.google.com/rss/search?q={clean_term}+site:economictimes.indiatimes.com&hl=en-IN&gl=IN&ceid=IN:en",
        f"https://news.google.com/rss/search?q={clean_term}+site:livemint.com&hl=en-IN&gl=IN&ceid=IN:en"
    ]
    
    scores = []
    articles = []
    seen_links = set()
    
    for url in rss_sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.title
                link = entry.link
                if link in seen_links: continue
                seen_links.add(link)
                
                sentiment = analyzer.polarity_scores(title)['compound']
                
                # Identify Source
                source_name = "News"
                if "moneycontrol" in link: source_name = "MoneyControl"
                elif "livemint" in link: source_name = "LiveMint"
                elif "economictimes" in link: source_name = "Economic Times"
                elif "yahoo" in link: source_name = "Yahoo Finance"
                else: source_name = "Google News"
                
                db.log_sentiment(ticker, source_name, title, sentiment)
                scores.append(sentiment)
                articles.append((title, sentiment, link))
        except Exception:
            pass
            
    avg_score = np.mean(scores) if scores else 0.0
    return avg_score, articles

PEER_MAP = {
    "RELIANCE.NS": ["TATASTEEL.NS", "ADANIENT.NS"],
    "TCS.NS": ["INFY.NS", "WIPRO.NS"],
    "HDFCBANK.NS": ["ICICIBANK.NS", "SBIN.NS"],
    "INFY.NS": ["TCS.NS", "HCLTECH.NS"],
    "TATAMOTORS.NS": ["MARUTI.NS", "ASHOKLEY.NS"],
    "ADANIENT.NS": ["RELIANCE.NS", "TATASTEEL.NS"],
    # Add more as needed
}

def get_peers(ticker):
    """Returns a list of peer tickers for a given stock."""
    return PEER_MAP.get(ticker, ["^NSEI"]) # Default to Nifty 50 if unknown

def generate_ai_summary(sentiment_score, z_score):
    """
    Generates a 'Smart Summary' based on data signals.
    """
    summary = "Market is neutral. No major signals detected."
    
    # High Volatility Scenarios
    if z_score > 3.0:
        if sentiment_score > 0.2:
            summary = "🚀 **Bullish Breakout:** High volume spike backed by positive news suggests strong buying momentum."
        elif sentiment_score < -0.2:
            summary = "🩸 **Panic Selling:** Heavy volume with negative sentiment indicates a potential crash or correction."
        else:
            summary = "⚠️ **Volatile Uncertainty:** Massive volume spike without clear sentiment direction. Tread carefully."
            
    # Low Volatility Scenarios
    else:
        if sentiment_score > 0.4:
            summary = "📈 **Silent Accumulation:** Strong positive chatter despite normal volume. Watch for a breakout."
        elif sentiment_score < -0.4:
            summary = "📉 **Bearish Sentiment:** Negative rumors circulating. Price may drift lower."
            
    return summary
# --- ANALYSIS & PIPELINE ---

def detect_anomalies(ticker, current_volume, threshold=3.0):
    """
    Uses Z-Score with CUSTOM THRESHOLD passed from DB.
    """
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT volume FROM market_data WHERE ticker=? ORDER BY id DESC LIMIT 20", (ticker,))
    rows = c.fetchall()
    conn.close()
    
    volumes = [r[0] for r in rows]
    if len(volumes) < 5: return False, 0.0
    
    mean_vol = np.mean(volumes)
    std_vol = np.std(volumes)
    if std_vol == 0: return False, 0.0
    
    z_score = (current_volume - mean_vol) / std_vol
    
    # Use the custom threshold
    if z_score > threshold:
        return True, z_score
    return False, z_score

def run_pipeline():
    """Runs the full data collection and analysis cycle."""
    stocks = db.get_tracked_stocks()
    summary = []
    
    if not stocks: return "No stocks tracked."

    for stock in stocks:
        ticker = stock['ticker']
        term = stock['search_term']
        
        # Retrieve custom alert settings (defaulting if missing)
        s_thresh = stock.get('sentiment_thresh', 0.2)
        a_thresh = stock.get('anomaly_thresh', 3.0)
        
        # 1. Market Data & Anomaly Check
        price, vol = fetch_market_price(ticker)
        if price:
            db.log_market_data(ticker, price, vol)
            # Pass custom anomaly threshold
            is_anom, z = detect_anomalies(ticker, vol, threshold=a_thresh)
            if is_anom: 
                msg = f"Volume Spike (Z={z:.2f} > {a_thresh})"
                db.log_alert(ticker, "ANOMALY", msg)

        # 2. News Sentiment Check
        avg, arts = fetch_news_sentiment(ticker, term)
        # Check against custom sentiment threshold
        if abs(avg) > s_thresh:
            stype = "Positive" if avg > 0 else "Negative"
            msg = f"News Sentiment Shift: {stype} ({avg:.2f} > {s_thresh})"
            db.log_alert(ticker, "SENTIMENT", msg)
        
        summary.append(f"{ticker}: ₹{price:.2f}")
            
    return " | ".join(summary)