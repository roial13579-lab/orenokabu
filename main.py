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
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "MTUzNTYzNjc4MzU1ODA0MTY0MA.GBw8SB.9TSIbUXCWXJZJN5tn0h3sUfKALHRFCDs4yO5Dg")
PANEL_CHANNEL_ID = int(os.environ.get("PANEL_CHANNEL_ID", "1535613064056152247"))

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

SECTOR_MACRO_FACTORS = {
    "1.半導体": {"high": "AIインフラ需要増・先端プロセス需給ひっ迫により資金集中。", "low": "米ハイテク株調整や利益確定売り進行。"},
    "2.重工防衛": {"high": "防衛予算拡大期待や地政学リスク高まりで防衛・重機へ資金流入。", "low": "短期的材料出尽くし感による一時的ポジション調整。"},
    "3.自動車": {"high": "為替の円安推移や輸出採算改善を見込んだ買い。", "low": "円高進行懸念や関税・貿易摩擦による警戒感。"},
    "4.大型金融": {"high": "日銀利上げ観測に伴う貸出利ざや改善期待。", "low": "金利上昇が一服し利益確定売り。"},
    "5.エネ資源": {"high": "原油・天然ガス価格の高騰やインフレヘッジでの買い。", "low": "世界的な景気減速懸念による原油・商品需要減退。"},
    "6.海運物流": {"high": "地政学上の航路回航問題や運賃指数上昇。", "low": "運賃指数の下落や燃料コスト増加懸念。"},
    "7.メガテック": {"high": "クラウド・生成AI需要拡大や株主還元姿勢を好感。", "low": "高PER株からの資金シフトやIT投資回収速度懸念。"},
    "8.商社流通": {"high": "高配当・自社株買いなどの株主還元強化で買い。", "low": "資源価格一服や円高転換による目減り懸念。"},
    "9.医薬バイオ": {"high": "ディフェンシブ資産としての逃避買い。", "low": "薬価改定リスクや他セクターへの資金移動。"},
    "10.電気精密": {"high": "産業用機器・パワー半導体需要の回復期待。", "low": "中国市場での設備投資停滞懸念。"}
}

alert_history = {}

def get_session():
    try:
        return cffi_requests.Session(impersonate="chrome120")
    except Exception:
        return None

def fetch_ticker_full_analysis(ticker: str):
    """単一銘柄のデータ取得・解析"""
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
        try:
            info = ticker_obj.info or {}
            bid = info.get("bidSize", 0)
            ask = info.get("askSize", 0)
            if bid and ask and ask > 0:
                bid_ask_ratio = round(bid / ask, 2)
            else:
                bid_ask_ratio = round(vol_ratio * (1.2 if current_price > prev_price else 0.8), 2)
        except Exception:
            pass

        board_breakout_imminent = (bid_ask_ratio >= 1.5) and vol_spike
        is_dip = (rsi <= 35 or bb_oversold) and (bias25 <= -5.0)
        is_overbought = (rsi >= 72) or (bias25 >= 15.0)

        # 10倍株適性チェック（安全なフォールバック付き）
        per, roe, revenue_growth = "N/A", "N/A", "N/A"
        is_tenbagger = False
        try:
            info = ticker_obj.info or {}
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

def fetch_all_sync():
    """全銘柄を一括取得する同期関数"""
    all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
    results = {}
    for code in all_tickers:
        tech = fetch_ticker_full_analysis(code)
        if tech:
            results[code] = tech
        time.sleep(0.05)
    return results

def get_action_advice(tech):
    if tech['board_breakout']:
        return "⚡ **【大口板買い集中】** 板が極めて薄く上放れ直前。追随買い検討。"
    elif tech['is_dip']:
        return "🟢 **【打診買い】** 売られ過ぎからの反発ポイント。"
    elif tech['perfect_order'] and tech['vol_spike']:
        return "🔥 **【強気追随】** パーフェクトオーダー ＋ 大商い。"
    elif tech['bb_breakout']:
        return "🚀 **【ブレイク買い / 利確準備】** +2σ突破。"
    elif tech['is_gc'] or tech['macd_gc']:
        return "✅ **【トレンド転換】** ゴールデンクロス発生。"
    elif tech['is_overbought']:
        return "🔴 **【高値警戒】** RSI高値圏。利確考慮。"
    else:
        return "🟡 **【様子見】** 明確なシグナル待ち。"

