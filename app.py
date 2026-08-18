import streamlit as st

# 1. ページ基本設定
st.set_page_config(
    page_title="個別銘柄検索 & 深掘り",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. カスタムCSS（赤色の強い圧迫感を抑え、元のレイアウトを保つ）
st.markdown("""
<style>
    /* 全体背景 */
    .main {
        background-color: #fafafa;
    }

    /* 銘柄分析ボタンのスタイル（赤背景を解消し、見やすいカード風に変更） */
    div.stButton > button {
        background-color: #ffffff !important;
        color: #333333 !important;
        border: 1px solid #e0e0e0 !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        padding: 6px 10px !important;
        margin-bottom: 4px !important;
        box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.05) !important;
        width: 100% !important;
        text-align: left !important;
    }

    /* ボタンホバー（カーソルをのせた時）のスタイル */
    div.stButton > button:hover {
        background-color: #f0f7ff !important;
        border-color: #0066cc !important;
        color: #0066cc !important;
    }

    /* トップへ戻るボタンの強調表示 */
    div[data-testid="stColumn"] > div > div > div > button {
        border-color: #cccccc !important;
    }

    /* カテゴリタイトルの余白調整 */
    .category-header {
        font-size: 18px;
        font-weight: bold;
        color: #222222;
        margin-top: 15px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 3. 業界＆銘柄データ構造（画像上の銘柄順）
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

# 全銘柄リスト（検索ドロップダウン用）
ALL_STOCKS = [stock for category in STOCK_DATA.values() for stock in category]

# 4. セッション状態（State）の初期化
if "selected_stock" not in st.session_state:
    st.session_state["selected_stock"] = None

# 5. アプリヘッダー部分
st.write("🔍 **個別銘柄 検索 & 深掘り**")

# 「トップに戻る」ボタンエリア
col_back, col_empty = st.columns([2, 5])
with col_back:
    if st.button("⬅️ 個別銘柄トップ（10大業界一覧）に戻る", key="btn_return_top"):
        st.session_state["selected_stock"] = None
        st.rerun()

# 銘柄検索バー
st.write("🔍 銘柄コードまたは社名で検索・選択してください")
search_selection = st.selectbox(
    "銘柄選択",
    options=["タップして銘柄を選択または入力..."] + ALL_STOCKS,
    index=0 if st.session_state["selected_stock"] is None else (
        ALL_STOCKS.index(st.session_state["selected_stock"]) + 1 
        if st.session_state["selected_stock"] in ALL_STOCKS else 0
    ),
    label_visibility="collapsed"
)

# 検索バーで銘柄が選ばれた場合の処理
if search_selection != "タップして銘柄を選択または入力..." and search_selection != st.session_state["selected_stock"]:
    st.session_state["selected_stock"] = search_selection
    st.rerun()

st.write("---")

# 6. メイン表示切り替え（トップ一覧 ⇄ 個別分析画面）
if st.session_state["selected_stock"] is None:
    # -------------------------------------------------------------
    # 【画面1】トップ一覧画面（赤色を廃止した5列レイアウト）
    # -------------------------------------------------------------
    st.title("🏆 全10業界 & 米国株トップ10一覧")
    st.caption("上記の検索バーに検索・入力するか、気になる銘柄の「📝 分析」ボタンを押すと詳細チャートを表示します。")

    for category_name, stocks in STOCK_DATA.items():
        st.markdown(f'<div class="category-header">🏢 {category_name}</div>', unsafe_allow_html=True)
        
        # 横5列に配置
        cols = st.columns(5)
        for idx, stock_name in enumerate(stocks):
            col = cols[idx % 5]
            with col:
                # 銘柄分析ボタン（クリックしたら個別詳細画面へ遷移）
                if st.button(f"📝 分析 ({stock_name})", key=f"btn_{category_name}_{stock_name}"):
                    st.session_state["selected_stock"] = stock_name
                    st.rerun()

else:
    # -------------------------------------------------------------
    # 【画面2】個別銘柄 詳細分析画面
    # -------------------------------------------------------------
    selected = st.session_state["selected_stock"]
    
    st.title(f"📊 {selected} の詳細分析")
    st.success(f"現在 **{selected}** の分析画面を表示しています。")
    
    # ここにチャートや詳細指標などのコンテンツが入ります
    st.write("・株価データおよび詳細チャートを表示中...")
