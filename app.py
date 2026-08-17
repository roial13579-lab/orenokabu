import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- ページ設定 ---
st.set_page_config(
    page_title="俺の株ダッシュボード PRO+",
    page_icon="📈",
    layout="wide"
)

st.title("📈 10大業界 株価・テクニカル・テンバガー分析 PRO+")

# --- 10大業界：トップ5社 ＆ 長期的期待5社 ---
SECTOR_DATA = {
    "1.半導体": {
        "top5": {"8035.T": "東京エレクトロン", "6857.T": "アドバンテスト", "6146.T": "ディスコ", "6920.T": "レーザーテック", "NVDA": "NVIDIA"},
        "future5": {"6723.T": "ルネサス", "7735.T": "SCREEN HD", "6758.T": "ソニーグループ", "ASML": "ASML", "TSM": "TSMC"},
        "event": "AI需要加速、次世代プロセス競争、為替ドルの影響"
    },
    "2.重工防衛": {
        "top5": {"7011.T": "三菱重工業", "7012.T": "川崎重工業", "7013.T": "IHI", "6301.T": "小松製作所", "6367.T": "ダイキン工業"},
        "future5": {"6208.T": "石川製作所", "6203.T": "豊和工業", "7003.T": "三井E&S", "LMT": "Lockheed Martin", "RTX": "RTX"},
        "event": "防衛費増額政策、宇宙関連需要、インフラ更新投資"
    },
    "3.自動車": {
        "top5": {"7203.T": "トヨタ自動車", "7267.T": "ホンダ", "7270.T": "SUBARU", "7201.T": "日産自動車", "TSLA": "Tesla"},
        "future5": {"7269.T": "スズキ", "7202.T": "いすゞ自動車", "6594.T": "ニデック", "RACE": "Ferrari", "BYDDF": "BYD"},
        "event": "PHEV・ハイブリッド再評価、自動運転開発、円安メリット"
    },
    "4.大型金融": {
        "top5": {"8306.T": "三菱UFJ FG", "8316.T": "三井住友 FG", "8411.T": "みずほ FG", "8604.T": "野村 HD", "8766.T": "東京海上 HD"},
        "future5": {"8308.T": "りそな HD", "8309.T": "三井住友トラスト", "8630.T": "SOMPO HD", "8725.T": "MS&AD", "JPM": "JPMorgan Chase"},
        "event": "日銀金利引き上げ観測、イールドカーブ変化、株主還元拡大"
    },
    "5.エネ資源": {
        "top5": {"1605.T": "INPEX", "5020.T": "ENEOS HD", "5401.T": "日本製鉄", "4063.T": "信越化学工業", "XOM": "ExxonMobil"},
        "future5": {"1518.T": "三井松島 HD", "5019.T": "出光興産", "5713.T": "住友金属鉱山", "CVX": "Chevron", "SHEL": "Shell"},
        "event": "WTI原油価格動向、地政学リスク、脱炭素/GX投資"
    }
}

ALL_TICKERS = {}
for s, v in SECTOR_DATA.items():
    ALL_TICKERS.update(v["top5"])
    ALL_TICKERS.update(v["future5"])

def calculate_indicators(df):
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA25'] = df['Close'].rolling(window=25).mean()
    df['SMA75'] = df['Close'].rolling(window=75).mean()
    
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['Upper_Band'] = df['SMA20'] + (df['STD20'] * 2)
    df['Lower_Band'] = df['SMA20'] - (df['STD20'] * 2)
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    body = abs(df['Close'] - df['Open'])
    lower_shadow = np.minimum(df['Open'], df['Close']) - df['Low']
    df['Pinbar'] = lower_shadow >= (2 * body)
    df['Vol_Ratio'] = df['Volume'] / df['Volume'].rolling(window=20).mean()
    return df

@st.cache_data(ttl=300)
def fetch_data():
    return yf.download(list(ALL_TICKERS.keys()), period="1y", interval="1d", group_by="ticker", progress=False)

data_dict = fetch_data()

# --- セッション状態の初期化 ---
if "target_ticker" not in st.session_state:
    st.session_state.target_ticker = "8035.T"
if "current_mode" not in st.session_state:
    st.session_state.current_mode = "📊 業界一覧（トップ5 vs 期待5）"

# 銘柄選択・遷移用関数
def go_to_detail(ticker):
    st.session_state.target_ticker = ticker
    st.session_state.current_mode = "📈 個別銘柄詳細＆売買アドバイス"

# --- サイドバーナビゲーション ---
mode = st.sidebar.radio(
    "機能切り替え",
    ["📊 業界一覧（トップ5 vs 期待5）", "📈 個別銘柄詳細＆売買アドバイス", "🚀 テンバガー（急騰）候補"],
    key="current_mode"
)