def analyze_single_ticker(code_input: str):
    code_input = code_input.upper().strip()
    ticker = f"{code_input}.T" if code_input.isdigit() and len(code_input) == 4 else code_input
    tech = fetch_ticker_full_analysis(ticker)
    if tech:
        status_str = "⚡ レンジ推移"
        if tech['board_breakout']: status_str = "⚡ **板情報大口ブレイク直前**"
        elif tech['is_dip']: status_str = "🎯 **押し目買いシグナル**"
        elif tech['perfect_order'] and tech['vol_spike']: status_str = "🔥 **大商い・上昇パーフェクトオーダー**"
        elif tech['bb_breakout']: status_str = "🚀 **ボリンジャー+2σブレイク**"
        elif tech['is_gc'] or tech['macd_gc']: status_str = "✅ **トレンド転換ゴールデンクロス**"
        elif tech['is_overbought']: status_str = "⚠️ **過熱警戒（買われ過ぎ）**"

        advice = get_action_advice(tech)
        gc_str = "✅ MA/MACDクロス" if (tech['is_gc'] or tech['macd_gc']) else "➖ なし"
        po_str = "🔥 完全上昇配列" if tech['perfect_order'] else "➖ 通常"
        vol_str = f"🔥 {tech['vol_ratio']}倍 (急増)" if tech['vol_spike'] else f"{tech['vol_ratio']}倍"

        return (
            f"📊 **【最新リアルタイム多角解析】`{code_input}`**\n"
            f"├ **現在値**: {tech['price']}円 ({tech['change']}%)\n"
            f"├ **板買い圧力倍率**: `{tech['bid_ask_ratio']}倍`\n"
            f"├ **移動平均(25日乖離)**: {tech['bias']}%\n"
            f"├ **移動平均配列**: {po_str}\n"
            f"├ **RSI(14日)**: {tech['rsi']}%\n"
            f"├ **ゴールデンクロス**: {gc_str}\n"
            f"├ **出来高倍率**: {vol_str}\n"
            f"├ **指標**: PER `{tech['per']}倍` | ROE `{tech['roe']}%` | 増収率 `{tech['rev_growth']}%` \n"
            f"├ **総合判定**: {status_str}\n"
            f"└ 💡 **アクション指針**: {advice}"
        )
    else:
        return f"⚠️ `{code_input}` の最新データを取得できませんでした。"

