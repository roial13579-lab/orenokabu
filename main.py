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
import feedparser  # 📰 Google News RSS取得用

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
GENERAL_CHANNEL_ID = int(os.environ.get("GENERAL_CHANNEL_ID", "0"))
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

# 🔍 ニュース検索用キーワードの定義
SECTOR_KEYWORDS = {
    "1.半導体": "半導体 株価 SOX",
    "2.重工防衛": "防衛 重工 防衛費",
    "3.自動車": "自動車 株価 為替 円安",
    "4.大型金融": "銀行 株価 金利 日銀",
    "5.エネ資源": "原油 石油 資源 株価",
    "6.海運物流": "海運 運賃 バルチック",
    "7.メガテック": "ビッグテック AI IT株",
    "8.商社流通": "総合商社 資源 株価",
    "9.医薬バイオ": "製薬 医薬品 株価",
    "10.電気精密": "電機 精密機器 株価"
}

DATA_CACHE = {}

def get_session():
    try:
        return cffi_requests.Session(impersonate="chrome120")
    except Exception:
        return None

# 📰 Google Newsから本物の最新ニュースを取得・解析する関数
def fetch_real_sector_news(sector_name: str, avg_change: float):
    keyword = SECTOR_KEYWORDS.get(sector_name, "株式市場")
    encoded_query = urllib.parse.quote(keyword)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    
    try:
        feed = feedparser.parse(rss_url)
        if not feed.entries:
            return "📰 関連ニュースの取得に失敗しました。"

        # 最新3件の見出しを取得
        latest_titles = [entry.title.split(" - ")[0] for entry in feed.entries[:3]]
        news_summary = " / ".join(latest_titles)

        # 株価推移との因果関係評価
        if avg_change > 0.5:
            impact_eval = f"📈 **【追い風】** 直近ニュース（「{latest_titles[0]}」等）が材料視され、買いが優勢となっています。"
        elif avg_change < -0.5:
            impact_eval = f"📉 **【向かい風】** 報道（「{latest_titles[0]}」等）への警戒感や利確売りが上値を抑える要因になっています。"
        else:
            impact_eval = f"➡️ **【交錯・様子見】** ニュース（「{latest_titles[0]}」等）に対する市場の反応は拮抗しており、方向感を模索する動きです。"

        return f"📰 **最新ニュース頭出し**: {news_summary}\n└ 💬 **影響評価**: {impact_eval}"

    except Exception as e:
        print(f"News fetch error for {sector_name}: {e}")
        return "📰 ニュース取得中にエラーが発生しました。"

def get_exact_jp_stock_data(code: str):
    clean_code = code.replace(".T", "")
    url = f"https://kabutan.jp/stock/?code={clean_code}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.text, "html.parser")
        
        price_tag = soup.find("span", class_="kabuka")
        if not price_tag: return None
        price_str = price_tag.text.replace(",", "").replace("円", "").strip()
        current_price = float(price_str)

        day_change = 0.0
        change_dt = soup.find("dd", class_=re.compile(r"stock_kabuka_"))
        if change_dt:
            match = re.search(r"\(([-+]?\d+\.?\d*)%\)", change_dt.text)
            if match:
                day_change = float(match.group(1))

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
        volume = df['Volume'].dropna() if 'Volume' in df else pd.Series()

        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2]) if len(close) >= 2 else current_price
        day_change = round(((current_price - prev_price) / prev_price) * 100, 2)

        if ticker.endswith(".T"):
            exact = get_exact_jp_stock_data(ticker)
            if exact and exact["price"] > 0:
                current_price = exact["price"]
                day_change = exact["change"]

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

        bid_ask_ratio = round(vol_ratio * (1.2 if day_change > 0 else 0.8), 2)
        mcap_in_billion = 0
        revenue_growth = "N/A"

        try:
            info = ticker_obj.info or {}
            mcap = info.get("marketCap")
            rev_val = info.get("revenueGrowth")
            if mcap: mcap_in_billion = round(mcap / 1e8, 1)
            if rev_val: revenue_growth = round(float(rev_val * 100), 1)
        except Exception:
            pass

        is_tenbagger_candidate = (
            (mcap_in_billion > 0 and mcap_in_billion < 1500) and 
            (revenue_growth != "N/A" and revenue_growth >= 15.0) and 
            (vol_spike or vol_ratio >= 1.5) and 
            (rsi >= 50)
        )
        is_large_cap = mcap_in_billion >= 3000

        base_score = (vol_ratio * 20) + (abs(day_change) * 5) + (rsi * 0.2)
        if perfect_order: base_score += 15
        if is_tenbagger_candidate: base_score += 20
        if is_long_downtrend: base_score -= 25

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
            "perfect_order": perfect_order,
            "bid_ask_ratio": bid_ask_ratio,
            "is_long_downtrend": is_long_downtrend,
            "is_tenbagger_candidate": is_tenbagger_candidate,
            "is_large_cap": is_large_cap,
            "mcap_billion": mcap_in_billion,
            "score": final_score
        }
    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
        return None

