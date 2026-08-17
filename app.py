import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- ページ設定 ---
st.set_page_config(
    page_title="俺の株ダッシュボード PRO",
    page_icon="📈",
    layout="wide"
)

st.title("📈 10大業界 株価・テクニカル・板情報・急騰スクリーニング PRO")

# --- 10大業界＆会社名マップ ---
SECTOR_COMPANIES = {
    "1.半導体": {
        "8035.T": "東京エレクトロン", "6857.T": "アドバンテスト",
        "6146.T": "ディスコ", "6920.T": "レーザーテック", "NVDA": "NVIDIA"
    },
    "2.重工防衛": {
        "7011.T": "三菱重工業", "7012.T": "川崎重工業",
        "7013.T": "IHI", "6301.T": "小松製作所", "6367.T": "ダイキン工業"
    },
    "3.自動車": {
        "7203.T": "トヨタ自動車", "7267.T": "ホンダ",
        "7270.T": "SUBARU", "7201.T": "日産自動車", "TSLA": "Tesla"
    },
    "4.大型金融": {
        "8306.T": "三菱UFJ FG", "8316.T": "三井住友 FG",
        "8411.T": "みずほ FG", "8604.T": "野村 HD", "8766.T": "東京海上 HD"
    },
    "5.エネ資源": {
        "1605.T": "INPEX", "5020.T": "ENEOS HD",
        "5401.T": "日本製鉄", "4063.T": "信越化学工業", "XOM": "ExxonMobil"
    },
    "6.海運物流": {
        "9101.T": "日本郵船", "9104.T": "商船三井",
        "9107.T": "川崎汽船", "9020.T": "JR東日本", "9143.T": "SGホールディングス"
    },
    "7.メガテック": {
        "9984.T": "ソフトバンクG", "9432.T": "NTT",
        "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet"
    },
    "8.商社流通": {
        "8058.T": "三菱商事", "8001.T": "伊藤忠商事",
        "8031.T": "三井物産", "8053.T": "住友商事", "3382.T": "セブン&アイ HD"
    },
    "9.医薬バイオ": {
        "4502.T": "武田薬品工業", "4519.T": "中外製薬",
        "4568.T": "第一三共", "4503.T": "アステラス製薬", "LLY": "Eli Lilly"
    },
    "10.電気精密": {
        "6501.T": "日立製作所", "6758.T": "ソニーグループ",
        "6503.T": "三菱電機", "7751.T": "キヤノン", "6752.T": "パナソニック HD"
    }
}

# 業界別最新イベント・変動要因
SECTOR_EVENTS = {
    "1.半導体": "米国半導体株の調整影響、次世代AIチップ需要拡大、為替ドルの動き",
    "2.重工防衛": "防衛予算拡充方針、航空宇宙需要増、インフラ需要",
    "3.自動車": "EV需要一巡・PHEVシフト、米国関税政策論議、円安効果",
    "4.大型金融": "日銀利上げ観測・イールドカーブ変化、自社株買い発表",
    "5.エネ資源": "原油価格（WTI）変動、中東情勢、脱炭素投資動向",
    "6.海運物流": "コンテナ船運賃指数（CCFI）動向、紅海情勢、国内物流2024年問題影響",
    "7.メガテック": "生成AIマネタイズ動向、米大型IT決算発表、自己株式取得",
    "8.商社流通": "バフェット効果持続、資源高還元、海外事業M&A",
    "9.医薬バイオ": "新薬パイプライン治験結果、米国薬価抑制政策、特許切れ影響",
    "10.電気精密": "データセンター需要拡大、事業ポートフォリオ再編、円安メリット"
}

# --- テクニカル分析指標の計算関数 ---
def calculate_indicators(df):
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA25'] = df['Close'].rolling(window=25).mean()
    df['SMA75'] = df['Close'].rolling(window=75).mean()
    
    # ボリンジャーバンド (20, 2σ)
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['Upper_Band'] = df['SMA20'] + (df['STD20'] * 2)
    df['Lower_Band'] = df['SMA20'] - (df['STD20'] * 2)
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 下ひげ（ピンバー）判定
    body = abs(df['Close'] - df['Open'])
    lower_shadow = np.minimum(df['Open'], df['Close']) - df['Low']
    df['Pinbar'] = lower_shadow >= (2 * body)
    
    # 出来高倍率（過去20日平均比）
    df['Vol_Ratio'] = df['Volume'] / df['Volume'].rolling(window=20).mean()
    
    return df