class StockSearchModal(Modal, title="銘柄テクニカル＆板情報検索"):
    stock_code = TextInput(
        label="銘柄コード または ティッカーを入力",
        placeholder="例: 7011, 8035, NVDA",
        min_length=1,
        max_length=10,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        res_msg = await asyncio.to_thread(analyze_single_ticker, self.stock_code.value)
        await interaction.followup.send(res_msg)

class InstitutionalBoardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔍 銘柄詳細解析", style=discord.ButtonStyle.success, custom_id="search_stock_modal_perm")
    async def search_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockSearchModal())

    @discord.ui.button(label="🌐 各業界 資金流入力学", style=discord.ButtonStyle.primary, custom_id="fetch_sector_flow_perm")
    async def sector_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        tech_data = await asyncio.to_thread(fetch_all_sync)
        
        full_report = "📊 **【全10セクター リアルタイム資金流入力学・変動要因レポート】**\n\n"
        sector_scores = {}

        for sector_name, tickers in SECTORS.items():
            full_report += f"**🔹 {sector_name}**\n"
            line_items = []
            scores = []
            for code in tickers:
                tech = tech_data.get(code)
                clean_code = code.replace('.T','')
                if tech:
                    score = min(max(int(
                        (tech['vol_ratio'] * 25) + 
                        (tech['rsi'] * 0.4) + 
                        (15 if tech['is_gc'] or tech['macd_gc'] else 0) +
                        (15 if tech['perfect_order'] else 0)
                    ), 10), 100)
                    scores.append(score)
                    status = "🔥" if score >= 65 else ("⚡" if score >= 40 else "🔻")
                    line_items.append(f"`{clean_code}`:{status}{score}点")
                else:
                    line_items.append(f"`{clean_code}`:取得中")
            
            avg_score = int(sum(scores) / len(scores)) if scores else 0
            sector_scores[sector_name] = avg_score
            macro_info = SECTOR_MACRO_FACTORS.get(sector_name, {"high": "需要拡大期待。", "low": "利確・調整売り。"})
            reason_str = macro_info["high"] if avg_score >= 50 else macro_info["low"]

            full_report += "> " + " | ".join(line_items) + f"\n"
            full_report += f"├ **セクター勢い**: `{avg_score}点`\n"
            full_report += f"└ 🧠 **変動要因分析**: {reason_str}\n\n"

        sorted_sectors = sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)
        top_sector = sorted_sectors[0] if sorted_sectors else ("なし", 0)
        bottom_sector = sorted_sectors[-1] if sorted_sectors else ("なし", 0)

        full_report += "📈 **【リアルタイム全般の資金流入力学サマリー】**\n"
        full_report += f"├ 🔥 **最大資金流入**: **{top_sector[0]}** (`{top_sector[1]}点`)\n"
        full_report += f"├ 🔻 **最不振セクター**: **{bottom_sector[0]}** (`{bottom_sector[1]}点`)\n"
        full_report += f"└ 🧭 **立ち回り**: 「{top_sector[0]}」への順張り、または「{bottom_sector[0]}」の反発狙いが有効です。\n"

        await interaction.followup.send(full_report)

    @discord.ui.button(label="🎯 押し目・買われ過ぎシグナル", style=discord.ButtonStyle.secondary, custom_id="fetch_dip_signals_perm")
    async def dip_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        tech_data = await asyncio.to_thread(fetch_all_sync)
        report = "🎯 **【リアルタイム抽出 注目銘柄・テクニカルシグナル】**\n\n"
        found_count = 0
        for code, tech in tech_data.items():
            if tech and (tech['is_dip'] or tech['is_gc'] or tech['macd_gc'] or tech['bb_breakout'] or tech['perfect_order'] or tech['is_tenbagger']):
                found_count += 1
                signals = []
                if tech['is_dip']: signals.append("押し目(売られ過ぎ)")
                if tech['perfect_order']: signals.append("上昇パーフェクトオーダー")
                if tech['is_gc'] or tech['macd_gc']: signals.append("ゴールデンクロス")
                if tech['bb_breakout']: signals.append("+2σブレイク")
                if tech['is_tenbagger']: signals.append("10倍株財務通過")

                advice = get_action_advice(tech)
                clean_code = code.replace('.T','')
                report += f"💡 **銘柄**: `{clean_code}` | **シグナル**: {', '.join(signals)}\n"
                report += f"├ **現在値**: {tech['price']}円 ({tech['change']}%) | **RSI**: {tech['rsi']}%\n"
                report += f"└ 🧭 **アクション指針**: {advice}\n\n"
        
        if found_count == 0:
            report += "現在、明確なシグナル条件に合致する注目銘柄はありません。"
        
        await interaction.followup.send(report)

    @discord.ui.button(label="⚡ 板情報＆大動き動向分析", style=discord.ButtonStyle.danger, custom_id="fetch_board_breakout_perm")
    async def board_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        tech_data = await asyncio.to_thread(fetch_all_sync)
        report = "⚡ **【リアルタイム板情報・大口買い圧ブレイク分析】**\n\n"
        found = False

        for code, tech in tech_data.items():
            if tech and (tech['board_breakout'] or tech['bid_ask_ratio'] >= 1.4):
                found = True
                advice = get_action_advice(tech)
                report += f"🔥 **銘柄**: `{tech['code']}` | **板買い圧力**: `{tech['bid_ask_ratio']}倍`\n"
                report += f"├ **現在値**: {tech['price']}円 ({tech['change']}%) | **出来高**: `{tech['vol_ratio']}倍`\n"
                report += f"└ 🧭 **分析**: {advice}\n\n"

        if not found:
            report += "現在、板情報で売り板を急速に飲み込むような大口集中銘柄はありません。"

        await interaction.followup.send(report)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- バックグラウンド非同期監視 ---
@tasks.loop(minutes=10)
async def real_time_signal_monitor():
    await bot.wait_until_ready()
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if not channel:
        return

    now = datetime.now(JST)
    if now.weekday() >= 5:
        return

    all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
    for code in all_tickers:
        tech = await asyncio.to_thread(fetch_ticker_full_analysis, code)
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
            signal_title = "⚡ 【板情報急変】大口買い注文集中＆上放れ直前"
        elif tech['perfect_order'] and tech['vol_spike']:
            triggered = True
            signal_title = "🔥 【上昇パーフェクトオーダー】出来高急増で上昇トレンド突入"
        elif tech['macd_gc'] or tech['is_gc']:
            triggered = True
            signal_title = "✅ 【ゴールデンクロス発生】転換初動シグナル"
        elif tech['is_dip']:
            triggered = True
            signal_title = "🎯 【絶好の押し目】自律反発期待ゾーン到達"

        if triggered:
            alert_history[clean_code] = now
            advice = get_action_advice(tech)
            
            msg = (
                f"🚨 **リアルタイム・テクニカルシグナル発報** 🚨\n"
                f"📌 **{signal_title}**\n"
                f"├ **銘柄**: `{clean_code}` | **現在値**: {tech['price']}円 ({tech['change']}%)\n"
                f"├ **板買い圧力倍率**: `{tech['bid_ask_ratio']}倍` | **出来高**: `{tech['vol_ratio']}倍`\n"
                f"├ **RSI**: {tech['rsi']}% | **25日乖離**: {tech['bias']}%\n"
                f"└ 🧭 **推奨アクション**: {advice}"
            )
            await channel.send(msg)
        await asyncio.sleep(0.1)