def refresh_all_cache():
    global DATA_CACHE
    all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
    new_data = {}
    for code in all_tickers:
        tech = fetch_ticker_full_analysis(code)
        if tech: new_data[code] = tech
        time.sleep(0.05)
    if new_data:
        DATA_CACHE = new_data

def get_future_action_eval(tech):
    unit = "$" if tech['is_us'] else "円"
    p = tech['price']
    tp_short = round(p * 1.08, 1)
    tp_ten = round(p * 2.5, 1)
    sl_line = round(p * 0.94, 1)

    if tech['is_long_downtrend']:
        return "⚠️ **【戻り売り警戒】** 長期下落傾向。反発は一転して売られやすい局面。"
    elif tech['is_tenbagger_candidate']:
        return f"🚀 **【テンバガー狙い・高ボラ型】** 短期爆発期待！\n└ 🎯 目標: `{tp_ten}{unit}` / 撤退: `{sl_line}{unit}`"
    elif tech['is_large_cap']:
        return "🏛️ **【大型主力株・ガチホ/押し目評価】** 長期安心銘柄。" if tech['perfect_order'] else "🏛️ **【大型株・ボックス推移】** 引きつけての買い。"
    else:
        return f"🟢 **【短期モメンタム型】** 直近高値突破の可能性あり（短期目標: `{tp_short}{unit}`）。" if tech['score'] >= 75 else "🟡 **【様子見】** 明確なトレンド待ち。"

async def send_to_channel(channel, full_text: str):
    chunks, curr_chunk = [], ""
    for line in full_text.split("\n"):
        if len(curr_chunk) + len(line) + 1 > 1900:
            chunks.append(curr_chunk)
            curr_chunk = line + "\n"
        else: curr_chunk += line + "\n"
    if curr_chunk: chunks.append(curr_chunk)
    for chunk in chunks: await channel.send(chunk)

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
            f"├ **時価総額**: `{tech['mcap_billion']}億円` | **出来高倍率**: `{tech['vol_ratio']}倍`\n"
            f"└ 💡 **評価**: {eval_str}"
        )
    return f"⚠️ `{code_input}` のデータを取得できませんでした。"

class StockSearchModal(Modal, title="銘柄多角解析"):
    stock_code = TextInput(label="銘柄コードを入力", placeholder="例: 7013, 8035, NVDA")
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        res = await asyncio.to_thread(analyze_single_ticker, self.stock_code.value)
        await send_to_channel(interaction.channel, res)

