import os
import time
import re
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
import numpy as np
import requests
from bs4 import BeautifulSoup

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
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", os.environ.get("TOKEN", ""))

DASHBOARD_CHANNEL_ID = int(os.environ.get("DASHBOARD_CHANNEL_ID", os.environ.get("PANEL_CHANNEL_ID", "0")))
GENERAL_CHANNEL_ID = int(os.environ.get("GENERAL_CHANNEL_ID", "0"))
ALERT_CHANNEL_ID = int(os.environ.get("ALERT_CHANNEL_ID", "0"))
REPORT_CHANNEL_ID = int(os.environ.get("REPORT_CHANNEL_ID", "0"))

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
    "1.半導体": {"high": "🌐 米SOX指数上昇やAI需要による大口資金流入。", "low": "🌐 ハイテク利確売りや米中規制警戒。"},
    "2.重工防衛": {"high": "🌐 海外情勢緊迫や防衛予算増額方針で買い加速。", "low": "🌐 材料出尽くしに伴うポジション調整売り。"},
    "3.自動車": {"high": "🌐 ドル円の円安推移による輸出採算改善期待。", "low": "🌐 米貿易関税リスクや円高懸念。"},
    "4.大型金融": {"high": "🌐 日銀利上げ観測や金利上昇による利ざや拡大期待。", "low": "🌐 世界的な景気減速懸念に伴う金利低下。"},
    "5.エネ資源": {"high": "🌐 中東情勢やOPEC減産による原油・ガス価格急伸。", "low": "🌐 景気後退懸念に伴うエネルギー需要縮小。"},
    "6.海運物流": {"high": "🌐 地政学航路迂回や運賃指数急上昇報道。", "low": "🌐 港湾混雑解消や運賃指数の調整局面。"},
    "7.メガテック": {"high": "🌐 生成AI・クラウド事業の好決算ニュース。", "low": "🌐 米金利上昇による高PER警戒感。"},
    "8.商社流通": {"high": "🌐 海外投資家からの再評価＆資源高の好影響。", "low": "🌐 商品市況沈静化による利益押し下げ。"},
    "9.医薬バイオ": {"high": "🌐 ディフェンシブ逃避・新薬承認ニュース。", "low": "🌐 薬価改定・他成長セクターへの資金移動。"},
    "10.電気精密": {"high": "🌐 産業機器需要回復やパワー半導体需要。", "low": "🌐 中華圏向けFA需要の停滞。"}
}

DATA_CACHE = {}
LAST_CACHE_TIME = None
alert_history = {}

def get_session():
    try:
        return cffi_requests.Session(impersonate="chrome120")
    except Exception:
        return None

# 🎯 株探（Kabutan）から日本株の100%ピンポイント価格を取得する関数
def get_exact_jp_stock_data(code: str):
    clean_code = code.replace(".T", "")
    url = f"https://kabutan.jp/stock/?code={clean_code}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.text, "html.parser")
        
        price_tag = soup.find("span", class_="kabuka")
        if not price_tag: return None
        price_str = price_tag.text.replace(",", "").replace("円", "").strip()
        current_price = float(price_str)

        change_tag = soup.find("dd", class_=re.compile(r"stock_kabuka_"))
        match = re.search(r"\(([-+]?\d+\.\d+)%\)", change_tag.text if change_tag else "")
        day_change = float(match.group(1)) if match else 0.0

        return {"price": current_price, "change": day_change}
    except Exception as e:
        print(f"Kabutan Scraping Error ({code}): {e}")
        return None

