import os
import time
import threading
import urllib.request
import asyncio
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
import yfinance as yf
from curl_cffi import requests as cffi_requests
import pandas as pd

# 日本時間 (JST)
JST = timezone(timedelta(hours=9))

# --- Render用ダミーサーバー & Self-Ping ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        pass

def run_dummy_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def keep_alive_ping():
    time.sleep(30)
    service_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not service_url:
        port = os.environ.get("PORT", "10000")
        service_url = f"http://127.0.0.1:{port}"

    while True:
        try:
            req = urllib.request.Request(
                service_url,
                headers={'User-Agent': 'Mozilla/5.0 (Render Keep-Alive Loop)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                pass
        except Exception as e:
            print(f"⚠️ [Keep-Alive] Ping failed: {e}")
        time.sleep(600)

threading.Thread(target=run_dummy_server, daemon=True).start()
threading.Thread(target=keep_alive_ping, daemon=True).start()

# --- Discord Bot 設定 ---
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", os.environ.get("TOKEN", "MTUzNTYzNjc4MzU1ODA0MTY0MA.GBw8SB.9TSIbUXCWXJZJN5tn0h3sUfKALHRFCDs4yO5Dg"))

# チャンネルIDの設定
DASHBOARD_CHANNEL_ID = int(os.environ.get("DASHBOARD_CHANNEL_ID", os.environ.get("PANEL_CHANNEL_ID", "1537090733490835498")))
GENERAL_CHANNEL_ID = int(os.environ.get("GENERAL_CHANNEL_ID", "1535613064056152247"))  # 一般チャンネル
ALERT_CHANNEL_ID = int(os.environ.get("ALERT_CHANNEL_ID", "1537090877003014226"))      # 売買アラート
REPORT_CHANNEL_ID = int(os.environ.get("REPORT_CHANNEL_ID", "1537090824834261122"))    # 定時レポート

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

SECTOR_NEWS_FACTORS = {
    "1.半導体": {
        "high": "🌐 **【米ハイテク・AI投資連動】** 米SOX指数上昇や大手ビッグテックの巨額AIインフラ需要により大口資金が集中。",
        "low": "🌐 **【米半導体株調整・規制警戒】** 米ハイテク株の利確売りや米中半導体規制強化のニュースによる警戒感。"
    },
    "2.重工防衛": {
        "high": "🌐 **【地政学リスク・防衛予算拡大】** 海外情勢の緊迫化ニュースや各国の防衛費増額方針で大口買いが加速。",
        "low": "🌐 **【材料出尽くし・ポジション調整】** 短期的な地政学ニュース沈静化に伴う利益確定売り。"
    },
    "3.自動車": {
        "high": "🌐 **【為替・円安進行ニュース】** ドル円の円安推移による輸出採算改善期待の買い。",
        "low": "🌐 **【関税懸念・円高転換】** 米貿易関税リスクや円高進行による業績圧迫懸念。"
    },
    "4.大型金融": {
        "high": "🌐 **【金利上昇・日銀利上げ観測】** 中央銀行の利上げ報道や長短金利上昇による利ざや拡大期待。",
        "low": "🌐 **【世界的な金利低下】** 世界的な景気減速懸念に伴う長期金利下落。"
    },
    "5.エネ資源": {
        "high": "🌐 **【原油/商品高騰・インフレ報道】** 中東情勢やOPEC減産による原油・天然ガス価格急伸。",
        "low": "🌐 **【世界的な原油需要減退ニュース】** 景気後退懸念に伴うエネルギー需要縮小報道。"
    },
    "6.海運物流": {
        "high": "🌐 **【地政学航路迂回・運賃高騰】** 海峡通過リスクやコンテナ運賃指数（SCFI）の急上昇報道。",
        "low": "🌐 **【海運運賃指数の下落】** 港湾混雑解消や運賃指数の調整局面。"
    },
    "7.メガテック": {
        "high": "🌐 **【生成AI・クラウド市場拡大】** 米決算発表でのクラウド・AI事業の好決算ニュース。",
        "low": "🌐 **【金利高による高PER懸念】** 米金利上昇によるバリュエーション高値警戒感。"
    },
    "8.商社流通": {
        "high": "🌐 **【バフェット氏買い増し・株主還元】** 海外投資家からの日本株再評価＆資源高の好影響。",
        "low": "🌐 **【資源価格一服・為替評価損】** 商品市況の沈静化による利益押し下げ。"
    },
    "9.医薬バイオ": {
        "high": "🌐 **【ディフェンシブ逃避・新薬承認ニュース】** 市場全般の波乱時における安全資産としての逃避買い。",
        "low": "🌐 **【薬価改定・他成長セクターへの資金移動】** リスクオン局面での資金流出。"
    },
    "10.電気精密": {
        "high": "🌐 **【産業機器・FA機器需要回復】** 世界的な設備投資再開ニュースやパワー半導体需要。",
        "low": "🌐 **【中国景気減速ニュース】** 中華圏向けファクトリーオートメーション需要の停滞。"
    }
}

DATA_CACHE = {}
LAST_CACHE_TIME = None
alert_history = {}

def get_session():
    try:
        return cffi_requests.Session(impersonate="chrome120")
    except Exception:
        return None

def fetch_ticker_full_analysis(ticker: str):
    try:
        session = get_session()
        ticker_obj = yf.Ticker(ticker, session=session) if session else yf.Ticker(ticker)
        
        df = ticker_obj.history(period="6mo", interval="1d")
        if df.empty or len(df['Close']) < 30:
            df = yf.Ticker(ticker).history(period="6mo", interval="1d")
            if df.empty or len(df['Close']) < 30:
                return None

        close = df['Close'].dropna()
        volume = df['Volume'].dropna() if 'Volume' in df else pd.Series()
        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2]) if len(close) >= 2 else current_price
        day_change = round(((current_price - prev_price) / prev_price) * 100, 2)

        past_20d_high = close.iloc[-21:-1].max() if len(close) >= 21 else close.max()
        is_20d_high_breakout = current_price > past_20d_high

        sma5 = close.rolling(window=5).mean()
        sma25 = close.rolling(window=25).mean()
        sma75 = close.rolling(window=75).mean() if len(close) >= 75 else sma25
        
        bias25 = round(((current_price - sma25.iloc[-1]) / sma25.iloc[-1]) * 100, 1) if sma25.iloc[-1] != 0 else 0
        perfect_order = (sma5.iloc[-1] > sma25.iloc[-1]) and (sma25.iloc[-1] > sma75.iloc[-1])
        is_gc = (sma5.iloc[-2] <= sma25.iloc[-2]) and (sma5.iloc[-1] > sma25.iloc[-1])

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        last_loss = loss.iloc[-1] if not loss.empty else 0
        rsi = round(100.0 if last_loss == 0 else 100 - (100 / (1 + (gain.iloc[-1] / last_loss))), 1)

        exp12 = close.ewm(span=12, adjust=False).mean()
        exp26 = close.ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_gc = (macd.iloc[-2] <= signal.iloc[-2]) and (macd.iloc[-1] > signal.iloc[-1])

        std25 = close.rolling(window=25).std()
        upper_band = sma25 + (std25 * 2)
        lower_band = sma25 - (std25 * 2)
        bb_breakout = current_price > upper_band.iloc[-1]
        bb_oversold = current_price < lower_band.iloc[-1]

        vol_ma = volume.rolling(window=25).mean().iloc[-1] if len(volume) >= 25 else 0
        vol_ratio = round((volume.iloc[-1] / vol_ma), 2) if vol_ma > 0 else 1.0
        vol_spike = vol_ratio >= 1.8

        bid_ask_ratio = 1.0
        per, roe, revenue_growth = "N/A", "N/A", "N/A"
        is_tenbagger = False

        try:
            info = ticker_obj.info or {}
            bid = info.get("bidSize", 0)
            ask = info.get("askSize", 0)
            if bid and ask and ask > 0:
                bid_ask_ratio = round(bid / ask, 2)
            else:
                bid_ask_ratio = round(vol_ratio * (1.2 if current_price > prev_price else 0.8), 2)

            per_val = info.get("trailingPE") or info.get("forwardPE")
            roe_val = info.get("returnOnEquity")
            rev_val = info.get("revenueGrowth")
            mcap = info.get("marketCap")
            
            if per_val: per = round(float(per_val), 1)
            if roe_val: roe = round(float(roe_val * 100), 1)
            if rev_val: revenue_growth = round(float(rev_val * 100), 1)
            
            mcap_ok = (mcap / 1e8 < 1000) if (mcap and ticker.endswith(".T")) else True
            is_tenbagger = mcap_ok and (rev_val and rev_val >= 0.2) and (roe_val and roe_val >= 0.15)
        except Exception:
            pass

        board_breakout_imminent = (bid_ask_ratio >= 1.5) and vol_spike
        is_dip = (rsi <= 38 or bb_oversold) or (bias25 <= -5.0)
        is_overbought = (rsi >= 70) or (bias25 >= 15.0)

        return {
            "code": ticker.replace(".T", ""),
            "price": current_price,
            "change": day_change,
            "bias": bias25,
            "rsi": rsi,
            "vol_ratio": vol_ratio,
            "vol_spike": vol_spike,
            "is_gc": is_gc,
            "macd_gc": macd_gc,
            "perfect_order": perfect_order,
            "bb_breakout": bb_breakout,
            "bb_oversold": bb_oversold,
            "is_high_breakout": is_20d_high_breakout,
            "bid_ask_ratio": bid_ask_ratio,
            "board_breakout": board_breakout_imminent,
            "is_dip": is_dip,
            "is_overbought": is_overbought,
            "is_tenbagger": is_tenbagger,
            "per": per,
            "roe": roe,
            "rev_growth": revenue_growth
        }
    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
        return None