# ==========================================
# 📊 業界一覧（トップ5 vs 期待5）
# ==========================================
if mode == "📊 業界一覧（トップ5 vs 期待5）":
    st.header("📊 業界別：トップ5社 vs 長期期待5社")
    st.caption("💡 銘柄のボタンを押すと、直接チャート・分析画面へ遷移します。")
    
    for sector_name, info in SECTOR_DATA.items():
        st.subheader(f"🏢 {sector_name}")
        st.info(f"💡 **注目イベント・変動要因**: {info['event']}")
        
        tab1, tab2 = st.tabs(["🏆 業界トップ5社", "🚀 長期的期待5社"])
        
        for tab, comp_dict in zip([tab1, tab2], [info["top5"], info["future5"]]):
            with tab:
                cols = st.columns(len(comp_dict))
                for idx, (ticker, name) in enumerate(comp_dict.items()):
                    try:
                        df = data_dict[ticker].dropna()
                        latest = df.iloc[-1]
                        prev = df.iloc[-2]
                        change = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
                        is_us = not ticker.endswith(".T")
                        unit = "$" if is_us else "¥"
                        
                        with cols[idx]:
                            st.metric(
                                label=f"{name} ({ticker.replace('.T','')})",
                                value=f"{unit}{latest['Close']:,.1f}",
                                delta=f"{change:+.2f}%"
                            )
                            st.button(f"📈 分析を見る", key=f"btn_sec_{ticker}", on_click=go_to_detail, args=(ticker,))
                    except Exception:
                        with cols[idx]:
                            st.write(f"取得失敗: {name}")

