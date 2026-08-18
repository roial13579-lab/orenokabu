import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- ページ基本設定 ---
st.set_page_config(
    page_title="株ダッシュボード PRO+",
    page_icon="📈",
    layout="wide"
)

# --- 10大業界データ・背景・イベント・トップ10銘柄 ---
SECTOR_DATA = {
    "半導体": {
        "bg": "生成AIマーケットの爆発的拡大とデータセンター投資の加速。政府の国内製造拠点への手厚い補助金政策も強力な追い風。",
        "top10": {
            "8035.T": "東京エレクトロン", "6857.T": "アドバンテスト", "6146.T": "ディスコ", "6920.T": "レーザーテック", "NVDA": "NVIDIA",
            "6723.T": "ルネサス", "7735.T": "SCREEN HD", "6758.T": "ソニーグループ", "ASML": "ASML", "TSM": "TSMC"
        },
        "event": "次世代プロセス微細化競合、米国対中輸出規制の動向、主要AI・ビッグテック企業の設備投資計画"
    },
    "重工防衛": {
        "bg": "地政学リスクの高まりに伴う国家防衛費増額政策。宇宙開発や次世代インフラ更新需要の急増。",
        "top10": {
            "7011.T": "三菱重工業", "7012.T": "川崎重工業", "7013.T": "IHI", "6301.T": "小松製作所", "6367.T": "ダイキン工業",
            "6208.T": "石川製作所", "6203.T": "豊和工業", "7003.T": "三井E&S", "LMT": "Lockheed Martin", "RTX": "RTX"
        },
        "event": "防衛予算閣議決定、装備品輸出制限の緩和議論、宇宙航空関連の新規ナショナルプロジェクト発足"
    },
    "自動車": {
        "bg": "EV急拡大の一巡に伴うハイブリッド・PHEV車の再評価。円安による輸出利益の底上げとSDV化の加速。",
        "top10": {
            "7203.T": "トヨタ自動車", "7267.T": "ホンダ", "7270.T": "SUBARU", "7201.T": "日産自動車", "TSLA": "Tesla",
            "7269.T": "スズキ", "7202.T": "いすゞ自動車", "6594.T": "ニデック", "RACE": "Ferrari", "BYDDF": "BYD"
        },
        "event": "為替レート変動、新興国市場でのEV普及ペース、次世代電池の量産ロードマップ"
    },
    "大型金融": {
        "bg": "日銀の金利引き上げ局面における利ざや改善期待。東証改革に伴う大規模な自社株買い・増配の定着。",
        "top10": {
            "8306.T": "三菱UFJ FG", "8316.T": "三井住友 FG", "8411.T": "みずほ FG", "8604.T": "野村 HD", "8766.T": "東京海上 HD",
            "8308.T": "りそな HD", "8309.T": "三井住友トラスト", "8630.T": "SOMPO HD", "8725.T": "MS&AD", "JPM": "JPMorgan Chase"
        },
        "event": "日銀金融政策決定会合の金利方針、イールドカーブ長短金利の動き、政策保有株の売却進捗状況"
    },
    "エネ資源": {
        "bg": "世界的なインフレ懸念と資源供給制限リスク。脱炭素（GX）投資と従来型エネルギーの収益最大化の併走。",
        "top10": {
            "1605.T": "INPEX", "5020.T": "ENEOS HD", "5401.T": "日本製鉄", "4063.T": "信越化学工業", "XOM": "ExxonMobil",
            "1518.T": "三井松島 HD", "5019.T": "出光興産", "5713.T": "住友金属鉱山", "CVX": "Chevron", "SHEL": "Shell"
        },
        "event": "OPEC+の生産調整決定、WTI原油/LNG市場価格の乱高下、GX経済移行債の利活用展開"
    },
    "IT・通信": {
        "bg": "DX需要の定着とクラウド移行。通信料金改定の一巡と5G/6Gインフラ投資。",
        "top10": {
            "9432.T": "NTT", "9433.T": "KDDI", "9984.T": "ソフトバンクグループ", "4755.T": "楽天グループ", "9434.T": "ソフトバンク",
            "MSFT": "Microsoft", "GOOGL": "Alphabet", "AAPL": "Apple", "ORCL": "Oracle", "ACN": "Accenture"
        },
        "event": "AIソリューション導入件数、ARPU推移、自社株買い等の株主還元策"
    },
    "医薬品": {
        "bg": "特許切れを克服するバイオ医薬品やmRNA技術へのシフト。世界的な高齢化に伴う医療需要の増大。",
        "top10": {
            "4502.T": "武田薬品工業", "4568.T": "第一三共", "4519.T": "中外製薬", "4503.T": "アステラス製薬", "4523.T": "エーザイ",
            "LLY": "Eli Lilly", "NVO": "Novo Nordisk", "PFE": "Pfizer", "JNJ": "Johnson & Johnson", "MRK": "Merck"
        },
        "event": "新薬パイプラインの治験成否、肥満症薬等の世界的販売拡大、薬価改定の影響"
    },
    "大手商社": {
        "bg": "バークシャー投資で世界的人気。資源利権と非資源事業の分散収益モデル。",
        "top10": {
            "8058.T": "三菱商事", "8001.T": "伊藤忠商事", "8031.T": "三井物産", "8015.T": "豊田通商", "8002.T": "丸紅",
            "2768.T": "双日", "8053.T": "住友商事", "8020.T": "兼松", "BRK-B": "Berkshire Hathaway", "8028.T": "ユニゾHD"
        },
        "event": "累進配当の維持・拡充、海外大型案件のM&A動向、金属・エネルギー市場価格"
    },
    "不動産": {
        "bg": "都心再開発事業による賃料水準の上昇とインバウンド需要に伴うホテル事業の好調。金利上昇局面での選別投資。",
        "top10": {
            "8801.T": "三井不動産", "8802.T": "三菱地所", "8830.T": "住友不動産", "3289.T": "東急不動産HD", "8804.T": "東京建物",
            "PLD": "Prologis", "AMT": "American Tower", "EQIX": "Equinix", "SPG": "Simon Property", "O": "Realty Income"
        },
        "event": "都心オフィス空室率推移、地価公示価格の変動、借入金利（長期金利）の上昇ペース"
    },
    "消費・小売": {
        "bg": "訪日外国人客の消費拡大と価格転嫁定着による粗利益率の向上。",
        "top10": {
            "9983.T": "ファーストリテイリング", "3382.T": "セブン&アイHD", "8267.T": "イオン", "7532.T": "パン・パシフィックHD", "2681.T": "ゲオHD",
            "WMT": "Walmart", "COST": "Costco", "PG": "Procter & Gamble", "KO": "Coca-Cola", "NKE": "Nike"
        },
        "event": "月次売上高の推移、インバウンド免税売上額、海外店舗の出店・伸び率"
    }
}