# --- データ一括取得 ---
ALL_TICKERS = [t for sub in SECTOR_COMPANIES.values() for t in sub.keys()]

@st.cache_data(ttl=300)
def fetch_data():
    data = yf.download(ALL_TICKERS, period="1y", interval="1d", group_by="ticker", progress=False)
    return data

data_dict = fetch_data()

# --- サイドバー：機能切り替え ---
mode = st.sidebar.radio("表示モード切り替え", ["📊 業界一覧ダッシュボード", "📈 個別銘柄テクニカル＆板情報", "🚀 テンバガー（急騰）候補スクリーニング"])

# ==========================================
# モード1: 業界一覧ダッシュボード
# ==========================================
if mode == "📊 業界一覧ダッシュボード":
    st.header("📊 業界別リアルタイム市況＆背景イベント")
    
    for sector_name, companies in SECTOR_COMPANIES.items():
        st.subheader(sector_name)
        st.info(f"💡 **注目イベント・変動要因**: {SECTOR_EVENTS[sector_name]}")
        
        cols = st.columns(len(companies))
        changes = []
        
        for idx, (ticker, name) in enumerate(companies.items()):
            try:
                df = data_dict[ticker].dropna()
                price = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                change = ((price - prev) / prev) * 100
                changes.append(change)
                is_us = not ticker.endswith(".T")
                unit = "$" if is_us else "¥"
                fmt = f"{unit}{price:,.2f}" if is_us else f"{unit}{price:,.0f}"
                
                with cols[idx]:
                    st.metric(
                        label=f"{name} ({ticker.replace('.T', '')})",
                        value=fmt,
                        delta=f"{change:+.2f}%"
                    )
            except Exception:
                with cols[idx]:
                    st.write(f"取得失敗: {name}")
                    
        avg = sum(changes) / len(changes) if changes else 0.0
        st.caption(f"業界平均変動率: **{avg:+.2f}%**")
        st.divider()

# ==========================================
# モード2: 個別銘柄テクニカル＆板情報
# ==========================================
elif mode == "📈 個別銘柄テクニカル＆板情報":
    st.header("📈 詳細テクニカル分析＆気配板情報")
    
    selected_ticker = st.selectbox("銘柄を選択", ALL_TICKERS, format_func=lambda x: f"{x} - " + [v[x] for k, v in SECTOR_COMPANIES.items() if x in v][0])
    
    df = data_dict[selected_ticker].dropna()
    df = calculate_indicators(df)
    
    comp_name = [v[selected_ticker] for k, v in SECTOR_COMPANIES.items() if selected_ticker in v][0]
    st.subheader(f"{comp_name} ({selected_ticker}) チャート解析")
    
    # Plotlyでローソク足＋移動平均線＋ボリンジャーバンド＋出来高＋RSI作成
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    
    # ローソク足
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='ローソク足'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA5'], name='5日線(短期)', line=dict(color='orange', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA25'], name='25日線(中期)', line=dict(color='blue', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA75'], name='75日線(長期)', line=dict(color='purple', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Upper_Band'], name='+2σ', line=dict(color='gray', dash='dash')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Lower_Band'], name='-2σ', line=dict(color='gray', dash='dash')), row=1, col=1)
    
    # 出来高
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='出来高', marker_color='cadetblue'), row=2, col=1)
    
    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI(14)', line=dict(color='green')), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="blue", row=3, col=1)
    
    fig.update_layout(height=700, xaxis_rangeslider_visible=False, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)
    
    # テクニカル分析所見
    latest = df.iloc[-1]
    st.markdown("### 🔍 自動テクニカル判定")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("**パーフェクトオーダー (トレンド強さ)**")
        if latest['SMA5'] > latest['SMA25'] > latest['SMA75']:
            st.success("🔥 上昇パーフェクトオーダー形成中（超強気）")
        elif latest['SMA5'] < latest['SMA25'] < latest['SMA75']:
            st.error("❄️ 下降パーフェクトオーダー形成中（弱気）")
        else:
            st.info("🔄 レンジ・転換期")
            
    with c2:
        st.markdown("**RSI 買われすぎ/売られすぎ**")
        if latest['RSI'] >= 70:
            st.warning(f"⚠️ RSI: {latest['RSI']:.1f}% (買われすぎ警戒)")
        elif latest['RSI'] <= 30:
            st.success(f"🎯 RSI: {latest['RSI']:.1f}% (売られすぎ・反発狙い)")
        else:
            st.write(f"RSI: {latest['RSI']:.1f}% (中立領域)")
            
    with c3:
        st.markdown("**下ひげ（底打ちサイン）判定**")
        if latest['Pinbar']:
            st.success("🎯 最新ローソク足で下ひげ（ピンバー）検出！底打ち反発の可能性あり")
        else:
            st.write("検出なし")

    # 板情報（リアルタイム板のシミュレーション表示枠）
    st.markdown("### 📋 板情報（気配値・歩み値）")
    st.caption("※証券会社API連携時はここにリアルタイム板が直接反映されます")
    
    last_price = int(latest['Close']) if not selected_ticker.endswith("NVDA") and not selected_ticker.endswith("AAPL") else round(latest['Close'], 2)
    
    board_data = {
        "売気配数量": [1200, 3500, 800, 2300, 1500, "", "", "", "", ""],
        "気配株価": [last_price+5, last_price+4, last_price+3, last_price+2, last_price+1, last_price, last_price-1, last_price-2, last_price-3, last_price-4],
        "買気配数量": ["", "", "", "", "", 4500, 1800, 2900, 5100, 1200]
    }
    st.table(pd.DataFrame(board_data))

