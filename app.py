import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="株式・業界分析アプリ", layout="wide")

# 10大業界の代表的な日本株・米国株リスト (各業界トップ10などの定義用)
TOP_COMPANIES_BY_SECTOR = {
    "情報通信・IT": [
        {"name": "トヨタ自動車", "symbol": "7203.T"},
        {"name": "ソニーグループ", "symbol": "6758.T"},
        {"name": "NTT", "symbol": "9432.T"},
        {"name": "ソフトバンクG", "symbol": "9984.T"},
        {"name": "Apple", "symbol": "AAPL"},
        {"name": "Microsoft", "symbol": "MSFT"},
        {"name": "NVIDIA", "symbol": "NVDA"},
        {"name": "Alphabet (Google)", "symbol": "GOOGL"},
        {"name": "Amazon", "symbol": "AMZN"},
        {"name": "Meta", "symbol": "META"},
    ],
    "金融・銀行": [
        {"name": "三菱UFJ FG", "symbol": "8306.T"},
        {"name": "三井住友 FG", "symbol": "8316.T"},
        {"name": "みずほ FG", "symbol": "8411.T"},
        {"name": "JPMorgan Chase", "symbol": "JPM"},
        {"name": "Bank of America", "symbol": "BAC"},
    ],
    # 必要に応じて他の業界を追加
}

# --- タブ設定 ---
tab1, tab2 = st.tabs(["📊 10大業界分析", "🔍 個別銘柄詳細"])

# ==========================================
# TAB 1: 10大業界分析（市況指標付き）
# ==========================================
with tab1:
    st.title("10大業界マップ・市場動向")

    # 隙間を活用して主要指標を表示
    col1, col2, col3 = st.columns(3)
    
    with col1:
        try:
            nk = yf.Ticker("^N225").history(period="2d")
            latest_nk = nk["Close"].iloc[-1]
            prev_nk = nk["Close"].iloc[-2]
            diff_nk = latest_nk - prev_nk
            st.metric("日経平均株価", f"{latest_nk:,.2f} 円", f"{diff_nk:+,.2f}")
        except Exception:
            st.metric("日経平均株価", "取得失敗", "-")

    with col2:
        try:
            usdjpy = yf.Ticker("JPY=X").history(period="2d")
            latest_fx = usdjpy["Close"].iloc[-1]
            prev_fx = usdjpy["Close"].iloc[-2]
            diff_fx = latest_fx - prev_fx
            st.metric("米ドル / 円", f"{latest_fx:.2f} 円", f"{diff_fx:+.2f}")
        except Exception:
            st.metric("米ドル / 円", "取得失敗", "-")

    with col3:
        st.info("💡 業界別チャートやマップをここに配置")

    st.markdown("---")
    st.subheader("業界別パフォーマンス一覧")
    # ここに10大業界のヒートマップや比較グラフを実装

# ==========================================
# TAB 2: 個別銘柄検索 (検索バーはここ限定)
# ==========================================
with tab2:
    st.title("個別銘柄検索 & 分析")

    # このタブ内のみに検索バーを設置
    query = st.text_input(
        "銘柄コードまたはティッカーを入力してください（日本株: 7203.T / 米国株: AAPL, NVDA 等）",
        value=""
    )

    if query:
        # 銘柄検索結果の表示領域
        st.subheader(f"検索結果: {query.upper()}")
        try:
            ticker = yf.Ticker(query)
            info = ticker.info
            hist = ticker.history(period="1mo")

            if not hist.empty:
                current_price = hist["Close"].iloc[-1]
                currency = info.get("currency", "USD")
                st.metric(f"{info.get('shortName', query.upper())} 株価", f"{current_price:,.2f} {currency}")
                st.line_chart(hist["Close"])
            else:
                st.warning("該当する銘柄データが見つかりませんでした。")
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

    else:
        # 検索前のトップページ：各業界のトップ10社を表示
        st.subheader("🏆 各業界の主要銘柄 (日本株・米国株)")
        st.caption("検索バーに未入力の際は、各業界の代表的な上位企業を表示しています。")

        for sector, companies in TOP_COMPANIES_BY_SECTOR.items():
            st.write(f"### {sector}")
            cols = st.columns(5)
            for idx, comp in enumerate(companies[:10]):
                with cols[idx % 5]:
                    st.write(f"**{comp['name']}**")
                    st.caption(f"コード: `{comp['symbol']}`")
