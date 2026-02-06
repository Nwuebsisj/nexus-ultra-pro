import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import pytz
import requests
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Nexus Ultra Pro 24/7", layout="wide")
st.title("🏛️ Nexus Ultra Pro: Multi-Asset Engine")

# --- DATABASE SETUP ---
LOG_FILE = "trading_log.csv"
if not os.path.exists(LOG_FILE):
    pd.DataFrame(columns=["Timestamp", "Asset", "Signal", "Price", "T1", "T2", "SL"]).to_csv(LOG_FILE, index=False)

# --- SIDEBAR & TELEGRAM CONFIG ---
st.sidebar.header("🕹️ Setup")
asset_name = st.sidebar.selectbox("Asset", ["EURUSD", "GOLD", "USD/PHP"])
symbol = {"EURUSD": "EURUSD=X", "GOLD": "GC=F", "USD/PHP": "PHP=X"}[asset_name]
tf = st.sidebar.selectbox("Timeframe", ["5m", "15m", "1h"], index=1)

st.sidebar.markdown("---")
st.sidebar.header("📲 Telegram Alerts")

# --- SMART LOGIC: SECRETS VS MANUAL ---
if "BOT_TOKEN" in st.secrets and "CHAT_ID" in st.secrets:
    bot_token = st.secrets["BOT_TOKEN"]
    chat_id = str(st.secrets["CHAT_ID"])
    st.sidebar.success("✅ Telegram Linked via Secrets")
else:
    bot_token = st.sidebar.text_input("Bot Token", type="password")
    chat_id = st.sidebar.text_input("Chat ID")

send_alerts = st.sidebar.toggle("Enable Mobile Alerts", value=True)
news_active = st.sidebar.toggle("High Impact News Today?", value=False)

if st.sidebar.button("🔔 Send Test Alert"):
    if bot_token and chat_id:
        test_msg = f"🔔 *Nexus Test*\nAsset: {asset_name}\nStatus: System Online 🚀"
        requests.get(f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                     params={"chat_id": chat_id, "text": test_msg, "parse_mode": "Markdown"})
        st.sidebar.success("Check Telegram!")

# --- DATA ENGINE ---
@st.cache_data(ttl=60)
def get_data(ticker, interval):
    df = yf.download(ticker, period="10d", interval=interval, progress=False)
    if df.empty: return df
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # 5-DIGIT ROUNDING
    df['Close'] = df['Close'].round(5)
    df['EMA20'] = ta.ema(df['Close'], length=20).round(5)
    df['EMA50'] = ta.ema(df['Close'], length=50).round(5)
    
    macd = ta.macd(df['Close'])
    if macd is not None:
        df = pd.concat([df, macd], axis=1)
        hist_col = [c for c in df.columns if 'MACDH' in str(c).upper()][0]
        df['MACD_Hist'] = df[hist_col]
    
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Lower_Wick'] = df[['Open', 'Close']].min(axis=1) - df['Low']
    df['Upper_Wick'] = df['High'] - df[['Open', 'Close']].max(axis=1)
    return df

# --- EXECUTION ---
df = get_data(symbol, tf)

if not df.empty:
    curr = df.iloc[-1]
    pht = datetime.now(pytz.timezone('Asia/Manila'))
    
    # Weekend Logic (Market closes Sat 6AM PHT, Opens Mon 6AM PHT)
    # 5 = Saturday, 6 = Sunday
    is_weekend = pht.weekday() == 6 or (pht.weekday() == 5 and pht.hour >= 6)
    
    # Active Session: 3PM to 11PM PHT (London/NY overlap)
    is_active_hours = 15 <= pht.hour <= 23 

    # --- STATUS LOGIC ---
    if is_weekend:
        signal = "💤 MARKET CLOSED"
        color = "#FFA500" # Orange
    elif news_active:
        signal = "⚠️ NEWS PAUSE (STAY OUT)"
        color = "#FF4B4B"
    elif not is_active_hours:
        signal = "⏳ WAITING FOR SESSION..."
        color = "#888888"
    else:
        signal = "🔎 SCANNING..."
        color = "#888888"

    targets = None

    # --- TRADING LOGIC ---
    if not is_weekend and not news_active and is_active_hours:
        # BUY LOGIC
        if curr['Close'] > curr['EMA50'] and curr['Low'] <= curr['EMA20']:
            if curr['Lower_Wick'] > (curr['Body'] * 0.2) and curr['MACD_Hist'] > 0:
                signal = "🚀 PRO BUY SIGNAL"
                color = "#00FF00"
                risk = abs(curr['Close'] - curr['EMA50'])
                targets = {"SL": curr['EMA50'], "T1": curr['Close'] + risk, "T2": curr['Close'] + (risk * 2)}

        # SELL LOGIC
        elif curr['Close'] < curr['EMA50'] and curr['High'] >= curr['EMA20']:
            if curr['Upper_Wick'] > (curr['Body'] * 0.2) and curr['MACD_Hist'] < 0:
                signal = "🔥 PRO SELL SIGNAL"
                color = "#FF4B4B"
                risk = abs(curr['EMA50'] - curr['Close'])
                targets = {"SL": curr['EMA50'], "T1": curr['Close'] - risk, "T2": curr['Close'] - (risk * 2)}

    # ALERT LOGIC
    if "SIGNAL" in signal:
        msg = f"*{signal}*\n📍 *Asset:* {asset_name}\n💰 *Price:* {curr['Close']:.5f}\n🎯 *TP1:* {targets['T1']:.5f}\n🛑 *SL:* {targets['SL']:.5f}"
        if "last_signal_time" not in st.session_state or st.session_state.last_signal_time != str(df.index[-1]):
            requests.get(f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                         params={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
            st.session_state.last_signal_time = str(df.index[-1])

    # UI RENDERING
    st.markdown(f"<h1 style='text-align: center; color: {color};'>{signal}</h1>", unsafe_allow_html=True)
    if targets:
        c1, c2, c3 = st.columns(3)
        c1.metric("STOP LOSS", f"{targets['SL']:.5f}")
        c2.metric("SAFE TP", f"{targets['T1']:.5f}")
        c3.metric("PRO TP", f"{targets['T2']:.5f}")

    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='yellow', width=1), name="EMA20"))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='cyan', width=2), name="EMA50"))
    fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=600)
    st.plotly_chart(fig, use_container_width=True)

# --- CURRENCY STRENGTH METER ---
st.sidebar.markdown("---")
st.sidebar.header("📊 Currency Strength (24h)")
@st.cache_data(ttl=300)
def get_strength():
    majors = {"USD": "DX-Y.NYB", "EUR": "EURUSD=X", "GBP": "GBPUSD=X", "JPY": "USDJPY=X", "AUD": "AUDUSD=X", "PHP": "PHP=X"}
    results = {}
    for name, sym in majors.items():
        try:
            data = yf.download(sym, period="2d", interval="1d", progress=False)
            if len(data) >= 2:
                change = ((data['Close'].iloc[-1] - data['Close'].iloc[-2]) / data['Close'].iloc[-2]) * 100
                if name in ["JPY", "PHP"]: change = -change
                results[name] = float(change)
        except: continue
    return results

strength_data = get_strength()
if strength_data:
    sorted_strength = dict(sorted(strength_data.items(), key=lambda x: x[1], reverse=True))
    for cur, val in sorted_strength.items():
        st.sidebar.markdown(f"**{cur}** ({val:+.2f}%)")
        st.sidebar.progress(max(0.0, min(1.0, (val + 2) / 4)))