# ==========================================
# モード3: テンバガー（急騰）候補スクリーニング
# ==========================================
elif mode == "🚀 テンバガー（急騰）候補スクリーニング":
    st.header("🚀 急騰（テンバガー）候補スクリーニング")
    st.markdown("過去の大化け株（テンバガー）に共通する**「出来高急増」「下ひげ底打ち」「移動平均線ゴールデンクロス」「RSI売られすぎからの反発」**をもとにスコアリングしています。")
    
    results = []
    
    for ticker in ALL_TICKERS:
        try:
            df = data_dict[ticker].dropna()
            if len(df) < 75: continue
            df = calculate_indicators(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            comp_name = [v[ticker] for k, v in SECTOR_COMPANIES.items() if ticker in v][0]
            
            score = 0
            reasons = []
            
            # 1. 出来高急増（通常比2倍以上）
            if latest['Vol_Ratio'] >= 2.0:
                score += 30
                reasons.append(f"出来高急増({latest['Vol_Ratio']:.1f}倍)")
                
            # 2. 下ひげピンバー検出
            if latest['Pinbar']:
                score += 25
                reasons.append("下ひげピンバー(底打ち)")
                
            # 3. ゴールデンクロス（5日線が25日線を上抜け）
            if prev['SMA5'] <= prev['SMA25'] and latest['SMA5'] > latest['SMA25']:
                score += 25
                reasons.append("5日線×25日線 GC")
                
            # 4. RSI売られすぎからの反発
            if prev['RSI'] < 35 and latest['RSI'] > prev['RSI']:
                score += 20
                reasons.append(f"RSI底打ち反発({latest['RSI']:.1f}%)")
                
            if score > 0:
                results.append({
                    "コード": ticker.replace(".T", ""),
                    "会社名": comp_name,
                    "現在株価": f"{latest['Close']:,.1f}",
                    "急騰スコア": score,
                    "検出シグナル": " / ".join(reasons)
                })
        except Exception:
            continue
            
    res_df = pd.DataFrame(results)
    if not res_df.empty:
        res_df = res_df.sort_values(by="急騰スコア", ascending=False).reset_index(drop=True)
        st.dataframe(res_df, use_container_width=True)
    else:
        st.info("現在、急騰シグナルに該当する銘柄はありません。")