def fetch_ticker_full_analysis(ticker: str):
    try:
        session = get_session()
        ticker_obj = yf.Ticker(ticker, session=session) if session else yf.Ticker(ticker)
        
        df = ticker_obj.history(period="1y", interval="1d")
        if df.empty or len(df['Close']) < 30:
            return None

        close = df['Close'].dropna()
        open_p = df['Open'].dropna()
        high_p = df['High'].dropna()
        low_p = df['Low'].dropna()
        volume = df['Volume'].dropna() if 'Volume' in df else pd.Series()

        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2]) if len(close) >= 2 else current_price
        day_change = round(((current_price - prev_price) / prev_price) * 100, 2)

        # 🎯 日本株なら株探の公式数値にピンポイント差し替え
        if ticker.endswith(".T"):
            exact = get_exact_jp_stock_data(ticker)
            if exact:
                current_price = exact["price"]
                day_change = exact["change"]

        # テクニカル分析
        sma5 = close.rolling(window=5).mean()
        sma25 = close.rolling(window=25).mean()
        sma75 = close.rolling(window=75).mean() if len(close) >= 75 else sma25
        sma200 = close.rolling(window=200).mean().iloc[-1] if len(close) >= 200 else current_price

        is_long_downtrend = current_price < sma200
        perfect_order = (sma5.iloc[-1] > sma25.iloc[-1]) and (sma25.iloc[-1] > sma75.iloc[-1])
        bias25 = round(((current_price - sma25.iloc[-1]) / sma25.iloc[-1]) * 100, 1) if sma25.iloc[-1] != 0 else 0

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        last_loss = loss.iloc[-1] if not loss.empty else 0
        rsi = round(100.0 if last_loss == 0 else 100 - (100 / (1 + (gain.iloc[-1] / last_loss))), 1)

        vol_ma = volume.rolling(window=25).mean().iloc[-1] if len(volume) >= 25 else 0
        vol_ratio = round((volume.iloc[-1] / vol_ma), 2) if vol_ma > 0 else 1.0
        vol_spike = vol_ratio >= 1.8

        bid_ask_ratio = 1.0
        per, roe, revenue_growth, mcap_ok = "N/A", "N/A", "N/A", False
        mcap_in_billion = 0

        try:
            info = ticker_obj.info or {}
            bid = info.get("bidSize", 0)
            ask = info.get("askSize", 0)
            if bid and ask and ask > 0:
                bid_ask_ratio = round(bid / ask, 2)
            else:
                bid_ask_ratio = round(vol_ratio * (1.2 if day_change > 0 else 0.8), 2)

            per_val = info.get("trailingPE") or info.get("forwardPE")
            roe_val = info.get("returnOnEquity")
            rev_val = info.get("revenueGrowth")
            mcap = info.get("marketCap")
            
            if mcap:
                mcap_in_billion = round(mcap / 1e8, 1)
                mcap_ok = (mcap_in_billion < 1500)
            if per_val: per = round(float(per_val), 1)
            if roe_val: roe = round(float(roe_val * 100), 1)
            if rev_val: revenue_growth = round(float(rev_val * 100), 1)
        except Exception:
            pass

        is_tenbagger_candidate = (
            mcap_ok and 
            (revenue_growth != "N/A" and revenue_growth >= 15.0) and 
            (vol_spike or vol_ratio >= 1.5) and 
            (rsi >= 50)
        )
        is_large_cap = mcap_in_billion >= 3000
        is_heavy_over = (bid_ask_ratio <= 0.75)

        base_score = (vol_ratio * 20) + (abs(day_change) * 5) + (rsi * 0.2)
        if perfect_order: base_score += 15
        if is_tenbagger_candidate: base_score += 20
        if is_long_downtrend: base_score -= 25
        if is_heavy_over: base_score -= 15

        final_score = min(max(int(base_score), 10), 100)
        is_us = not ticker.endswith(".T")

        return {
            "code": ticker.replace(".T", ""),
            "is_us": is_us,
            "price": current_price,
            "change": day_change,
            "bias": bias25,
            "rsi": rsi,
            "vol_ratio": vol_ratio,
            "vol_spike": vol_spike,
            "perfect_order": perfect_order,
            "bid_ask_ratio": bid_ask_ratio,
            "is_long_downtrend": is_long_downtrend,
            "is_heavy_over": is_heavy_over,
            "is_tenbagger_candidate": is_tenbagger_candidate,
            "is_large_cap": is_large_cap,
            "mcap_billion": mcap_in_billion,
            "score": final_score
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
        if tech: new_data[code] = tech
        time.sleep(0.05)
    if new_data:
        DATA_CACHE = new_data
        LAST_CACHE_TIME = datetime.now(JST)

def get_future_action_eval(tech):
    unit = "$" if tech['is_us'] else "円"
    p = tech['price']
    tp_short = round(p * 1.08, 1)
    tp_ten = round(p * 2.5, 1)
    sl_line = round(p * 0.94, 1)

    if tech['is_long_downtrend'] and tech['is_heavy_over']:
        return "⚠️ **【戻り売り警戒】** 長期下落＋売り圧力強。反発は一転して売られやすい局面。手仕舞い推奨。"
    elif tech['is_tenbagger_candidate']:
        return f"🚀 **【テンバガー狙い・高ボラ型】** 短期爆発期待！\n└ 🎯 目標: `{tp_ten}{unit}` / 撤退: `{sl_line}{unit}`"
    elif tech['is_large_cap']:
        return "🏛️ **【大型主力株・ガチホ/押し目評価】** 長期安心銘柄。急落時は絶好の仕込み場。" if tech['perfect_order'] else "🏛️ **【大型株・ボックス推移】** 節目での一部利確、引きつけての買い。"
    else:
        return f"🟢 **【短期モメンタム型】** 直近高値突破の可能性あり（短期目標: `{tp_short}{unit}`）。" if tech['score'] >= 75 else "🟡 **【様子見】** 明確なトレンド待ち。"

async def send_to_general_channel(interaction: discord.Interaction, full_text: str):
    if not interaction.response.is_done(): await interaction.response.defer()
    target_channel = bot.get_channel(GENERAL_CHANNEL_ID) if GENERAL_CHANNEL_ID else interaction.channel
    chunks, curr_chunk = [], ""
    for line in full_text.split("\n"):
        if len(curr_chunk) + len(line) + 1 > 1900:
            chunks.append(curr_chunk)
            curr_chunk = line + "\n"
        else: curr_chunk += line + "\n"
    if curr_chunk: chunks.append(curr_chunk)
    for chunk in chunks: await target_channel.send(chunk)

def analyze_single_ticker(code_input: str):
    code_input = code_input.upper().strip()
    ticker = f"{code_input}.T" if code_input.isdigit() and len(code_input) == 4 else code_input
    tech = fetch_ticker_full_analysis(ticker)
    if tech:
        unit = "$" if tech['is_us'] else "円"
        eval_str = get_future_action_eval(tech)
        return (
            f"📊 **【高度多角解析】`{code_input}`** (スコア: `{tech['score']}点`)\n"
            f"├ **現在値**: {tech['price']}{unit} (**{tech['change']}%**)\n"
            f"├ **時価総額**: `{tech['mcap_billion']}億円` | **板買い圧力**: `{tech['bid_ask_ratio']}倍`\n"
            f"└ 💡 **評価**: {eval_str}"
        )
    return f"⚠️ `{code_input}` のデータを取得できませんでした。"

class StockSearchModal(Modal, title="銘柄多角解析"):
    stock_code = TextInput(label="銘柄コードを入力", placeholder="例: 7013, 8035, NVDA")
    async def on_submit(self, interaction: discord.Interaction):
        res = await asyncio.to_thread(analyze_single_ticker, self.stock_code.value)
        await send_to_general_channel(interaction, res)

class InstitutionalBoardView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="🔍 銘柄多角高度解析", style=discord.ButtonStyle.success, custom_id="search_stock_modal_perm")
    async def search_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockSearchModal())

    @discord.ui.button(label="🌐 業界別 資金動向", style=discord.ButtonStyle.primary, custom_id="fetch_sector_flow_perm")
    async def sector_button(self, interaction: discord.Interaction, button: Button):
        full_report = "📊 **【10大業界 資金動向・ニュース・将来評価】**\n\n"
        for sector_name, tickers in SECTORS.items():
            scores, line_items = [], []
            for code in tickers:
                tech = DATA_CACHE.get(code)
                if tech:
                    scores.append(tech['score'])
                    tag = "🚀" if tech['is_tenbagger_candidate'] else ("🔥" if tech['score'] >= 70 else "🔻")
                    line_items.append(f"`{tech['code']}`:{tag}{tech['score']}点({tech['change']}%)")
            avg_score = int(sum(scores) / len(scores)) if scores else 50
            reason = SECTOR_NEWS_FACTORS.get(sector_name, {})["high" if avg_score >= 50 else "low"]
            full_report += f"**🔹 {sector_name}** (`{avg_score}点`)\n> " + " | ".join(line_items) + f"\n└ 🧠 {reason}\n\n"
        await send_to_general_channel(interaction, full_report)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.add_view(InstitutionalBoardView())
    if not real_time_signal_monitor.is_running(): real_time_signal_monitor.start()
    if not scheduled_market_reports.is_running(): scheduled_market_reports.start()

