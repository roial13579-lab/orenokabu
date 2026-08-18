import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- ページ基本設定 ---
st.set_page_config(
    page_title="株ダッシュボード PRO+ 10大業界",
    page_icon="📈",
    layout="wide"
)

# --- 10大業界データ・流入背景・注目イベント・トップ10銘柄 ---
SECTOR_DATA = {
    "1.半導体": {
        "bg": "生成AIマーケットの爆発的拡大とデータセンター投資の加速。政府の国内製造拠点への手厚い補助金政策も強力な追い風。",
        "top10": {
            "8035.T": "東京エレクトロン", "6857.T": "アドバンテスト", "6146.T": "ディスコ", "6920.T": "レーザーテック", "NVDA": "NVIDIA",
            "6723.T": "ルネサス", "7735.T": "SCREEN HD", "6758.T": "ソニーグループ", "ASML": "ASML", "TSM": "TSMC"
        },
        "event": "次世代プロセス微細化競合、米国対中輸出規制の動向、主要AI・ビッグテック企業の設備投資計画"
    },
    "2.重工防衛": {
        "bg": "地政学リスクの高まりに伴う国家防衛費増額政策。宇宙開発や次世代インフラ更新需要の急増。",
        "top10": {
            "7011.T": "三菱重工業", "7012.T": "川崎重工業", "7013.T": "IHI", "6301.T": "小松製作所", "6367.T": "ダイキン工業",
            "6208.T": "石川製作所", "6203.T": "豊和工業", "7003.T": "三井E&S", "LMT": "Lockheed Martin", "RTX": "RTX"
        },
        "event": "防衛予算閣議決定、装備品輸出制限の緩和議論、宇宙航空関連の新規ナショナルプロジェクト発足"
    },
    "3.自動車": {
        "bg": "EV急拡大の一巡に伴うハイブリッド・PHEV車の再評価。円安による輸出利益の底上げとSDV（ソフトウェア定義車両）化の加速。",
        "top10": {
            "7203.T": "トヨタ自動車", "7267.T": "ホンダ", "7270.T": "SUBARU", "7201.T": "日産自動車", "TSLA": "Tesla",
            "7269.T": "スズキ", "7202.T": "いすゞ自動車", "6594.T": "ニデック", "RACE": "Ferrari", "BYDDF": "BYD"
        },
        "event": "為替レート変動、新興国市場でのEV普及ペース、次世代電池（全固体電池）の量産ロードマップ"
    },
    "4.大型金融": {
        "bg": "日銀の金利引き上げ局面における利ざや（貸出金利と預金金利の差）改善期待。東証改革に伴う大規模な自社株買い・増配の定着。",
        "top10": {
            "8306.T": "三菱UFJ FG", "8316.T": "三井住友 FG", "8411.T": "みずほ FG", "8604.T": "野村 HD", "8766.T": "東京海上 HD",
            "8308.T": "りそな HD", "8309.T": "三井住友トラスト", "8630.T": "SOMPO HD", "8725.T": "MS&AD", "JPM": "JPMorgan Chase"
        },
        "event": "日銀金融政策決定会合の金利方針、イールドカーブ長短金利の動き、政策保有株の売却進捗状況"
    },
    "5.エネ資源": {
        "bg": "世界的なインフレ懸念と資源供給制限リスク。脱炭素（GX）投資と従来型エネルギーの収益最大化の併走。",
        "top10": {
            "1605.T": "INPEX", "5020.T": "ENEOS HD", "5401.T": "日本製鉄", "4063.T": "信越化学工業", "XOM": "ExxonMobil",
            "1518.T": "三井松島 HD", "5019.T": "出光興産", "5713.T": "住友金属鉱山", "CVX": "Chevron", "SHEL": "Shell"
        },
        "event": "OPEC+の生産調整決定、WTI原油/LNG市場価格の乱高下、GX経済移行債の利活用展開"
    },
    "6.IT・通信": {
        "bg": "DX（デジタルトランスフォーメーション）需要の定着とクラウド移行。通信料金改定の一巡と5G/6Gインフラ投資。",
        "top10": {
            "9432.T": "NTT", "9433.T": "KDDI", "9984.T": "ソフトバンクグループ", "4755.T": "楽天グループ", "9434.T": "ソフトバンク",
            "MSFT": "Microsoft", "GOOGL": "Alphabet", "AAPL": "Apple", "ORCL": "Oracle", "ACN": "Accenture"
        },
        "event": "AIソリューション導入件数、ARPU（ユーザー平均単価）推移、自社株買い等の株主還元策"
    },
    "7.医薬品": {
        "bg": "特許切れ（特許の壁）を克服するバイオ医薬品やmRNA技術へのシフト。世界的な高齢化に伴う医療需要の増大。",
        "top10": {
            "4502.T": "武田薬品工業", "4568.T": "第一三共", "4519.T": "中外製薬", "4503.T": "アステラス製薬", "4523.T": "エーザイ",
            "LLY": "Eli Lilly", "NVO": "Novo Nordisk", "PFE": "Pfizer", "JNJ": "Johnson & Johnson", "MRK": "Merck"
        },
        "event": "新薬パイプラインの治験（Phase3等）成否、肥満症薬等の世界的販売拡大、薬価改定の影響"
    },
    "8.大手商社": {
        "bg": "ウォーレン・バフェット率いるバークシャーの投資で世界的人気。資源利権と非資源事業（食料・IT等）の分散収益モデル。",
        "top10": {
            "8058.T": "三菱商事", "8001.T": "伊藤忠商事", "8031.T": "三井物産", "8015.T": "豊田通商", "8002.T": "丸紅",
            "2768.T": "双日", "8053.T": "住友商事", "8020.T": "兼松", "BRK-B": "Berkshire Hathaway", "8028.T": "ユニゾHD"
        },
        "event": "配当方針（累進配当の維持・拡充）、海外大型案件のM&A動向、金属・エネルギー市場価格"
    },
    "9.不動産": {
        "bg": "都心再開発事業による賃料水準の上昇とインバウンド需要に伴うホテル事業の好調。金利上昇局面での選別投資。",
        "top10": {
            "8801.T": "三井不動産", "8802.T": "三菱地所", "8830.T": "住友不動産", "3289.T": "東急不動産HD", "8804.T": "東京建物",
            "PLD": "Prologis", "AMT": "American Tower", "EQIX": "Equinix", "SPG": "Simon Property", "O": "Realty Income"
        },
        "event": "都心オフィス空室率推移、地価公示価格の変動、借入金利（長期金利）の上昇ペース"
    },
    "10.消費・小売": {
        "bg": "訪日外国人客（インバウンド）の消費拡大と価格転嫁（値上げ）定着による粗利益率の向上。",
        "top10": {
            "9983.T": "ファーストリテイリング", "3382.T": "セブン&アイHD", "8267.T": "イオン", "7532.T": "パン・パシフィックHD", "2681.T": "ゲオHD",
            "WMT": "Walmart", "COST": "Costco", "PG": "Procter & Gamble", "KO": "Coca-Cola", "NKE": "Nike"
        },
        "event": "月次売上高の推移、インバウンド免税売上額、海外店舗（中国・欧米）の出店・伸び率"
    }
}