# --- 市場前後の定時レポート配信 ---
@tasks.loop(minutes=1)
async def scheduled_market_reports():
    await bot.wait_until_ready()
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if not channel:
        return

    now = datetime.now(JST)
    if now.weekday() >= 5:
        return

    time_str = now.strftime("%H:%M")

    if time_str == "08:45":
        all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
        board_candidates = []
        for code in all_tickers:
            tech = await asyncio.to_thread(fetch_ticker_full_analysis, code)
            if tech and (tech['bid_ask_ratio'] >= 1.3 or tech['vol_spike']):
                board_candidates.append(tech)

        msg = "🌅 **【市場寄り付き前 ストラテジー＆気配板ピックアップ】**\n"
        msg += f"📅 日時: {now.strftime('%Y-%m-%d')} 08:45\n\n"
        msg += "📊 **本日板情報・気配値で大動きが予想される銘柄:**\n"
        
        if board_candidates:
            for t in board_candidates[:5]:
                msg += f"├ `{t['code']}` | 板買い圧力 `{t['bid_ask_ratio']}倍` | 前日比 `{t['change']}%`\n"
        else:
            msg += "├ 特筆すべき異常気配は現在検出されていません。\n"
            
        msg += "\n🧭 **本日の立ち回り**: 寄付き直後の出来高急増銘柄に絞り、板の売り圧力が薄い方向への順張りが有効です。"
        await channel.send(msg)

    if time_str == "15:30":
        all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
        tech_results = []
        for code in all_tickers:
            tech = await asyncio.to_thread(fetch_ticker_full_analysis, code)
            if tech:
                tech_results.append(tech)

        tech_results.sort(key=lambda x: x['change'], reverse=True)
        top_gainers = tech_results[:3]
        top_losers = tech_results[-3:]

        msg = "🌇 **【大引け後 市場総合評価＆明日への分析レポート】**\n"
        msg += f"📅 日時: {now.strftime('%Y-%m-%d')} 15:30 本日の取引終了\n\n"
        
        msg += "📈 **本日上昇モメンタムトップ3:**\n"
        for t in top_gainers:
            msg += f"├ `{t['code']}`: **+{t['change']}%** (現在値: {t['price']}円 | 出来高 `{t['vol_ratio']}倍`)\n"
            
        msg += "\n📉 **本日調整・下落トップ3:**\n"
        for t in top_losers:
            msg += f"├ `{t['code']}`: **{t['change']}%** (現在値: {t['price']}円 | RSI: `{t['rsi']}%`)\n"

        msg += "\n🔮 **明日以降の注目判定**: 本日出来高を伴って+2σを突破した銘柄はトレンド継続、RSI30以下の銘柄はリバウンド狙いの買い候補となります。"
        await channel.send(msg)

async def send_or_move_panel(channel):
    if not channel:
        return
    try:
        async for msg in channel.history(limit=15):
            if msg.author == bot.user and "常設ダッシュボード" in msg.content:
                await msg.delete()
    except Exception:
        pass

    view = InstitutionalBoardView()
    await channel.send(
        "📌 **【常設ダッシュボード】株式機関投資分析・イベント予測 Bot**\n"
        "以下のボタンを押すと、リアルタイム解析を実行してレポートを出力します。\n"
        "※ `🔍 銘柄詳細解析` ボタンを押すか、`!c 銘柄コード` で個別にチェックできます。",
        view=view
    )

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.add_view(InstitutionalBoardView())
    
    target_channel = bot.get_channel(PANEL_CHANNEL_ID) if PANEL_CHANNEL_ID != 0 else None
    if target_channel:
        await send_or_move_panel(target_channel)
        
    if not real_time_signal_monitor.is_running():
        real_time_signal_monitor.start()
    if not scheduled_market_reports.is_running():
        scheduled_market_reports.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    text = message.content.strip()

    if text in ["!k", "!panel", "！ｋ", "！ｐａｎｅｌ"]:
        await send_or_move_panel(message.channel)
        return

    if text.startswith("!c ") or text.startswith("!check "):
        parts = text.split()
        if len(parts) >= 2:
            async with message.channel.typing():
                res_msg = await asyncio.to_thread(analyze_single_ticker, parts[1])
                await message.channel.send(res_msg)
        return

    await bot.process_commands(message)

bot.run(TOKEN)