def refresh_all_cache():
    global DATA_CACHE, LAST_CACHE_TIME
    all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
    new_data = {}
    for code in all_tickers:
        tech = fetch_ticker_full_analysis(code)
        if tech:
            new_data[code] = tech
        time.sleep(0.05)
    
    if new_data:
        DATA_CACHE = new_data
        LAST_CACHE_TIME = datetime.now(JST)

def get_action_advice(tech):
    if tech['is_overbought'] or (tech['bias'] >= 18.0):
        return "🔴 **【利確・一部売却】** 高値過熱感あり。利益確定売りや押し目待ちを推奨。"
    elif tech['board_breakout'] or tech['is_high_breakout']:
        return "🚀 **【新規買い / 買い増し】** 大口買い上昇ブレイク！順張りエントリー好好機。"
    elif tech['is_dip'] or tech['is_gc'] or tech['macd_gc']:
        return "🟢 **【新規買い（打診買い）】** 売られ過ぎ反発・トレンド転換初動。買い場到来。"
    elif tech['perfect_order']:
        return "🔥 **【ホールド（継続保有）】** パーフェクトオーダー形成中。利益伸長を狙い維持。"
    else:
        return "🟡 **【ホールド / 様子見】** 明確な方向感模索中。静観または既存ポジション維持。"