US_POPULAR_10 = {
    "NVDA": "NVIDIA", "AAPL": "Apple", "MSFT": "Microsoft", "AMZN": "Amazon", "GOOGL": "Alphabet",
    "META": "Meta Platforms", "TSLA": "Tesla", "AVGO": "Broadcom", "LLY": "Eli Lilly", "BRK-B": "Berkshire Hathaway"
}

# 全銘柄マップの作成
ALL_TICKERS = {}
for s, v in SECTOR_DATA.items():
    ALL_TICKERS.update(v["top10"])
ALL_TICKERS.update(US_POPULAR_10)

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

@st.cache_data(ttl=600)
def fetch_data():
    all_symbols = list(ALL_TICKERS.keys()) + ["^N225", "JPY=X"]
    return yf.download(all_symbols, period="1y", interval="1d", group_by="ticker", progress=False)

@st.cache_data(ttl=3600)
def fetch_info_data(ticker):
    try:
        t = yf.Ticker(ticker)
        return t.info
    except Exception:
        return {}

data_dict = fetch_data()

# --- セッション状態管理 ---
if "history" not in st.session_state:
    st.session_state.history = ["📊 10大業界＆米国株トップ10"]
if "target_ticker" not in st.session_state:
    st.session_state.target_ticker = ""