US_POPULAR_10 = {
    "NVDA": "NVIDIA", "AAPL": "Apple", "MSFT": "Microsoft", "AMZN": "Amazon", "GOOGL": "Alphabet",
    "META": "Meta Platforms", "TSLA": "Tesla", "AVGO": "Broadcom", "LLY": "Eli Lilly", "BRK-B": "Berkshire Hathaway"
}

ALL_TICKERS = {}
for s, v in SECTOR_DATA.items():
    ALL_TICKERS.update(v["top10"])
ALL_TICKERS.update(US_POPULAR_10)

def calculate_indicators(df):
    """テクニカル指標の計算（MultiIndexや欠損に安全に対応）"""
    df = df.copy()
    
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
    
    vol_sma20 = df['Volume'].rolling(window=20).mean()
    df['Vol_Ratio'] = np.where(vol_sma20 > 0, df['Volume'] / vol_sma20, 0)
    return df

@st.cache_data(ttl=600)
def fetch_data():
    all_symbols = list(ALL_TICKERS.keys()) + ["^N225", "JPY=X"]
    return yf.download(all_symbols, period="1y", interval="1d", group_by="ticker", progress=False)

def get_ticker_df(raw_data, ticker):
    """MultiIndex構造から安全に特定銘柄のデータフレームを抽出する関数"""
    try:
        if ticker in raw_data.columns.levels[0]:
            df = raw_data[ticker].copy().dropna(subset=['Close'])
            return df
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_info_data(ticker):
    try:
        t = yf.Ticker(ticker)
        return t.info
    except Exception:
        return {}

data_dict = fetch_data()

# --- セッション状態 ---
if "target_ticker" not in st.session_state:
    st.session_state.target_ticker = ""

NAV_MODES = ["📊 10大業界＆米国株トップ10", "📈 個別銘柄詳細＆深掘り分析", "🚀 テンバガー（急騰）候補"]
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = NAV_MODES[0]

def select_ticker(ticker):
    st.session_state.target_ticker = ticker
    st.session_state.selected_mode = "📈 個別銘柄詳細＆深掘り分析"

def clear_ticker():
    st.session_state.target_ticker = ""

