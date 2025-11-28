import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go 
import database as db
import backend as bk
import time
from datetime import datetime, timedelta

# --- Page Config ---
st.set_page_config(page_title="PBL Project 3.0", page_icon="📈", layout="wide")

# Initialize DB
db.init_db()

# --- HELPER FUNCTIONS ---

def get_time_ago(timestamp_str):
    try:
        dt = pd.to_datetime(timestamp_str)
        now = datetime.now()
        diff = now - dt
        minutes = int(diff.total_seconds() / 60)
        if minutes < 1: return "Just now"
        if minutes < 60: return f"{minutes} min ago"
        hours = int(minutes / 60)
        if hours < 24: return f"{hours} hr ago"
        return f"{int(hours/24)} days ago"
    except:
        return timestamp_str

def fmt_num(num):
    if num is None: return "N/A"
    if num > 1e9: return f"₹{num/1e9:.2f} B"
    if num > 1e6: return f"₹{num/1e6:.2f} M"
    return f"₹{num:.2f}"

def fmt_pct(num):
    if num is None: return "N/A"
    return f"{num * 100:.2f}%"

def get_smart_tags(title):
    """
    Analyzes headline text and returns a list of (Label, HexColor) tuples.
    """
    if not title: return []
    title_lower = title.lower()
    tags = []
    
    if any(x in title_lower for x in ["profit", "loss", "quarter", "q1", "q2", "q3", "q4", "result", "revenue", "dividend", "net income", "margin"]):
        tags.append(("💰 Earnings", "#FFD700")) 
    if any(x in title_lower for x in ["acquire", "deal", "merge", "partnership", "contract", "order", "win", "launch", "expand", "new"]):
        tags.append(("🚀 Growth", "#00CC96")) 
    if any(x in title_lower for x in ["ceo", "cfo", "resign", "appoint", "quit", "step down", "board", "director", "management"]):
        tags.append(("👔 Mgmt", "#AB63FA")) 
    if any(x in title_lower for x in ["sebi", "rbi", "ban", "fraud", "scam", "court", "suit", "penalty", "fine", "compliance"]):
        tags.append(("⚖️ Legal", "#EF553B")) 
    if any(x in title_lower for x in ["surge", "jump", "crash", "drop", "plunge", "rally", "target", "upgrade", "downgrade", "buy", "sell"]):
        tags.append(("📈 Market", "#636EFA"))
        
    return tags

# --- SIDEBAR ---
st.sidebar.title("PBL Project 3.0")
st.sidebar.markdown("**Real-Time Sentiment & Anomaly Alert System**")

# 1. Add Stock
st.sidebar.subheader("➕ Add Stock")
with st.sidebar.form("Add Stock"):
    ticker = st.text_input("Ticker Symbol (e.g. RELIANCE.NS)")
    term = st.text_input("Search Keyword (e.g. Reliance)")
    if st.form_submit_button("Start Tracking"):
        if ticker and term:
            db.add_stock(ticker, term)
            st.success(f"Tracking {ticker}")
            time.sleep(1)
            st.rerun() 

# 2. Remove Stock
st.sidebar.divider()
st.sidebar.subheader("❌ Remove Stock")
current_stocks = db.get_tracked_stocks()
stock_list = [s['ticker'] for s in current_stocks]

if stock_list:
    selected_to_remove = st.sidebar.selectbox("Select Stock to Remove", stock_list)
    if st.sidebar.button("Remove Stock"):
        db.remove_stock(selected_to_remove)
        st.sidebar.success(f"Removed {selected_to_remove}")
        time.sleep(1)
        st.rerun()
else:
    st.sidebar.caption("No stocks being tracked.")

# 3. Refresh Controls
st.sidebar.divider()
auto_refresh = st.sidebar.checkbox("Enable Auto-Refresh (1 min)")

if auto_refresh:
    with st.spinner("Syncing with Market..."):
        status = bk.run_pipeline()
        time.sleep(60) 
        st.rerun()

if st.sidebar.button("🔄 Manual Refresh"):
    with st.spinner("Fetching Data..."):
        status = bk.run_pipeline()
    st.sidebar.success(status)

st.sidebar.divider()
st.sidebar.markdown("### 🛠 Project Details")
st.sidebar.info("Team 10\nCourse: Cloud Computing\nCode: 22CBS73")

# --- MAIN DASHBOARD ---

# 1. PREPARE DATA
stocks = db.get_tracked_stocks()
tracked_tickers = [s['ticker'] for s in stocks] if stocks else []