# ==========================================
# 📈 個別銘柄詳細＆売買アドバイス
# ==========================================
elif mode == "📈 個別銘柄詳細＆売買アドバイス":
    st.header("📈 個別銘柄テクニカル＆当日の株価詳細")
    
    selected_ticker = st.selectbox(
        "銘柄を選択してください",
        options=list(ALL_TICKERS.keys()),
        index=list(ALL_TICKERS.keys()).index(st.session_state.target_ticker) if st.session_state.target_ticker in ALL_TICKERS else 0,
        format_func=lambda x: f"{x.replace('.T', '')} - {ALL_TICKERS.get(x, '')}"
    )
    st.session_state.target_ticker = selected_ticker
    
    df = data_dict[selected_ticker].dropna()
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    comp_name = ALL_TICKERS.get(selected_ticker, "")
    is_us = not selected_ticker.endswith(".T")
    unit = "$" if is_us else "¥"
    
    st.markdown(f"## **{comp_name} ({selected_ticker})**")
    
    # --- 当日の詳細株価 ---
    st.markdown("### 💵 当日（最新）の株価詳細")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("現在値 (終値)", f"{unit}{latest['Close']:,.1f}", f"{((latest['Close']-prev['Close'])/prev['Close'])*100:+.2f}%")
    m2.metric("始値 (Open)", f"{unit}{latest['Open']:,.1f}")
    m3.metric("高値 (High)", f"{unit}{latest['High']:,.1f}")
    m4.metric("安値 (Low)", f"{unit}{latest['Low']:,.1f}")
    m5.metric("前日終値", f"{unit}{prev['Close']:,.1f}")
    
    # --- チャート表示（ズーム・スライダー強化） ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='ローソク足'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA5'], name='5日線(短期)', line=dict(color='orange', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA25'], name='25日線(中期)', line=dict(color='blue', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA75'], name='75日線(長期)', line=dict(color='purple', width=1)), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='出来高', marker_color='cadetblue'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI(14)', line=dict(color='green')), row=3, col=1)
    
    # 拡大・レンジ切替ボタンの追加
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1ヶ月", step="month", stepmode="backward"),
                dict(count=3, label="3ヶ月", step="month", stepmode="backward"),
                dict(count=6, label="6ヶ月", step="month", stepmode="backward"),
                dict(step="all", label="全期間")
            ])
        ),
        rangeslider=dict(visible=True),  # チャート下部のスライダーで自由な拡大縮小が可能
        type="date"
    )
    fig.update_layout(height=700, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("🔍 **拡大方法**: チャート上のドラッグ、マウスホイール、下部スライダー、または左上の「1ヶ月/3ヶ月」ボタンで拡大表示できます。")
    
    # --- 短期・中期・長期 売買アドバイス ---
    st.markdown("### 🎯 期間別テクニカル判定＆買いアドバイス")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("⏱️ 短期（数日〜1週間）")
        if latest['Pinbar'] or latest['RSI'] < 30:
            st.success("🟢 **買い推奨（押し目買い/反発狙い）**")
            st.caption("**理由**: 下ひげピンバー検出、またはRSI30以下で短期的売られすぎ。リバウンド狙いの買い好機。")
        elif latest['Close'] > latest['SMA5']:
            st.info("🟡 **様子見 / 押し目待ち**")
            st.caption("**理由**: 短期5日線の上で上昇トレンド中だが、やや買われすぎ領域に接近。")
        else:
            st.error("🔴 **静観 / 売り検討**")
            st.caption("**理由**: 5日線を下回り短期弱気モード。")

    with c2:
        st.subheader("📅 中期（数週間〜数ヶ月）")
        if latest['SMA5'] > latest['SMA25'] and prev['SMA5'] <= prev['SMA25']:
            st.success("🟢 **強力買い（ゴールデンクロス発生）**")
            st.caption("**理由**: 5日移動平均線が25日線を明確に上抜け。トレンド転換の買いサイン。")
        elif latest['Close'] > latest['SMA25']:
            st.success("🟢 **継続保有 / 買い**")
            st.caption("**理由**: 25日移動平均線の上で推移しており中期上昇トレンドを維持。")
        else:
            st.error("🔴 **静観（トレンド悪化）**")
            st.caption("**理由**: 25日線を割り込んでおり、中期的な調整リスクあり。")

    with c3:
        st.subheader("🏛️ 長期（半年〜数年）")
        if latest['SMA5'] > latest['SMA25'] > latest['SMA75']:
            st.success("🟢 **買い推奨（パーフェクトオーダー）**")
            st.caption("**理由**: 5日>25日>75日の完全上昇配列。長期成長ストーリーに乗る買い場。")
        elif latest['Close'] > latest['SMA75']:
            st.info("🟡 **押し目買い検討**")
            st.caption("**理由**: 75日線が下支え（サポート）として機能中。")
        else:
            st.error("🔴 **見送り**")
            st.caption("**理由**: 長期トレンドが下降傾向。買いは慎重に。")

# ==========================================
# 🚀 テンバガー（急騰）候補
# ==========================================
elif mode == "🚀 テンバガー（急騰）候補":
    st.header("🚀 テンバガー（急騰）候補スクリーニング")
    st.caption("シグナルを検出したすべての銘柄を表示しています。「📈 分析を見る」ボタンを押すと即座に詳細へ遷移します。")
    
    results = []
    for ticker, name in ALL_TICKERS.items():
        try:
            df = data_dict[ticker].dropna()
            if len(df) < 75: continue
            df = calculate_indicators(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            score = 0
            reasons = []
            actions = []
            
            if latest['Vol_Ratio'] >= 2.0:
                score += 30
                reasons.append(f"出来高急増({latest['Vol_Ratio']:.1f}倍)")
                actions.append("大口資金流入。打診買い検討")
                
            if latest['Pinbar']:
                score += 25
                reasons.append("下ひげ(底打ち)")
                actions.append("反発サイン。指値買い準備")
                
            if prev['SMA5'] <= prev['SMA25'] and latest['SMA5'] > latest['SMA25']:
                score += 25
                reasons.append("5日線×25日線 GC")
                actions.append("上昇開始。順張り追加")
                
            if prev['RSI'] < 35 and latest['RSI'] > prev['RSI']:
                score += 20
                reasons.append(f"RSI反発({latest['RSI']:.1f}%)")
                actions.append("セリクラ通過。エントリー検討")
                
            if score > 0:
                results.append({
                    "ticker": ticker,
                    "code": ticker.replace(".T", ""),
                    "name": name,
                    "price": f"{latest['Close']:,.1f}",
                    "score": score,
                    "reasons": " / ".join(reasons),
                    "actions": " / ".join(actions)
                })
        except Exception:
            continue
            
    if results:
        results = sorted(results, key=lambda x: x['score'], reverse=True)
        st.write(f"**該当件数: 全 {len(results)} 件**")
        
        # ボタン付きカード形式で件数制限なしで表示
        for res in results:
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 3, 3, 1.5])
                col1.markdown(f"**{res['code']}**\n{res['name']}")
                col2.markdown(f"**価格**: {res['price']}\n**スコア**: {res['score']}")
                col3.markdown(f"**シグナル**:\n{res['reasons']}")
                col4.markdown(f"**推奨アクション**:\n{res['actions']}")
                with col5:
                    st.button("📈 分析を見る", key=f"btn_tb_{res['ticker']}", on_click=go_to_detail, args=(res['ticker'],))
                st.divider()
    else:
        st.info("現在、急騰シグナル条件に合致する銘柄はありません。")