# サイドバーナビゲーション
current_mode_idx = NAV_MODES.index(st.session_state.selected_mode) if st.session_state.selected_mode in NAV_MODES else 0
mode = st.sidebar.radio(
    "機能選択",
    options=NAV_MODES,
    index=current_mode_idx,
    key="nav_radio"
)
st.session_state.selected_mode = mode

# 業界別「平均値動き額（絶対値）」の算出・ランキング化
sector_movement = {}
for s_name, s_data in SECTOR_DATA.items():
    diffs = []
    for t_code in s_data["top10"].keys():
        df = get_ticker_df(data_dict, t_code)
        if len(df) >= 2:
            diff = abs(df['Close'].iloc[-1] - df['Close'].iloc[-2])
            diffs.append(diff)
    sector_movement[s_name] = np.mean(diffs) if diffs else 0

# 金額変動の大きい順に業界をソート
sorted_sectors = sorted(SECTOR_DATA.keys(), key=lambda x: sector_movement.get(x, 0), reverse=True)

# ==========================================
# 📊 10大業界＆米国株トップ10
# ==========================================
if mode == "📊 10大業界＆米国株トップ10":
    st.title("📊 10大業界マップ・市場動向")
    st.caption("※業界タブは「本日市場で動いた金額の大きさ（平均変動幅）」が大きい順に自動並び替えされています。")
    
    col_m1, col_m2, col_m3 = st.columns(3)
    
    with col_m1:
        nk_df = get_ticker_df(data_dict, "^N225")
        if len(nk_df) >= 2:
            latest = nk_df['Close'].iloc[-1]
            prev = nk_df['Close'].iloc[-2]
            diff = latest - prev
            pct = (diff / prev) * 100
            st.metric("日経平均株価", f"{latest:,.2f} 円", f"{diff:+,.2f} 円 ({pct:+.2f}%)")
        else:
            st.metric("日経平均株価", "データ取得中...", "-")
            
    with col_m2:
        fx_df = get_ticker_df(data_dict, "JPY=X")
        if len(fx_df) >= 2:
            latest = fx_df['Close'].iloc[-1]
            prev = fx_df['Close'].iloc[-2]
            diff = latest - prev
            pct = (diff / prev) * 100
            st.metric("米ドル / 円", f"{latest:.2f} 円", f"{diff:+.2f} 円 ({pct:+.2f}%)")
        else:
            st.metric("米ドル / 円", "データ取得中...", "-")
            
    with col_m3:
        st.info("💡 気になる銘柄の「📈 分析」ボタンを押すと、直接個別分析画面へ遷移できます。")
        
    st.markdown("---")
    
    tab_titles = ["🇺🇸 米国人気10選"] + [f"🔥 {s}" for s in sorted_sectors]
    tabs = st.tabs(tab_titles)
    
    # 1. 米国人気10選
    with tabs[0]:
        st.subheader("🇺🇸 米国株式市場：人気・主力10銘柄")
        st.info("💡 **資金流入背景**: 世界のAIイノベーションを牽引する巨大IT・半導体企業を中心とした資金集中。")
        
        cols = st.columns(5)
        for idx, (ticker, name) in enumerate(US_POPULAR_10.items()):
            df = get_ticker_df(data_dict, ticker)
            with cols[idx % 5]:
                if len(df) >= 2:
                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    change = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
                    st.button(f"📈 分析 ({ticker})", key=f"btn_us_{ticker}", on_click=select_ticker, args=(ticker,))
                    st.metric(label=f"{name}", value=f"${latest['Close']:,.1f}", delta=f"{change:+.2f}%")
                else:
                    st.write(f"取得失敗: {name}")

    # 2. 変動額順 10大業界タブ
    for s_idx, sector_name in enumerate(sorted_sectors):
        info = SECTOR_DATA[sector_name]
        with tabs[s_idx + 1]:
            st.subheader(f"🏢 {sector_name} (平均変動額: ¥{sector_movement[sector_name]:,.1f})")
            
            c_bg, c_ev = st.columns([2, 2])
            with c_bg:
                st.success(f"🌊 **資金流入の背景分析**\n\n{info['bg']}")
            with c_ev:
                st.warning(f"⚡ **今後の注目イベント・触媒**\n\n{info['event']}")
            
            st.markdown("#### 🏆 業界トップ10銘柄")
            cols = st.columns(5)
            for idx, (ticker, name) in enumerate(info["top10"].items()):
                df = get_ticker_df(data_dict, ticker)
                unit = "$" if not ticker.endswith(".T") else "¥"
                with cols[idx % 5]:
                    if len(df) >= 2:
                        latest = df.iloc[-1]
                        prev = df.iloc[-2]
                        change = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
                        st.button(f"📈 分析 ({ticker.replace('.T','')})", key=f"btn_sec_{sector_name}_{ticker}", on_click=select_ticker, args=(ticker,))
                        st.metric(label=f"{name}", value=f"{unit}{latest['Close']:,.1f}", delta=f"{change:+.2f}%")
                    else:
                        st.write(f"取得失敗: {name}")

