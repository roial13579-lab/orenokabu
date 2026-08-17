import streamlit as st
import pandas as pd
import yfinance as yf

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

# 全銘柄リストの作成
ALL_TICKERS = [ticker for tickers in SECTORS.values() for ticker in tickers]

# --- 株価取得ロジック（yfinanceで一括高速取得） ---
@st.cache_data(ttl=300)
def fetch_all_stocks():
    try:
        # 50銘柄を一括ダウンロード
        data = yf.download(ALL_TICKERS, period="5d", interval="1d", progress=False)["Close"]
        
        result = {}
        for ticker in ALL_TICKERS:
            if ticker in data.columns:
                series = data[ticker].dropna()
                if len(series) >= 2:
                    price = float(series.iloc[-1])
                    prev = float(series.iloc[-2])
                    change = round(((price - prev) / prev) * 100, 2)
                    is_us = not ticker.endswith(".T")
                    clean_code = ticker.replace(".T", "")
                    result[ticker] = {
                        "code": clean_code,
                        "price": price,
                        "change": change,
                        "is_us": is_us
                    }
            if ticker not in result:
                result[ticker] = {"code": ticker.replace(".T", ""), "price": 0.0, "change": 0.0, "is_us": False}
        return result
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return {}

# --- 更新ボタン ---
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🔄 最新データに更新", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# --- データ取得 ---
stock_data = fetch_all_stocks()

# --- 画面表示 ---
for sector_name, tickers in SECTORS.items():
    st.subheader(sector_name)
    cols = st.columns(len(tickers))
    changes = []
    
    for idx, ticker in enumerate(tickers):
        data = stock_data.get(ticker, {"code": ticker.replace(".T", ""), "price": 0.0, "change": 0.0, "is_us": False})
        changes.append(data["change"])
        
        unit = "$" if data["is_us"] else "¥"
        price_str = f"{unit}{data['price']:,.2f}" if data["is_us"] else f"{unit}{data['price']:,.0f}"
        
        with cols[idx]:
            st.metric(
                label=data["code"],
                value=price_str,
                delta=f"{data['change']:+.2f}%"
            )
            
    avg_change = sum(changes) / len(changes) if changes else 0.0
    st.caption(f"業界平均変動率: **{avg_change:+.2f}%**")
    st.divider()