# ★必ず「#一般」チャンネルへ送信するためのヘルパー関数
async def send_to_general_channel(interaction: discord.Interaction, full_text: str):
    # 送信先の「一般」チャンネルを取得
    target_channel = bot.get_channel(GENERAL_CHANNEL_ID) if GENERAL_CHANNEL_ID else interaction.channel

    chunks = []
    curr_chunk = ""
    for line in full_text.split("\n"):
        if len(curr_chunk) + len(line) + 1 > 1900:
            chunks.append(curr_chunk)
            curr_chunk = line + "\n"
        else:
            curr_chunk += line + "\n"
    if curr_chunk:
        chunks.append(curr_chunk)

    # 一般チャンネルへメッセージを分割送信
    for chunk in chunks:
        await target_channel.send(chunk)

    # ダッシュボード上で押したユーザーには、自分だけに見えるメッセージで完了通知
    channel_mention = target_channel.mention if hasattr(target_channel, 'mention') else "一般"
    await interaction.followup.send(f"✅ {channel_mention} チャンネルに解析結果を送信しました！", ephemeral=True)

def analyze_single_ticker(code_input: str):
    code_input = code_input.upper().strip()
    ticker = f"{code_input}.T" if code_input.isdigit() and len(code_input) == 4 else code_input
    tech = fetch_ticker_full_analysis(ticker)
    if tech:
        status_str = "⚡ レンジ推移"
        if tech['board_breakout']: status_str = "⚡ **大口買い集中・板上放れ**"
        elif tech['is_high_breakout']: status_str = "🚀 **直近20日高値ブレイク**"
        elif tech['is_dip']: status_str = "🎯 **過小評価・押し目シグナル**"
        elif tech['perfect_order'] and tech['vol_spike']: status_str = "🔥 **大商い・上昇パーフェクトオーダー**"
        elif tech['bb_breakout']: status_str = "🚀 **ボリンジャー+2σ突破**"
        elif tech['is_gc'] or tech['macd_gc']: status_str = "✅ **ゴールデンクロス**"

        advice = get_action_advice(tech)
        gc_str = "✅ クロス発生" if (tech['is_gc'] or tech['macd_gc']) else "➖ なし"
        vol_str = f"🔥 {tech['vol_ratio']}倍 (急増)" if tech['vol_spike'] else f"{tech['vol_ratio']}倍"

        return (
            f"📊 **【テクニカル・板解析】`{code_input}`**\n"
            f"├ **現在値**: {tech['price']}円 ({tech['change']}%)\n"
            f"├ **板買い圧力**: `{tech['bid_ask_ratio']}倍` | **出来高比**: {vol_str}\n"
            f"├ **25日移動平均乖離**: {tech['bias']}% | **RSI**: {tech['rsi']}%\n"
            f"├ **シグナル**: {status_str} (GC: {gc_str})\n"
            f"├ **指標**: PER `{tech['per']}倍` | ROE `{tech['roe']}%` | 増収率 `{tech['rev_growth']}%` \n"
            f"└ 💡 **アクション指針**: {advice}"
        )
    else:
        return f"⚠️ `{code_input}` のデータを取得できませんでした。"