# ==========================================
# 📈 個別銘柄詳細＆深掘り分析
# ==========================================
elif mode == "📈 個別銘柄詳細＆深掘り分析":
    st.title("🔍 個別銘柄 検索 ＆ 深掘り分析")
    
    # 銘柄が選択されている時のみ「トップへ戻る」ボタンを表示
    if st.session_state.target_ticker != "":
        st.button("⬅️ 個別銘柄トップ（10大業界一覧）に戻る", on_click=clear_ticker)

    # 検索バー
    search_options = [""] + list(ALL_TICKERS.keys())
    
    # 現在選択されている銘柄のインデックス取得
    current_idx = search_options.index(st.session_state.target_ticker) if st.session_state.target_ticker in search_options else 0
    
    selected_from_box = st.selectbox(
        "🔍 銘柄コードまたは社名で検索・選択してください",
        options=search_options,
        index=current_idx,
        format_func=lambda x: "🔎 タップして銘柄を選択または入力..." if x == "" else f"{x.replace('.T', '')} - {ALL_TICKERS.get(x, '')}",
        key="sb_ticker_selector"
    )
    
    if selected_from_box != st.session_state.target_ticker:
        st.session_state.target_ticker = selected_from_box

    selected_ticker = st.session_state.target_ticker

    # 銘柄が選択されている場合の詳細分析表示
    if selected_ticker != "":
        comp_name = ALL_TICKERS.get(selected_ticker, selected_ticker)
        is_us = not selected_ticker.endswith(".T")
        unit = "$" if is_us else "¥"
        
        st.markdown(f"## **{comp_name} ({selected_ticker})**")
        
        df = get_ticker_df(data_dict, selected_ticker)
        if len(df) >= 2:
            df = calculate_indicators(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("現在値 (終値)", f"{unit}{latest['Close']:,.1f}", f"{((latest['Close']-prev['Close'])/prev['Close'])*100:+.2f}%")
            m2.metric("始値", f"{unit}{latest['Open']:,.1f}")
            m3.metric("高値", f"{unit}{latest['High']:,.1f}")
            m4.metric("安値", f"{unit}{latest['Low']:,.1f}")
            m5.metric("前日終値", f"{unit}{prev['Close']:,.1f}")
            
            st.markdown("---")
            st.markdown("### 🔍 株価・業績期待値の深掘り評価")
            info = fetch_info_data(selected_ticker)
            
            f1, f2, f3 = st.columns(3)
            with f1:
                st.subheader("🏢 本業の収益力")
                profit_margin = info.get("profitMargins", None)
                roe = info.get("returnOnEquity", None)
                reasons_m = []
                if profit_margin is not None:
                    if profit_margin > 0.15: reasons_m.append(f"🟢 **高利益率 ({profit_margin*100:.1f}%)**: 価格転嫁力が強い。")
                    elif profit_margin < 0.04: reasons_m.append(f"🔴 **低利益率 ({profit_margin*100:.1f}%)**: コスト圧迫。")
                if roe is not None and roe > 0.12: reasons_m.append(f"🟢 **高ROE ({roe*100:.1f}%)**: 効率経営。")
                st.write("\n\n".join(reasons_m) if reasons_m else "標準的な収益構造です。")

            with f2:
                st.subheader("🎯 期待値・バリュエーション")
                per = info.get("trailingPE", None)
                pbr = info.get("priceToBook", None)
                reasons_e = []
                if per is not None:
                    if per > 35: reasons_e.append(f"🔥 **高成長織り込み (PER {per:.1f}倍)**")
                    elif per < 12: reasons_e.append(f"💡 **割安放置 (PER {per:.1f}倍)**")
                if pbr is not None and pbr < 1.0: reasons_e.append(f"📢 **PBR1倍割れ ({pbr:.2f}倍)**: 株主還元期待。")
                st.write("\n\n".join(reasons_e) if reasons_e else "中立的な評価水準です。")

            with f3:
                st.subheader("🛡️ 財務・株主還元")
                debt_eq = info.get("debtToEquity", None)
                div_yield = info.get("dividendYield", None)
                reasons_f = []
                if debt_eq is not None and debt_eq < 50: reasons_f.append("🏰 **健全な財務構造**")
                if div_yield is not None and div_yield > 0.03: reasons_f.append(f"💰 **高配当魅力 ({div_yield*100:.2f}%)**")
                st.write("\n\n".join(reasons_f) if reasons_f else "バランスのとれた財務状態です。")

            # チャート表示
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='ローソク足'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA5'], name='5日線', line=dict(color='orange', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA25'], name='25日線', line=dict(color='blue', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA75'], name='75日線', line=dict(color='purple', width=1)), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='出来高', marker_color='cadetblue'), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='green')), row=3, col=1)
            
            fig.update_xaxes(rangeselector=dict(buttons=list([
                dict(count=1, label="1ヶ月", step="month", stepmode="backward"),
                dict(count=3, label="3ヶ月", step="month", stepmode="backward"),
                dict(step="all", label="全期間")
            ])), rangeslider=dict(visible=True), type="date")
            fig.update_layout(height=650, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("データの取得に失敗したか、十分なデータがありません。")

    else:
        # 未選択時のトップ画面（全10業界トップ10一覧）
        st.markdown("---")
        st.subheader("🏆 全10業界 ＆ 米国株トップ10一覧")
        st.caption("上記の検索バーに検索・入力するか、気になる銘柄の「📈 分析」ボタンを押すと詳細チャートを表示します。")
        
        for sec_name in sorted_sectors:
            sec_info = SECTOR_DATA[sec_name]
            st.markdown(f"#### 🏢 {sec_name}")
            cols = st.columns(5)
            for idx, (ticker, name) in enumerate(sec_info["top10"].items()):
                with cols[idx % 5]:
                    st.button(f"📈 分析 ({name})", key=f"top_page_{sec_name}_{ticker}", on_click=select_ticker, args=(ticker,))

# ==========================================
# 🚀 テンバガー（急騰）候補
# ==========================================
elif mode == "🚀 テンバガー（急騰）候補":
    st.header("🚀 テンバガー（急騰）候補スクリーニング")
    st.caption("テクニカル条件に合致した注目銘柄一覧です。「📈 分析画面へ」ボタンで直接分析できます。")
    
    results = []
    for ticker, name in ALL_TICKERS.items():
        try:
            df = get_ticker_df(data_dict, ticker)
            if len(df) < 75: continue
            df = calculate_indicators(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            score = 0
            reasons = []
            actions = []
            
            if latest['Vol_Ratio'] >= 2.0:
                score += 30; reasons.append(f"出来高急増({latest['Vol_Ratio']:.1f}倍)"); actions.append("大口資金流入")
            if latest['Pinbar']:
                score += 25; reasons.append("下ひげ(底打ち)"); actions.append("反発サイン")
            if prev['SMA5'] <= prev['SMA25'] and latest['SMA5'] > latest['SMA25']:
                score += 25; reasons.append("5日線×25日線 GC"); actions.append("上昇トレンド開始")
            if prev['RSI'] < 35 and latest['RSI'] > prev['RSI']:
                score += 20; reasons.append(f"RSI反発({latest['RSI']:.1f}%)"); actions.append("打診買い検討")
                
            if score > 0:
                results.append({
                    "ticker": ticker, "code": ticker.replace(".T", ""), "name": name,
                    "price": f"{latest['Close']:,.1f}", "score": score,
                    "reasons": " / ".join(reasons), "actions": " / ".join(actions)
                })
        except Exception:
            continue
            
    if results:
        results = sorted(results, key=lambda x: x['score'], reverse=True)
        st.write(f"**該当件数: 全 {len(results)} 件**")
        
        for res in results:
            with st.container():
                col_btn, col_code, col_price, col_sig, col_act = st.columns([1.8, 2, 2, 3, 3])
                with col_btn:
                    st.button(f"📈 分析画面へ", key=f"btn_tb_{res['ticker']}", on_click=select_ticker, args=(res['ticker'],))
                col_code.markdown(f"**{res['code']}**\n\n{res['name']}")
                col_price.markdown(f"**株価**: {res['price']}\n\n**スコア**: {res['score']}")
                col_sig.markdown(f"**検出シグナル**:\n\n{res['reasons']}")
                col_act.markdown(f"**推奨アクション**:\n\n{res['actions']}")
                st.divider()
    else:
        st.info("現在、急騰シグナル条件に合致する銘柄はありません。")
