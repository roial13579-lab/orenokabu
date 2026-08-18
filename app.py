import streamlit as st

# ページ基本設定
st.set_page_config(
    page_title="個別銘柄 検索 & 深掘り",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------------
# 1. カスタムCSS（視認性の向上 & デザインの最適化）
# -------------------------------------------------------------------
st.markdown("""
<style>
    /* 全体背景 */
    .stApp {
        background-color: #f8fafc;
    }

    /* 上部ヘッダーの固定 */
    .sticky-header {
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: #ffffff;
        padding: 12px 0px;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 20px;
    }

    /* 銘柄分析ボタンのスタイル変更（赤色からの脱却・カード風デザイン） */
    div.stButton > button {
        width: 100% !important;
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        transition: all 0.2s ease-in-out !important;
        text-align: left !important;
    }

    /* ボタンホバー時 */
    div.stButton > button:hover {
        background-color: #eff6ff !important;
        border-color: #3b82f6 !important;
        color: #1d4ed8 !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
    }

    /* 戻るボタン専用スタイル */
    .back-btn > button {
        background-color: #f1f5f9 !important;
        border: 1px solid #94a3b8 !important;
        color: #334155 !important;
    }
    .back-btn > button:hover {
        background-color: #e2e8f0 !important;
        border-color: #64748b !important;
    }

    /* カテゴリ見出しの装飾 */
    .category-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #334155;
        border-left: 4px solid #3b82f6;
        padding-left: 10px;
        margin-top: 20px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# 2. 銘柄データ定義
# -------------------------------------------------------------------
STOCK_DATA = {
    "半導体": [
        "東京エレクトロン", "アドバンテスト", "ディスコ", "レーザーテック", "NVIDIA",
        "ルネサス", "SCREEN HD", "ソニーグループ", "ASML", "TSMC"
    ],
    "消費・小売り": [
        "ファーストリテイリング", "セブン＆アイHD", "イオン", "パン・パシフィックHD", "ゲオHD",
        "Walmart", "Costco", "Procter & Gamble", "Coca-Cola", "Nike"
    ],
    "重工・防衛": [
        "三菱重工業", "川崎重工業", "IHI", "小松製作所", "ダイキン工業",
        "石川製作所", "豊和工業", "三井E&S", "Lockheed Martin", "RTX"
    ],
    "エネ資源": [
        "INPEX", "ENEOS HD", "日本製鉄", "信越化学工業", "ExxonMobil"
    ]
}

# フラットなリスト（検索用）
ALL_STOCKS = [stock for category in STOCK_DATA.values() for stock in category]

# -------------------------------------------------------------------
# 3. セッション状態（State）の初期化
# -------------------------------------------------------------------
if "selected_stock" not in st.session_state:
    st.session_state["selected_stock"] = None

def select_stock(stock_name):
    st.session_state["selected_stock"] = stock_name

def reset_to_top():
    st.session_state["selected_stock"] = None

# -------------------------------------------------------------------
# 4. 固定上部ナビゲーションエリア
# -------------------------------------------------------------------
st.markdown('<div class="sticky-header">', unsafe_allow_html=True)

col_back, col_search = st.columns([1, 3])

with col_back:
    # 選択されている時のみ「戻る」ボタンを有効化/目立たせる
    if st.session_state["selected_stock"] is not None:
        st.button("⬅️ 個別銘柄トップ（10大業界一覧）に戻る", on_click=reset_to_top, key="back_btn")
    else:
        st.write("📊 **全10業界 & 米国株トップ一覧**")

with col_search:
    # ドロップダウン検索
    selected_from_search = st.selectbox(
        "🔍 銘柄コードまたは社名で検索・選択してください",
        options=[""] + ALL_STOCKS,
        index=0 if st.session_state["selected_stock"] is None else (
            ALL_STOCKS.index(st.session_state["selected_stock"]) + 1 
            if st.session_state["selected_stock"] in ALL_STOCKS else 0
        ),
        label_visibility="collapsed"
    )
    if selected_from_search and selected_from_search != st.session_state["selected_stock"]:
        st.session_state["selected_stock"] = selected_from_search
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# 5. メイン表示エリアの分岐
# -------------------------------------------------------------------
if st.session_state["selected_stock"] is None:
    # --- 【画面A】トップ一覧画面 ---
    st.subheader("🏆 全10業界 & 米国株トップ一覧")
    st.caption("気になる銘柄のボタンを押すと詳細チャート・分析を表示します。")

    for category, stocks in STOCK_DATA.items():
        st.markdown(f'<div class="category-title">🏢 {category}</div>', unsafe_allow_html=True)

        # 5列に並べて配置
        cols = st.columns(5)
        for idx, stock in enumerate(stocks):
            with cols[idx % 5]:
                st.button(
                    f"📝 {stock}",
                    key=f"btn_{category}_{stock}",
                    on_click=select_stock,
                    args=(stock,)
                )

else:
    # --- 【画面B】個別銘柄 詳細分析画面 ---
    stock_name = st.session_state["selected_stock"]
    st.title(f"🔍 {stock_name} の個別分析")

    # サンプル分析コンテンツ
    st.info(f"現在、**{stock_name}** のチャートおよび詳細データを表示しています。")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="現在値", value="2,450 円", delta="+35 円 (+1.45%)")
    with col2:
        st.metric(label="出来高", value="1,240,000 株", delta="-5.2%")

    st.write("---")
    st.subheader("📈 テクニカル分析指標")
    st.write("・RSI: 54.2 (中立)")
    st.write("・移動平均線: 25日線の上で推移中")