@tasks.loop(minutes=10)
async def real_time_signal_monitor():
    await bot.wait_until_ready()
    await asyncio.to_thread(refresh_all_cache)

@tasks.loop(minutes=1)
async def scheduled_market_reports():
    await bot.wait_until_ready()
    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not channel or datetime.now(JST).weekday() >= 5: return
    now = datetime.now(JST)
    if now.strftime("%H:%M") == "15:30":
        msg = "🌇 **【日本株 大引けサマリー＆ピンポイント価格レポート】**\n"
        jp_techs = [t for t in DATA_CACHE.values() if t and not t['is_us']]
        jp_techs.sort(key=lambda x: x['score'], reverse=True)
        for t in jp_techs[:5]:
            msg += f"├ `{t['code']}`: **{t['change']}%** ({t['price']}円) | スコア:`{t['score']}点`\n"
        await channel.send(msg)

@bot.event
async def on_message(message):
    if message.author.bot: return
    if message.content.strip() in ["!k", "!panel"]:
        channel = bot.get_channel(DASHBOARD_CHANNEL_ID) if DASHBOARD_CHANNEL_ID else message.channel
        await channel.purge(limit=10)
        await channel.send("📌 **【常設ダッシュボード】多角株式分析 Bot**", view=InstitutionalBoardView())
        return
    await bot.process_commands(message)

bot.run(TOKEN)