# 2. GLOBAL ALERT BANNER (Filtered & Time-Limited)
if tracked_tickers:
    all_alerts = db.fetch_recent_alerts(20)
    
    if not all_alerts.empty:
        active_alerts = all_alerts[all_alerts['ticker'].isin(tracked_tickers)]
        active_alerts['dt'] = pd.to_datetime(active_alerts['timestamp'])
        recent_limit = datetime.now() - timedelta(hours=24)
        active_alerts = active_alerts[active_alerts['dt'] > recent_limit]
        
        if not active_alerts.empty:
            st.subheader("🔔 Live Market Alerts (Last 24h)")
            st.markdown("""
                <style>
                .alert-card {
                    padding: 15px; border-radius: 8px; margin-bottom: 10px;
                    border-left: 5px solid; background-color: #262730;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                }
                .alert-header { display: flex; justify_content: space-between; font-weight: bold; font-size: 1.1em; }
                .alert-time { font-size: 0.8em; color: #aaa; }
                .anomaly { border-color: #ff4b4b; }
                .sentiment-pos { border-color: #00cc96; }
                .sentiment-neg { border-color: #ffa500; }
                </style>
            """, unsafe_allow_html=True)

            for index, row in active_alerts.head(3).iterrows():
                alert_class = "anomaly"
                icon = "🚨"
                if "SENTIMENT" in row['alert_type']:
                    if "Positive" in row['message']:
                        alert_class = "sentiment-pos"
                        icon = "🚀"
                    else:
                        alert_class = "sentiment-neg"
                        icon = "⚠️"
                
                st.markdown(f"""
                    <div class="alert-card {alert_class}">
                        <div class="alert-header">
                            <span>{icon} {row['ticker']}</span>
                            <span class="alert-time">{get_time_ago(row['timestamp'])}</span>
                        </div>
                        <div style="margin-top: 5px;">{row['message']}</div>
                    </div>
                """, unsafe_allow_html=True)

# 3. STOCK DATA GRID
st.subheader("📊 Market Intelligence Dashboard")

if not stocks:
    st.info("System Ready. Add a stock in the sidebar to begin analysis.")