class InstitutionalBoardView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="🔍 銘柄詳細解析", style=discord.ButtonStyle.success, custom_id="search_stock_modal_perm")
    async def search_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockSearchModal())

    # 2. 🌐 各業界 リアルニュース・資金動向
    @discord.ui.button(label="🌐 各業界 ニュース・資金動向", style=discord.ButtonStyle.primary, custom_id="fetch_sector_flow_perm")
    async def sector_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if not DATA_CACHE:
            await asyncio.to_thread(refresh_all_cache)

        full_report = "📊 **【10大業界 リアルタイムニュース＆株価影響分析】**\n\n"
        for sector_name, tickers in SECTORS.items():
            scores, changes, line_items = [], [], []
            for code in tickers:
                tech = DATA_CACHE.get(code)
                if tech:
                    scores.append(tech['score'])
                    changes.append(tech['change'])
                    tag = "🚀" if tech['is_tenbagger_candidate'] else ("🔥" if tech['score'] >= 70 else "🔻")
                    line_items.append(f"`{tech['code']}`:{tag}{tech['score']}点({tech['change']}%)")
            
            avg_score = int(sum(scores) / len(scores)) if scores else 50
            avg_change = float(np.mean(changes)) if changes else 0.0

            # 📰 ここでリアルのGoogle Newsを取得・分析
            news_analysis = await asyncio.to_thread(fetch_real_sector_news, sector_name, avg_change)

            full_report += (
                f"**🔹 {sector_name}** (`モメンタム:{avg_score}点` | 平均騰落:`{avg_change:+.2f}%`)\n"
                f"> " + " | ".join(line_items) + f"\n"
                f"{news_analysis}\n\n"
            )
        await send_to_channel(interaction.channel, full_report)

    @discord.ui.button(label="🎯 押し目・高値突破シグナル", style=discord.ButtonStyle.secondary, custom_id="fetch_breakout_signals_perm")
    async def breakout_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if not DATA_CACHE:
            await asyncio.to_thread(refresh_all_cache)

        sorted_items = sorted(DATA_CACHE.values(), key=lambda x: x['score'], reverse=True)
        high_score_items = [t for t in sorted_items if t['score'] >= 60][:8]

        res = "🎯 **【押し目・高値突破シグナル検出】**\n\n"
        if not high_score_items:
            res += "現在、明確なブレイクアウトシグナルが出ている銘柄はありません。"
        else:
            for t in high_score_items:
                unit = "$" if t['is_us'] else "円"
                tag = "🚀 [テンバガー候補]" if t['is_tenbagger_candidate'] else ("🔥 [パーフェクトオーダー]" if t['perfect_order'] else "📈 [上昇強気]")
                res += (
                    f"**{tag} `{t['code']}`** (スコア: `{t['score']}点`)\n"
                    f"├ **現在値**: {t['price']}{unit} ({t['change']}%) | **RSI**: `{t['rsi']}`\n"
                    f"└ 💡 **評価**: {get_future_action_eval(t)}\n\n"
                )
        await send_to_channel(interaction.channel, res)

    @discord.ui.button(label="⚡ 大口売買・板突破動向", style=discord.ButtonStyle.danger, custom_id="fetch_volume_spikes_perm")
    async def volume_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if not DATA_CACHE:
            await asyncio.to_thread(refresh_all_cache)

        spikes = [t for t in DATA_CACHE.values() if t['vol_ratio'] >= 1.3]
        spikes.sort(key=lambda x: x['vol_ratio'], reverse=True)

        res = "⚡ **【大口売買・板突破動向（出来高急増）】**\n\n"
        if not spikes:
            res += "現在、平時を超える急激な大口売買の集中は見られません。"
        else:
            for t in spikes[:8]:
                unit = "$" if t['is_us'] else "円"
                res += (
                    f"🔥 **`{t['code']}`** | **出来高倍率**: `{t['vol_ratio']}倍`\n"
                    f"├ **現在値**: {t['price']}{unit} ({t['change']}%) | **需給バランス比**: `{t['bid_ask_ratio']}`\n"
                    f"└ 🧠 **大口評価**: {'大口の本格買い集め・板上抜け動向。' if t['change'] > 0 else '大口の売り浴びせ・戻り売り警戒。'}\n\n"
                )
        await send_to_channel(interaction.channel, res)

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
        try:
            await message.channel.purge(limit=10)
        except Exception:
            pass

        await message.channel.send("📌 **【常設ダッシュボード】多角株式分析 Bot**", view=InstitutionalBoardView())
        return

    await bot.process_commands(message)

bot.run(TOKEN)