if "nav_mode" not in st.session_state:
    st.session_state.nav_mode = "📊 10大業界＆米国株トップ10"

def navigate_to(mode, ticker=None):
    if ticker is not None:
        st.session_state.target_ticker = ticker
    st.session_state.history.append(mode)
    st.session_state.nav_mode = mode

def go_back():
    if len(st.session_state.history) > 1:
        st.session_state.history.pop()
        st.session_state.nav_mode = st.session_state.history[-1]

# --- 左上 戻るボタンヘッダー ---
top_col1, top_col2 = st.columns([1, 5])
with top_col1:
    if len(st.session_state.history) > 1:
        st.button("⬅️ 前の画面に戻る", on_click=go_back, type="secondary")

# サイドバー設定
mode = st.sidebar.radio(
    "機能選択",
    ["📊 10大業界＆米国株トップ10", "📈 個別銘柄詳細＆深掘り分析", "🚀 テンバガー（急騰）候補"],
    key="nav_mode"
)

# ==========================================
# 📊 10大業界＆米国株トップ10
# ==========================================
if mode == "📊 10大業界＆米国株トップ10":
    st.title("📊 10大業界マップ・市場動向")
    
    # ── 市況リアルタイム指標（日経平均・ドル円） ──
    col_m1, col_m2, col_m3 = st.columns(3)
    
    # 日経平均
    with col_m1:
        try:
            nk_df = data_dict["^N225"].dropna()
            nk_latest = nk_df['Close'].iloc[-1]
            nk_prev = nk_df['Close'].iloc[-2]
            nk_diff = nk_latest - nk_prev
            nk_pct = (nk_diff / nk_prev) * 100
            st.metric("日経平均株価", f"{nk_latest:,.2f} 円", f"{nk_diff:+,.2f} 円 ({nk_pct:+.2f}%)")
        except Exception:
            st.metric("日経平均株価", "データ取得中...", "-")
            
    # ドル円
    with col_m2:
        try:
            fx_df = data_dict["JPY=X"].dropna()
            fx_latest = fx_df['Close'].iloc[-1]
            fx_prev = fx_df['Close'].iloc[-2]
            fx_diff = fx_latest - fx_prev
            fx_pct = (fx_diff / fx_prev) * 100
            st.metric("米ドル / 円", f"{fx_latest:.2f} 円", f"{fx_diff:+.2f} 円 ({fx_pct:+.2f}%)")
        except Exception:
            st.metric("米ドル / 円", "データ取得中...", "-")
            
    with col_m3:
        st.info("💡 下記のタブから業界ごとの「資金流入の背景」と「注目イベント」をご確認いただけます。")
        
    st.markdown("---")
    
    tab_titles = ["🇺🇸 米国人気10選"] + list(SECTOR_DATA.keys())
    tabs = st.tabs(tab_titles)
    
    # 1. 米国人気10選
    with tabs[0]:
        st.subheader("🇺🇸 米国株式市場：人気・主力10銘柄")
        st.info("💡 **資金流入背景**: 世界のAIイノベーションを牽引する巨大IT・半導体企業（マグニフィセント7等）を中心とした世界的な資金集中。")
        
        cols = st.columns(5)
        for idx, (ticker, name) in enumerate(US_POPULAR_10.items()):
            try:
                df = data_dict[ticker].dropna()
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                change = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
                with cols[idx % 5]:
                    st.button(f"📈 分析 ({ticker})", key=f"btn_us_{ticker}", on_click=navigate_to, args=("📈 個別銘柄詳細＆深掘り分析", ticker), type="primary")
                    st.metric(label=f"{name}", value=f"${latest['Close']:,.1f}", delta=f"{change:+.2f}%")
            except Exception:
                with cols[idx % 5]: st.write(f"取得失敗: {name}")

    # 2. 各10大業界タブ
    for s_idx, (sector_name, info) in enumerate(SECTOR_DATA.items()):
        with tabs[s_idx + 1]:
            st.subheader(f"🏢 {sector_name}")
            
            c_bg, c_ev = st.columns([2, 2])
            with c_bg:
                st.success(f"🌊 **資金流入の背景分析**\n\n{info['bg']}")
            with c_ev:
                st.warning(f"⚡ **今後の注目イベント・触媒**\n\n{info['event']}")
            
            st.markdown("#### 🏆 業界トップ10銘柄")
            cols = st.columns(5)
            for idx, (ticker, name) in enumerate(info["top10"].items()):
                try:
                    df = data_dict[ticker].dropna()
                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    change = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
                    unit = "$" if not ticker.endswith(".T") else "¥"
                    
                    with cols[idx % 5]:
                        st.button(f"📈 分析 ({ticker.replace('.T','')})", key=f"btn_sec_{sector_name}_{ticker}", on_click=navigate_to, args=("📈 個別銘柄詳細＆深掘り分析", ticker), type="primary")
                        st.metric(label=f"{name}", value=f"{unit}{latest['Close']:,.1f}", delta=f"{change:+.2f}%")
                except Exception:
                    with cols[idx % 5]: st.write(f"取得失敗: {name}")

