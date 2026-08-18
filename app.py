import streamlit as st

# 1. ページ基本設定
st.set_page_config(
    page_title="株式分析ダッシュボード",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. カスタムCSS（赤色の強圧感を抑え、元の見やすく整ったボタンデザインへ）
st.markdown("""
<style>
    /* 全体背景 */
    .stApp {
        background-color: #f8fafc;
    }

    /* 銘柄分析ボタン（赤背景から、見やすい白カード風デザインへ変更） */
    div.stButton > button {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        padding: 6px 10px !important;
        margin-bottom: 4px !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        width: 100% !important;
        text-align: left !important;
        transition: all 0.15s ease-in-out !important;
    }

    /* ボタンホバー時 */
    div.stButton > button:hover {
        background-color: #f1f5f9 !important;
        border-color: #2563eb !important;
        color: #2563eb !important;
    }

    /* 業界見出しの装飾 */
    .category-title {
        font-size: 16px;
        font-weight: 700;
        color: #334155;
        margin-top: 18px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    /* 検索バー周りの調整 */
    .search-box-label {
        font-size: 13px;
        color: #475569;
        font-weight: 600;
        margin-top: 8px;
    }
</style>
""", unsafe_allow_html=True)

# 3. データ定義（全10業界 & 米国株トップ一覧）
SECTOR_STOCKS = {
    "🏢 半導体": [
        "東京エレクトロン", "アドバンテスト", "ディスコ", "レーザーテック", "NVIDIA",
        "ルネサス", "SCREEN HD", "ソニーグループ", "ASML", "TSMC"
    ],
    "🏢 商業・小売り": [
        "ファーストリテイリング", "セブン＆アイHD", "イオン", "パン・パシフィックHD", "ゲオHD",
        "Walmart", "Costco", "Procter & Gamble", "Coca-Cola", "Nike"
    ],
    "🏢 重工・防衛": [
        "三菱重工業", "川崎重工業", "IHI", "小松製作所", "ダイキン工業",
        "石川製作所", "豊和工業", "三井E&S", "Lockheed Martin", "RTX"
    ],
    "🏢 エネ資源": [
        "INPEX", "ENEOS HD", "日本製鉄", "信越化学工業", "ExxonMobil",
        "Chevron", " Occidental", "Shell", "BP", "TotalEnergies"
    ],
    "🏢 自動車・輸送機器": [
        "トヨタ自動車", "本田技研工業", "日産自動車", "スズキ", "マツダ",
        "デンソー", "アイシン", "野村原油", "Tesla", "General Motors"
    ],
    "🏢 金融・銀行": [
        "三菱UFJ FG", "三井住友 FG", "みずほ FG", "ゆうちょ銀行", "野村 HD",
        "JPMorgan Chase", "Bank of America", "Morgan Stanley", "Wells Fargo", "Goldman Sachs"
    ],
    "🏢 情報通信・IT": [
        "NTT", "ソフトバンクグループ", "KDDI", "富士通", "NEC",
        "Microsoft", "Apple", "Alphabet (Google)", "Amazon", "Meta"
    ],
    "🏢 医薬品・バイオ": [
        "武田薬品工業", "中外製薬", "第一三共", "アステラス製薬", "エーザイ",
        "Eli Lilly", "Novo Nordisk", "Pfizer", "Merck", "AbbVie"
    ],
    "🏢 商社・卸売": [
        "三菱商事", "伊藤忠商事", "三井物産", "住友商事", "丸紅", "豊田通商", "双日", "岩谷産業", "稲畑産業", "加賀電子"
    ],
    "🏢 ゲーム・エンタメ": [
        "任天堂", "バンダイナムコHD", "スクウェア・エニックス", "カプコン", "東宝",
        "Walt Disney", "Netflix", "Electronic Arts", "Take-Two", "Sony Interactive"
    ]
}

# 全銘柄リスト（検索ドロップダウン用）
ALL_STOCKS_LIST = [stock for stocks in SECTOR_STOCKS.values() for stock in stocks]

# 4. セッション状態（State）管理
if "selected_stock" not in st.session_state:
    st.session_state["selected_stock"] = None

def select_stock(stock_name):
    st.session_state["selected_stock"] = stock_name

def reset_to_top():
    st.session_state["selected_stock"] = None

# 5. 上部操作エリア（「トップに戻る」ボタン & 検索バー）
col_back, col_space = st.columns([3, 4])
with col_back:
    # on_click で関数を呼び出すことで確実にトップへ戻る動作を実行
    st.button(
        "⬅️ 個別銘柄トップ（10大業界一覧）に戻る",
        key="btn_global_return",
        on_click=reset_to_top
    )

st.markdown('<div class="search-box-label">🔍 銘柄コードまたは社名で検索・選択してください</div>', unsafe_allow_html=True)

# ドロップダウン初期値の計算
current_index = 0
if st.session_state["selected_stock"] in ALL_STOCKS_LIST:
    current_index = ALL_STOCKS_LIST.index(st.session_state["selected_stock"]) + 1

selected_from_dropdown = st.selectbox(
    "検索・選択",
    options=["タップして銘柄を選択または入力..."] + ALL_STOCKS_LIST,
    index=current_index,
    label_visibility="collapsed"
)

# 検索ドロップダウン選択時の画面更新
if selected_from_dropdown != "タップして銘柄を選択または入力..." and selected_from_dropdown != st.session_state["selected_stock"]:
    st.session_state["selected_stock"] = selected_from_dropdown
    st.rerun()

st.write("---")

# 6. メイン表示エリア（トップ一覧 ⇄ 個別詳細分析）
if st.session_state["selected_stock"] is None:

    # タブメニューの構成（テンバガー等のタブを配置）
    tab_main, tab_tenbagger, tab_screening = st.tabs([
        "🏆 全10業界 & 米国株トップ一覧",
        "🚀 テンバガー候補・高成長株",
        "🔍 スクリーニング・指標一覧"
    ])

    # --- タブ1：全10業界 & 米国株トップ一覧 ---
    with tab_main:
        st.caption("上記の検索バーに検索・入力するか、気になる銘柄の「📝 分析」ボタンを押すと詳細チャートを表示します。")

        for category_title, stocks in SECTOR_STOCKS.items():
            st.markdown(f'<div class="category-title">{category_title}</div>', unsafe_allow_html=True)

            # 横5列配置
            cols = st.columns(5)
            for idx, stock in enumerate(stocks):
                with cols[idx % 5]:
                    st.button(
                        f"📝 分析 ({stock})",
                        key=f"btn_{category_title}_{stock}",
                        on_click=select_stock,
                        args=(stock,)
                    )

    # --- タブ2：テンバガー候補 ---
    with tab_tenbagger:
        st.subheader("🚀 テンバガー（10倍株）候補・注目高成長株")
        st.write("小型成長株や急拡大セクターの分析一覧を表示します。")
        
        tb_cols = st.columns(4)
        tenbagger_list = ["三井E&S", "石川製作所", "豊和工業", "レーザーテック"]
        for idx, stock in enumerate(tenbagger_list):
            with tb_cols[idx % 4]:
                st.button(
                    f"🔥 分析 ({stock})",
                    key=f"btn_tb_{stock}",
                    on_click=select_stock,
                    args=(stock,)
                )

    # --- タブ3：スクリーニング ---
    with tab_screening:
        st.subheader("🔍 スクリーニング・指標別一覧")
        st.write("PER/PBRや配当利回りなどのスクリーニング機能・条件検索です。")

else:
    # --- 【個別銘柄 詳細分析画面】 ---
    selected_stock_name = st.session_state["selected_stock"]
    
    st.title(f"📊 {selected_stock_name} の詳細分析・チャート")
    st.success(f"現在 **{selected_stock_name}** の詳細データを表示しています。")
    
    # 分析データ表示例
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="予想PER", value="14.2 倍")
    with col2:
        st.metric(label="PBR", value="1.15 倍")
    with col3:
        st.metric(label="配当利回り", value="3.45 %")

    st.write("---")
    st.caption("※「⬅️ 個別銘柄トップに戻る」ボタンを押すといつでも一覧に戻れます。")