class StockSearchModal(Modal, title="銘柄テクニカル＆板情報検索"):
    stock_code = TextInput(
        label="銘柄コード または ティッカーを入力",
        placeholder="例: 7011, 8035, NVDA",
        min_length=1,
        max_length=10,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        res_msg = await asyncio.to_thread(analyze_single_ticker, self.stock_code.value)
        await send_to_general_channel(interaction, res_msg)

class InstitutionalBoardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔍 銘柄詳細解析", style=discord.ButtonStyle.success, custom_id="search_stock_modal_perm")
    async def search_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockSearchModal())

    @discord.ui.button(label="🌐 各業界 ニュース・資金動向", style=discord.ButtonStyle.primary, custom_id="fetch_sector_flow_perm")
    async def sector_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        
        full_report = "📊 **【10大業界 世界ニュース・マクロ要因別 資金流入力学】**\n"
        if LAST_CACHE_TIME:
            full_report += f"⏱️ データ更新時刻: {LAST_CACHE_TIME.strftime('%H:%M:%S')}\n\n"

        sector_scores = {}

        for sector_name, tickers in SECTORS.items():
            full_report += f"**🔹 {sector_name}**\n"
            line_items = []
            scores = []
            for code in tickers:
                tech = DATA_CACHE.get(code)
                clean_code = code.replace('.T','')
                if tech:
                    score = min(max(int(
                        (tech['vol_ratio'] * 25) + 
                        (tech['rsi'] * 0.4) + 
                        (15 if tech['is_gc'] or tech['macd_gc'] else 0) +
                        (15 if tech['is_high_breakout'] else 0)
                    ), 10), 100)
                    scores.append(score)
                    status = "🔥" if score >= 65 else ("⚡" if score >= 40 else "🔻")
                    line_items.append(f"`{clean_code}`:{status}{score}点")
                else:
                    line_items.append(f"`{clean_code}`:取得中")
            
            avg_score = int(sum(scores) / len(scores)) if scores else 50
            sector_scores[sector_name] = avg_score
            news_info = SECTOR_NEWS_FACTORS.get(sector_name, {"high": "ニュース連動買い。", "low": "利確・調整売り。"})
            reason_str = news_info["high"] if avg_score >= 50 else news_info["low"]

            full_report += "> " + " | ".join(line_items) + f"\n"
            full_report += f"├ **資金流入スコア**: `{avg_score}点`\n"
            full_report += f"└ 🧠 **背景ニュース・要因**: {reason_str}\n\n"

        sorted_sectors = sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)
        top_sector = sorted_sectors[0] if sorted_sectors else ("なし", 0)
        bottom_sector = sorted_sectors[-1] if sorted_sectors else ("なし", 0)

        full_report += "📈 **【業界動向サマリー】**\n"
        full_report += f"├ 🔥 **最高資金流入**: **{top_sector[0]}** (`{top_sector[1]}点`)\n"
        full_report += f"└ 🔻 **最不振セクター**: **{bottom_sector[0]}** (`{bottom_sector[1]}点`)"

        await send_to_general_channel(interaction, full_report)

    @discord.ui.button(label="🎯 押し目・高値突破シグナル", style=discord.ButtonStyle.secondary, custom_id="fetch_dip_signals_perm")
    async def dip_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        report = "🎯 **【過去データ対比 注目シグナル抽出銘柄】**\n\n"
        found_count = 0
        for code, tech in DATA_CACHE.items():
            if tech and (tech['is_dip'] or tech['is_gc'] or tech['macd_gc'] or tech['bb_breakout'] or tech['is_high_breakout'] or tech['is_tenbagger']):
                found_count += 1
                signals = []
                if tech['is_high_breakout']: signals.append("直近高値突破")
                if tech['is_dip']: signals.append("過去反発点(売られ過ぎ)")
                if tech['perfect_order']: signals.append("上昇パーフェクトオーダー")
                if tech['is_gc'] or tech['macd_gc']: signals.append("ゴールデンクロス")
                if tech['bb_breakout']: signals.append("+2σブレイク")

                advice = get_action_advice(tech)
                clean_code = code.replace('.T','')
                report += f"💡 **銘柄**: `{clean_code}` | **シグナル**: {', '.join(signals)}\n"
                report += f"├ **現在値**: {tech['price']}円 ({tech['change']}%) | **出来高過去比**: `{tech['vol_ratio']}倍`\n"
                report += f"└ 🧭 **アクション指針**: {advice}\n\n"
        
        if found_count == 0:
            report += "現在、明確なシグナル条件に合致する銘柄はありません。"
        
        await send_to_general_channel(interaction, report)

    @discord.ui.button(label="⚡ 大口売買・板突破動向", style=discord.ButtonStyle.danger, custom_id="fetch_board_breakout_perm")
    async def board_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        report = "⚡ **【大口買い集中・板急変分析】**\n\n"
        found = False

        for code, tech in DATA_CACHE.items():
            if tech and (tech['board_breakout'] or tech['bid_ask_ratio'] >= 1.3 or tech['vol_spike']):
                found = True
                advice = get_action_advice(tech)
                report += f"🔥 **銘柄**: `{tech['code']}` | **板買い圧力**: `{tech['bid_ask_ratio']}倍`\n"
                report += f"├ **現在値**: {tech['price']}円 ({tech['change']}%) | **出来高過去比**: `{tech['vol_ratio']}倍`\n"
                report += f"└ 🧭 **アクション指針**: {advice}\n\n"

        if not found:
            report += "現在、大口の買いが急増している銘柄はありません。"

        await send_to_general_channel(interaction, report)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- パネルの自動固定関数 ---