# ==========================================
# 📈 個別銘柄詳細＆深掘り分析
# ==========================================
elif mode == "📈 個別銘柄詳細＆深掘り分析":
    st.title("🔍 個別銘柄 検索 ＆ 深掘り分析")
    
    # このページの上部に検索バーを配置
    search_query = st.selectbox(
        "🔍 銘柄コードまたは社名で検索・選択してください（日本株・米国株対応）",
        options=[""] + list(ALL_TICKERS.keys()),
        format_func=lambda x: "🔎 タップして銘柄を入力または選択してください..." if x == "" else f"{x.replace('.T', '')} - {ALL_TICKERS.get(x, '')}",
        key="indiv_search_bar"
    )
    
    if search_query:
        st.session_state.target_ticker = search_query

    selected_ticker = st.session_state.target_ticker

    # 銘柄が選択されている場合は詳細画面を表示
    if selected_ticker:
        comp_name = ALL_TICKERS.get(selected_ticker, selected_ticker)
        is_us = not selected_ticker.endswith(".T")
        unit = "$" if is_us else "¥"
        
        st.markdown(f"## **{comp_name} ({selected_ticker})**")
        
        df = data_dict[selected_ticker].dropna()
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
                if profit_margin > 0.15:
                    reasons_m.append(f"🟢 **高い純利益率 ({profit_margin*100:.1f}%)**: 価格転嫁力・ブランド力が高く、本業で圧倒的な稼ぐ力を保持。")
                elif profit_margin < 0.04:
                    reasons_m.append(f"🔴 **利益率の上値重さ ({profit_margin*100:.1f}%)**: 原材料費や人件費の高騰が利益圧迫要因。")
            if roe is not None:
                if roe > 0.12:
                    reasons_m.append(f"🟢 **高ROE ({roe*100:.1f}%)**: 株主資本を効率的に活用して収益を生み出す経営効率。")
            if not reasons_m:
                reasons_m.append("本業の収益構造および資本効率は標準的。")
            st.write("\n\n".join(reasons_m))

        with f2:
            st.subheader("🎯 期待値・バリュエーション")
            per = info.get("trailingPE", None)
            pbr = info.get("priceToBook", None)
            
            reasons_e = []
            if per is not None:
                if per > 35:
                    reasons_e.append(f"🔥 **高成長期待織り込み (PER {per:.1f}倍)**: テーマ性への評価が高い反面、決算未達時の反応に注意。")
                elif per < 12:
                    reasons_e.append(f"💡 **割安放置/見直し期待 (PER {per:.1f}倍)**: 利益水準に対して評価が低く、買い直し余地あり。")
            if pbr is not None and pbr < 1.0:
                reasons_e.append(f"📢 **PBR1倍割れ ({pbr:.2f}倍)**: 東証の株価意識要請に伴う自社株買い・増配期待が強い下値支持。")
            if not reasons_e:
                reasons_e.append("指標面の市場評価はバリュエーション的に中立水準。")
            st.write("\n\n".join(reasons_e))

        with f3:
            st.subheader("🛡️ 財務・株主還元")
            debt_eq = info.get("debtToEquity", None)
            div_yield = info.get("dividendYield", None)
            
            reasons_f = []
            if debt_eq is not None:
                if debt_eq < 50:
                    reasons_f.append(f"🏰 **健全な財務構造**: 負債比率が低く、金利上昇局面でも揺らがない安定感。")
                elif debt_eq > 200:
                    reasons_f.append(f"⚠️ **有利子負債多め**: 金利コスト増加が懸念材料。")
            if div_yield is not None and div_yield > 0.03:
                reasons_f.append(f"💰 **高配当インカム魅力 ({div_yield*100:.2f}%)**: 投資家の買いを呼び込む強力な下値の支え。")
            if not reasons_f:
                reasons_f.append("財務リスク・配当水準ともにバランスのとれた推移。")
            st.write("\n\n".join(reasons_f))

        # チャート表示
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='ローソク足'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA5'], name='5日線(短期)', line=dict(color='orange', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA25'], name='25日線(中期)', line=dict(color='blue', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA75'], name='75日線(長期)', line=dict(color='purple', width=1)), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='出来高', marker_color='cadetblue'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI(14)', line=dict(color='green')), row=3, col=1)
        
        fig.update_xaxes(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1ヶ月", step="month", stepmode="backward"),
                    dict(count=3, label="3ヶ月", step="month", stepmode="backward"),
                    dict(count=6, label="6ヶ月", step="month", stepmode="backward"),
                    dict(step="all", label="全期間")
                ])
            ),
            rangeslider=dict(visible=True),
            type="date"
        )
        fig.update_layout(height=650, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    else:
        # 未選択時の個別銘柄トップ表示（全10業界トップ10一覧）
        st.markdown("---")
        st.subheader("🏆 全10業界 ＆ 米国株トップ10一覧")
        st.caption("検索バーから検索するか、気になる銘柄の「📈 分析」ボタンを押すと詳細チャートを表示します。")
        
        for sec_name, sec_info in SECTOR_DATA.items():
            st.markdown(f"#### 🏢 {sec_name}")
            cols = st.columns(5)
            for idx, (ticker, name) in enumerate(sec_info["top10"].items()):
                with cols[idx % 5]:
                    st.button(f"📈 分析 ({name})", key=f"top_page_{sec_name}_{ticker}", on_click=navigate_to, args=("📈 個別銘柄詳細＆深掘り分析", ticker), type="primary")

# ==========================================
# 🚀 テンバガー（急騰）候補
# ==========================================
elif mode == "🚀 テンバガー（急騰）候補":
    st.header("🚀 テンバガー（急騰）候補スクリーニング")
    st.caption("テクニカル指標の条件に合致した注目銘柄一覧です。「📈 分析画面へ」ボタンで即座に個別分析に移行できます。")
    
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
        
        for res in results:
            with st.container():
                col_btn, col_code, col_price, col_sig, col_act = st.columns([1.8, 2, 2, 3, 3])
                with col_btn:
                    st.button(f"📈 分析画面へ", key=f"btn_tb_{res['ticker']}", on_click=navigate_to, args=("📈 個別銘柄詳細＆深掘り分析", res['ticker']), type="primary")
                col_code.markdown(f"**{res['code']}**\n\n{res['name']}")
                col_price.markdown(f"**株価**: {res['price']}\n\n**スコア**: {res['score']}")
                col_sig.markdown(f"**検出シグナル**:\n\n{res['reasons']}")
                col_act.markdown(f"**推奨アクション**:\n\n{res['actions']}")
                st.divider()
    else:
        st.info("現在、急騰シグナル条件に合致する銘柄はありません。")
