import streamlit as st
import requests
import re
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

# --- ページ基本設定 ---
st.set_page_config(
    page_title="俺の株ダッシュボード",
    page_icon="📈",
    layout="wide"
)

st.title("📈 10大業界 株価変動解析")

SECTORS = {
    "1.半導体": ["8035.T", "6857.T", "6146.T", "6920.T", "NVDA"],
    "2.重工防衛": ["7011.T", "7012.T", "7013.T", "6301.T", "6367.T"],
    "3.自動車": ["7203.T", "7267.T", "7270.T", "7201.T", "TSLA"],
    "4.大型金融": ["8306.T", "8316.T", "8411.T", "8604.T", "8766.T"],
    "5.エネ資源": ["1605.T", "5020.T", "5401.T", "4063.T", "XOM"],
    "6.海運物流": ["9101.T", "9104.T", "9107.T", "9020.T", "9143.T"],
    "7.メガテック": ["9984.T", "9432.T", "AAPL", "MSFT", "GOOGL"],
    "8.商社流通": ["8058.T", "8001.T", "8031.T", "8053.T", "3382.T"],
    "9.医薬バイオ": ["4502.T", "4519.T", "4568.T", "4503.T", "LLY"],
    "10.電気精密": ["6501.T", "6758.T", "6503.T", "7751.T", "6752.T"]
}

# --- 株価取得ロジック（キャッシュ機能付きで高速化） ---
@st.cache_data(ttl=300) # 5分間データをキャッシュしてYahooへの過剰アクセスを防ぐ
def fetch_stock(ticker):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if ticker.endswith(".T"):
        clean_code = ticker.replace(".T", "")
        url = f"https://finance.yahoo.co.jp/quote/{clean_code}.T"
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                match = re.search(r"(\d{1,3}(?:,\d{3})*|\d+)\s*[-+]\d+(?:\,\d+)*(?:\.\d+)?\s*([+-]?\d+\.\d+)%", soup.get_text())
                if match:
                    return {"code": clean_code, "price": float(match.group(1).replace(",", "")), "change": float(match.group(2)), "is_us": False}
        except Exception: pass
    else:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d"
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                meta = res.json()["chart"]["result"][0]["meta"]
                price = float(meta.get("regularMarketPrice", 0.0))
                prev = float(meta.get("chartPreviousClose", price))
                if price > 0 and prev > 0:
                    change = round(((price - prev) / prev) * 100, 2)
                    return {"code": ticker, "price": price, "change": change, "is_us": True}
        except Exception: pass
    return {"code": ticker, "price": 0.0, "change": 0.0, "is_us": False}

# --- 更新ボタン ---
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🔄 最新データに更新", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# --- 画面表示 ---
for sector_name, tickers in SECTORS.items():
    st.subheader(sector_name)
    
    cols = st.columns(len(tickers))
    changes = []
    
    for idx, ticker in enumerate(tickers):
        data = fetch_stock(ticker)
        changes.append(data["change"])
        
        unit = "$" if data["is_us"] else "¥"
        price_str = f"{unit}{data['price']:,.2f}" if data["is_us"] else f"{unit}{data['price']:,.0f}"
        
        with cols[idx]:
            st.metric(
                label=data["code"],
                value=price_str,
                delta=f"{data['change']:+.2f}%"
            )
            
    avg_change = float(np.mean(changes)) if changes else 0.0
    st.caption(f"業界平均変動率: **{avg_change:+.2f}%**")
    st.divider()