async def ensure_dashboard_panel():
    if not DASHBOARD_CHANNEL_ID:
        return
    channel = bot.get_channel(DASHBOARD_CHANNEL_ID)
    if not channel:
        return
    try:
        # ダッシュボード内の全メッセージをクリアしてボタンのみ再構築
        await channel.purge(limit=20)
    except Exception:
        pass

    view = InstitutionalBoardView()
    await channel.send(
        "📌 **【常設ダッシュボード】株式機関投資分析・イベント予測 Bot**\n"
        "ボタンを押すと、最新の解析結果が **#一般** チャンネルへ送信されます。\n"
        "※ `🔍 銘柄詳細解析` ボタンで個別検索も可能です。",
        view=view
    )

# --- バックグラウンド監視（「#売買アラート」へ送信） ---
@tasks.loop(minutes=10)
async def real_time_signal_monitor():
    await bot.wait_until_ready()
    await asyncio.to_thread(refresh_all_cache)

    channel = bot.get_channel(ALERT_CHANNEL_ID)
    if not channel:
        return

    now = datetime.now(JST)
    if now.weekday() >= 5:
        return

    for code, tech in DATA_CACHE.items():
        if not tech:
            continue

        clean_code = tech['code']
        last_time = alert_history.get(clean_code)
        if last_time and (now - last_time).total_seconds() < 10800:
            continue

        triggered = False
        signal_title = ""

        if tech['board_breakout']:
            triggered = True
            signal_title = "⚡ 【大口売買急変】板買い集中＆上放れ直前"
        elif tech['is_high_breakout']:
            triggered = True
            signal_title = "🚀 【直近高値突破】最高値を上抜け"
        elif tech['perfect_order'] and tech['vol_spike']:
            triggered = True
            signal_title = "🔥 【大商いトレンド】出来高急増＋完全上昇配列"

        if triggered:
            alert_history[clean_code] = now
            advice = get_action_advice(tech)
            
            msg = (
                f"🚨 **【自動検知】売買動作アラート** 🚨\n"
                f"📌 **{signal_title}**\n"
                f"├ **銘柄**: `{clean_code}` | **現在値**: {tech['price']}円 ({tech['change']}%)\n"
                f"├ **板買い圧力**: `{tech['bid_ask_ratio']}倍` | **出来高過去比**: `{tech['vol_ratio']}倍`\n"
                f"└ 🧭 **アクション指針**: {advice}"
            )
            await channel.send(msg)