else:
    tabs = st.tabs([s['ticker'] for s in stocks])
    
    for i, stock in enumerate(stocks):
        with tabs[i]:
            t = stock['ticker']
            term = stock['search_term']
            
            # Retrieve settings
            current_s_thresh = stock.get('sentiment_thresh', 0.2)
            current_a_thresh = stock.get('anomaly_thresh', 3.0)
            
            sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5 = st.tabs([
                "📈 Overview", "🏢 Fundamentals", "📰 News Pulse", "🗣️ Social & Experts", "🔔 Alert Config"
            ])

            # --- SUB-TAB 1: Price & Overview ---
            with sub_tab1:
                conn = db.get_connection()
                sent_df = pd.read_sql(f"SELECT * FROM sentiment_data WHERE ticker='{t}' ORDER BY id DESC LIMIT 20", conn)
                current_sent = sent_df['sentiment_score'].mean() if not sent_df.empty else 0.0
                
                vol_df = pd.read_sql(f"SELECT volume FROM market_data WHERE ticker='{t}' ORDER BY id DESC LIMIT 20", conn)
                conn.close()
                
                current_z = 0.0
                if len(vol_df) > 5:
                    vols = vol_df['volume'].values
                    mean_vol = vols.mean()
                    std_vol = vols.std()
                    if std_vol > 0:
                        current_z = (vols[0] - mean_vol) / std_vol

                ai_text = bk.generate_ai_summary(current_sent, current_z)
                st.info(f"🤖 **AI Executive Brief:** {ai_text}")

                stock_alerts = db.fetch_recent_alerts(10)
                stock_alerts = stock_alerts[stock_alerts['ticker'] == t]
                if not stock_alerts.empty:
                    with st.expander(f"🚨 Recent Alerts for {t}", expanded=True):
                        for ix, row in stock_alerts.head(3).iterrows():
                            st.caption(f"{get_time_ago(row['timestamp'])}: {row['message']}")

                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown("#### Price Action Analysis")
                    # FIX: Added unique key for selectbox
                    timeframe = st.selectbox(
                        f"Select Timeframe ({t})", 
                        ["1 Day", "5 Days", "1 Month", "6 Months", "1 Year", "5 Years"], 
                        index=3, 
                        key=f"timeframe_select_{t}_{i}"
                    )
                    
                    period_map = {"1 Day": "1d", "5 Days": "5d", "1 Month": "1mo", "6 Months": "6mo", "1 Year": "1y", "5 Years": "5y"}
                    
                    with st.spinner("Loading chart data..."):
                        hist_df = bk.fetch_historical_data(t, period=period_map[timeframe])

                    if hist_df is not None and not hist_df.empty:
                        fig = go.Figure()
                        fig.add_trace(go.Candlestick(x=hist_df.index, open=hist_df['Open'], high=hist_df['High'], low=hist_df['Low'], close=hist_df['Close'], name='Price'))
                        if len(hist_df) > 21:
                            hist_df['SMA_21'] = hist_df['Close'].rolling(window=21).mean()
                            fig.add_trace(go.Scatter(x=hist_df.index, y=hist_df['SMA_21'], mode='lines', name='SMA 21', line=dict(color='yellow', width=1)))
                        if len(hist_df) > 50:
                            hist_df['SMA_50'] = hist_df['Close'].rolling(window=50).mean()
                            fig.add_trace(go.Scatter(x=hist_df.index, y=hist_df['SMA_50'], mode='lines', name='SMA 50', line=dict(color='orange', width=1)))
                        if len(hist_df) > 200:
                            hist_df['SMA_200'] = hist_df['Close'].rolling(window=200).mean()
                            fig.add_trace(go.Scatter(x=hist_df.index, y=hist_df['SMA_200'], mode='lines', name='SMA 200', line=dict(color='red', width=1)))
                        fig.update_layout(title=f"{t} - {timeframe} Chart", yaxis_title="Price", xaxis_rangeslider_visible=False, template="plotly_dark", height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Could not load chart data.")

                with col2:
                    st.markdown("#### 🌡️ The Hype Meter")
                    fig_gauge = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = current_sent,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': "Sentiment Score"},
                        gauge = {
                            'axis': {'range': [-1, 1], 'tickwidth': 1, 'tickcolor': "white"},
                            'bar': {'color': "white", 'thickness': 0.2},
                            'bgcolor': "black",
                            'steps': [
                                {'range': [-1, -0.5], 'color': "#FF4545"},
                                {'range': [-0.5, 0], 'color': "#FFB74D"},
                                {'range': [0, 0.5], 'color': "#AED581"},
                                {'range': [0.5, 1], 'color': "#00C853"}
                            ],
                            'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': current_sent}
                        }
                    ))
                    fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20), paper_bgcolor="#262730", font={'color': "white"})
                    st.plotly_chart(fig_gauge, use_container_width=True)
                    
                    st.markdown("#### ⚔️ Peer Clash")
                    peers = bk.get_peers(t)
                    for peer in peers:
                        with st.spinner(f"Fetching {peer}..."):
                            p_price, p_vol = bk.fetch_market_price(peer)
                        if p_price:
                            st.metric(f"{peer}", f"₹{p_price:.2f}")
                        else:
                            st.caption(f"Could not fetch {peer}")

            # --- SUB-TAB 2: Fundamentals ---
            with sub_tab2:
                st.markdown(f"### 🏢 Deep Dive: {t}")
                with st.spinner("Fetching full fundamental report..."):
                    fund = bk.fetch_fundamentals(t)
                if fund:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Market Cap", fmt_num(fund['marketCap']))
                    c2.metric("P/E Ratio", f"{fund['trailingPE']:.2f}" if fund['trailingPE'] else "N/A")
                    c3.metric("PEG Ratio", f"{fund['pegRatio']:.2f}" if fund['pegRatio'] else "N/A")
                    c4.metric("Book Value", f"₹{fund['bookValue']:.2f}" if fund['bookValue'] else "N/A")
                    st.divider()
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("ROE", fmt_pct(fund['returnOnEquity']))
                    k2.metric("ROA", fmt_pct(fund['returnOnAssets']))
                    k3.metric("EPS", f"₹{fund['trailingEps']:.2f}" if fund['trailingEps'] else "N/A")
                    k4.metric("Total Sales", fmt_num(fund['totalRevenue']))
                    st.divider()
                    h1, h2, h3 = st.columns(3)
                    h1.metric("Debt to Equity", f"{fund['debtToEquity']:.2f}" if fund['debtToEquity'] else "N/A")
                    h2.metric("Free Cash Flow", fmt_num(fund['freeCashflow']))
                    h3.metric("Total Cash", fmt_num(fund['totalCash']))
                    st.divider()
                    st.info(f"**Business Summary:** {fund['summary']}")
                else:
                    st.error("Data unavailable.")

            # --- SUB-TAB 3: News ---
            with sub_tab3:
                st.markdown("#### 📰 Recent Headlines")
                conn = db.get_connection()
                news_df = pd.read_sql(f"SELECT * FROM sentiment_data WHERE ticker='{t}' AND source != 'Reddit' ORDER BY id DESC LIMIT 10", conn)
                conn.close()
                if not news_df.empty:
                    for idx, row in news_df.iterrows():
                        emoji = "🟢" if row['sentiment_score'] > 0 else "🔴"
                        clean_title = row['content'].rsplit('-', 1)[0]
                        
                        # Use Helper Function
                        tags = get_smart_tags(clean_title)
                        
                        tag_html = ""
                        for tag_text, tag_color in tags:
                            tag_html += f"<span style='background-color:{tag_color}20; color:{tag_color}; border:1px solid {tag_color}; padding:2px 8px; border-radius:12px; font-size:0.75em; font-weight:bold; margin-right:5px;'>{tag_text}</span>"
                        
                        st.markdown(f"{emoji} {tag_html} **{row['source']}**: {clean_title}", unsafe_allow_html=True)
                        st.caption(f"Sentiment Score: {row['sentiment_score']:.2f} | Time: {get_time_ago(row['timestamp'])}")
                        st.markdown("---")
                else:
                    st.info("No news found.")

            # --- SUB-TAB 4: Social & Experts ---
            with sub_tab4:
                col_expert, col_social = st.columns([1, 1])
                with col_expert:
                    st.markdown("#### 🧠 Expert Consensus")
                    with st.spinner("Analyzing Expert Data..."):
                        expert_data = bk.fetch_analyst_data(t)
                    if expert_data:
                        rec = expert_data['recommendation']
                        rec_color = "green" if "buy" in rec.lower() else "red" if "sell" in rec.lower() else "orange"
                        st.markdown(f"""
                            <div style="text-align: center; padding: 20px; background-color: #262730; border-radius: 10px;">
                                <h2 style="color: {rec_color}; margin:0;">{rec.upper()}</h2>
                                <p>Based on {expert_data['numberOfAnalysts']} Opinions</p>
                            </div>
                        """, unsafe_allow_html=True)
                        if expert_data['targetMean']:
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Low", f"₹{expert_data['targetLow']}")
                            c2.metric("Mean", f"₹{expert_data['targetMean']}")
                            c3.metric("High", f"₹{expert_data['targetHigh']}")
                    else:
                        st.warning("No Analyst Data.")
                with col_social:
                    st.markdown("#### 💬 Forum Discussions")
                    whisper_mode = st.toggle("🕵️ Activate Whisper Mode", key=f"whisper_{t}_{i}") # FIX: Unique Key
                    
                    with st.spinner("Scanning Forums..."):
                        reddit_posts = bk.fetch_reddit_posts(term)
                        vp_posts = bk.fetch_valuepickr_threads(term)
                    all_posts = []
                    if reddit_posts: all_posts.extend(reddit_posts)
                    if vp_posts: all_posts.extend(vp_posts)
                    if not all_posts:
                        st.info("No active discussions.")
                    else:
                        for post in all_posts:
                            p_score = post['sentiment']
                            if whisper_mode:
                                likes = post.get('score', 0)
                                if likes > 10 or abs(p_score) < 0.5: continue
                                st.caption("🕵️ Potential Whisper Detected")
                            emoji = "🐂" if p_score > 0.1 else "🐻"
                            source_tag = "🟦 Reddit" if "r/" in post['source'] else "🟩 ValuePickr"
                            st.markdown(f"""
                                <div style="border-left: 3px solid #555; padding-left: 10px; margin-bottom: 10px;">
                                    <strong>{emoji} {post['title']}</strong><br>
                                    <span style="font-size: 0.8em; color: #aaa;">
                                        {source_tag} • Sentiment: {p_score:.2f}
                                    </span>
                                </div>
                            """, unsafe_allow_html=True)
                            st.markdown(f"[Read More]({post['url']})")
                            st.markdown("---")

            # --- SUB-TAB 5: Alert Config ---
            with sub_tab5:
                st.markdown(f"### ⚙️ Configure Alerts for {t}")
                st.markdown("Adjust the sensitivity of the monitoring system for this specific stock.")
                with st.form(f"config_form_{t}"):
                    col_s, col_a = st.columns(2)
                    with col_s:
                        st.markdown("#### 📰 Sentiment Sensitivity")
                        # FIX: Unique Keys for Sliders
                        new_s_thresh = st.slider("Sentiment Threshold", 0.1, 1.0, float(current_s_thresh), 0.05, key=f"s_slider_{t}_{i}")
                    with col_a:
                        st.markdown("#### 📉 Anomaly Sensitivity")
                        new_a_thresh = st.slider("Anomaly Threshold", 2.0, 6.0, float(current_a_thresh), 0.1, key=f"a_slider_{t}_{i}")
                    
                    if st.form_submit_button("💾 Save Settings"):
                        db.update_stock_thresholds(t, new_s_thresh, new_a_thresh)
                        st.success(f"Settings updated for {t}!")
                        time.sleep(1)
                        st.rerun()