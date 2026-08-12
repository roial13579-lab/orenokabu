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

alert_history = {}

def get_session():
    try:
        return cffi_requests.Session(impersonate="chrome120")
    except Exception:
        return None

def fetch_ticker_full_analysis(ticker: str):
    """同期的に単一銘柄のデータ取得・解析を行う"""
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
            "is_overbought": is_overbought
        }
    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
        return None

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

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 1. バックグラウンド非同期監視 ---
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
        # 非同期化によりメインループを阻害しない
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

# --- 2. 市場前後の定時レポート配信 ---
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

# --- Discord ボタン操作 (タイムアウト完全回避仕様) ---
class InstitutionalBoardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚡ 板情報＆大動き動向分析", style=discord.ButtonStyle.danger, custom_id="fetch_board_breakout_perm")
    async def board_button(self, interaction: discord.Interaction, button: Button):
        # 1. 最初に即時応答（defer）を行い、Discordに処理中であることを伝えて3秒タイムアウトを回避
        await interaction.response.defer(thinking=True)
        
        all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
        report = "⚡ **【リアルタイム板情報・大口買い圧ブレイク分析】**\n\n"
        found = False

        for code in all_tickers:
            # 2. 通信・データ計算処理をスレッドに逃がしてバックグラウンド実行
            tech = await asyncio.to_thread(fetch_ticker_full_analysis, code)
            if tech and (tech['board_breakout'] or tech['bid_ask_ratio'] >= 1.4):
                found = True
                advice = get_action_advice(tech)
                report += f"🔥 **銘柄**: `{tech['code']}` | **板買い圧力**: `{tech['bid_ask_ratio']}倍`\n"
                report += f"├ **現在値**: {tech['price']}円 ({tech['change']}%) | **出来高**: `{tech['vol_ratio']}倍`\n"
                report += f"└ 🧭 **分析**: {advice}\n\n"

        if not found:
            report += "現在、板情報で売り板を急速に飲み込むような大口集中銘柄はありません。"

        # 3. 準備が整い次第、追記送信
        await interaction.followup.send(report)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.add_view(InstitutionalBoardView())
    
    if not real_time_signal_monitor.is_running():
        real_time_signal_monitor.start()
    if not scheduled_market_reports.is_running():
        scheduled_market_reports.start()

bot.run(TOKEN)