# --- 市場前後の定時レポート（「#定時レポート」へ送信） ---
@tasks.loop(minutes=1)
async def scheduled_market_reports():
    await bot.wait_until_ready()
    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not channel:
        return

    now = datetime.now(JST)
    if now.weekday() >= 5:
        return

    time_str = now.strftime("%H:%M")

    if time_str == "08:45":
        board_candidates = [t for t in DATA_CACHE.values() if t and (t['bid_ask_ratio'] >= 1.3 or t['vol_spike'])]
        msg = "🌅 **【寄り付き前 気配＆世界ニュース連動チェック】**\n"
        msg += f"📅 日時: {now.strftime('%Y-%m-%d')} 08:45\n\n"
        if board_candidates:
            for t in board_candidates[:5]:
                msg += f"├ `{t['code']}` | 板買い圧力 `{t['bid_ask_ratio']}倍` | 前日比 `{t['change']}%`\n"
        else:
            msg += "├ 特筆すべき異常気配は現在検出されていません。\n"
        await channel.send(msg)

    if time_str == "15:30":
        tech_results = [t for t in DATA_CACHE.values() if t]
        tech_results.sort(key=lambda x: x['change'], reverse=True)
        top_gainers = tech_results[:3]
        msg = "🌇 **【大引け後 市場総括レポート】**\n"
        msg += f"📅 日時: {now.strftime('%Y-%m-%d')} 15:30\n\n"
        msg += "📈 **本日の上昇トップ3:**\n"
        for t in top_gainers:
            msg += f"├ `{t['code']}`: **+{t['change']}%** (現在値: {t['price']}円)\n"
        await channel.send(msg)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.add_view(InstitutionalBoardView())
    await ensure_dashboard_panel()
    if not real_time_signal_monitor.is_running():
        real_time_signal_monitor.start()
    if not scheduled_market_reports.is_running():
        scheduled_market_reports.start()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    text = message.content.strip()

    if text in ["!k", "!panel", "！ｋ", "！ｐａｎｅｌ"]:
        await ensure_dashboard_panel()
        return

    if text.startswith("!c ") or text.startswith("!check "):
        parts = text.split()
        if len(parts) >= 2:
            async with message.channel.typing():
                res_msg = await asyncio.to_thread(analyze_single_ticker, parts[1])
                target_channel = bot.get_channel(GENERAL_CHANNEL_ID) if GENERAL_CHANNEL_ID else message.channel
                await target_channel.send(res_msg)
        return

    await bot.process_commands(message)

bot.run(TOKEN)
