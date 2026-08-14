import os
import time
import re
import gc
import threading
import urllib.request
import asyncio
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
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
        time.sleep(300) # 5分ごとにSelf-Pingしてスリープ防止

threading.Thread(target=run_dummy_server, daemon=True).start()
threading.Thread(target=keep_alive_ping, daemon=True).start()

# --- Discord Bot 設定 ---
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", os.environ.get("TOKEN", ""))
GENERAL_CHANNEL_ID = int(os.environ.get("GENERAL_CHANNEL_ID", "0"))

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

DATA_CACHE = {}
LAST_INTERACTION_TIME = time.time()  # 最終操作時刻

# 🇯🇵 日本株専用：Yahoo!ファイナンス（日本）から正確な前日比％を直接取得
def get_exact_jp_stock_data(code: str):
    clean_code = code.replace(".T", "")
    url = f"https://finance.yahoo.co.jp/quote/{clean_code}.T"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            body_text = soup.get_text()
            match = re.search(r"(\d{1,3}(?:,\d{3})*|\d+)\s*[-+]\d+(?:\,\d+)*(?:\.\d+)?\s*([+-]?\d+\.\d+)%", body_text)
            if match:
                price = float(match.group(1).replace(",", ""))
                change = float(match.group(2))
                return {"price": price, "change": change}
    except Exception as e:
        print(f"JP Fetch Error ({clean_code}): {e}")
    return None

# 🇺🇸 米国株用
def get_us_stock_data_direct(symbol: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            meta = res.json()["chart"]["result"][0]["meta"]
            price = float(meta.get("regularMarketPrice", 0.0))
            prev_close = float(meta.get("chartPreviousClose", meta.get("previousClose", 0.0)))
            if price > 0 and prev_close > 0:
                change = round(((price - prev_close) / prev_close) * 100, 2)
                return {"price": price, "change": change}
    except Exception as e:
        print(f"US Fetch Error ({symbol}): {e}")
    return {"price": 100.0, "change": 0.0}

def fetch_market_driver_context():
    url = "https://kabutan.jp/news/marketnews/?category=1"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200: return "市況動向解析中..."
        soup = BeautifulSoup(res.text, "html.parser")
        contexts = [link.text.strip() for item in soup.find_all("td", class_="news_time")[:5] if (link := item.parent.find("a"))]
        full_text = " ".join(contexts)
        drivers = []
        if "為替" in full_text or "円高" in full_text or "円安" in full_text: drivers.append("💱 為替（ドル円）")
        if "米株" in full_text or "SOX" in full_text or "ナスダック" in full_text: drivers.append("🌐 米国市場（SOX/ナスダック）")
        if "原油" in full_text or "WTI" in full_text: drivers.append("🛢️ 原油市況")
        return " / ".join(drivers) if drivers else "📊 決算発表・ポジション調整"
    except Exception:
        return "市場動向データ取得中"

def fetch_ticker_full_analysis(ticker: str):
    try:
        if ticker.endswith(".T"):
            jp_data = get_exact_jp_stock_data(ticker)
            if jp_data:
                return {"code": ticker.replace(".T", ""), "is_us": False, "price": jp_data["price"], "change": jp_data["change"]}
        else:
            us_data = get_us_stock_data_direct(ticker)
            return {"code": ticker, "is_us": True, "price": us_data["price"], "change": us_data["change"]}
    except Exception as e:
        print(f"Analysis Error ({ticker}): {e}")
    return None

# --- バックグラウンド定期更新 ＆ メモリ自動解放タスク ---
@tasks.loop(minutes=10)
async def auto_refresh_and_memory_clean():
    global DATA_CACHE, LAST_INTERACTION_TIME
    print("🔄 [定期タスク] 株価データを裏で更新中...")
    
    all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
    new_data = {}
    for code in all_tickers:
        tech = await asyncio.to_thread(fetch_ticker_full_analysis, code)
        if tech:
            new_data[code] = tech
        await asyncio.sleep(0.1)
    
    if new_data:
        DATA_CACHE = new_data
        print(f"✅ [定期タスク] キャッシュ更新完了 ({len(DATA_CACHE)}件)")

    # 15分以上操作がない場合はメモリを強制開放
    idle_time = time.time() - LAST_INTERACTION_TIME
    if idle_time > 900: # 900秒 = 15分
        print("🧹 [メモリ解放] 15分間無操作のためメモリクリーンアップを実行します")
        gc.collect()

def generate_sector_impact_analysis(sector_name: str, avg_change: float, main_driver: str):
    if "半導体" in sector_name:
        return f"🔴 **要因**: {main_driver}の影響で売り優勢（平均 `{avg_change:+.2f}%`）。" if avg_change < 0 else f"🟢 **要因**: AI需要や米株高を追い風に買戻し主導（平均 `{avg_change:+.2f}%`）。"
    elif "重工防衛" in sector_name:
        return f"🔴 **要因**: 利確売りに押され調整色（平均 `{avg_change:+.2f}%`）。" if avg_change < 0 else f"🟢 **要因**: 地政学リスクを背景にポジション構築（平均 `{avg_change:+.2f}%`）。"
    else:
        return f"🔴 **要因**: {main_driver}に伴い下値模索（平均 `{avg_change:+.2f}%`）。" if avg_change < 0 else f"🟢 **要因**: {main_driver}好転に伴い買い先行（平均 `{avg_change:+.2f}%`）。"

class StockSearchModal(Modal, title="銘柄多角解析"):
    stock_code = TextInput(label="銘柄コードを入力", placeholder="例: 8035, 7013, NVDA")
    async def on_submit(self, interaction: discord.Interaction):
        global LAST_INTERACTION_TIME
        LAST_INTERACTION_TIME = time.time()
        await interaction.response.defer(ephemeral=True)
        
        code_input = self.stock_code.value.upper().strip()
        ticker = f"{code_input}.T" if code_input.isdigit() and len(code_input) == 4 else code_input
        tech = await asyncio.to_thread(fetch_ticker_full_analysis, ticker)
        
        if tech:
            unit = "$" if tech['is_us'] else "円"
            res = (
                f"📊 **【多角解析】`{code_input}`**\n"
                f"├ **現在値**: {tech['price']:,}{unit} (**{tech['change']:+.2f}%**)\n"
                f"└ 💡 **判定**: {'🟢 買い優勢' if tech['change'] > 0 else '🔴 売り優勢・調整中'}"
            )
        else:
            res = f"⚠️ `{code_input}` のデータを取得できませんでした。"
            
        target_channel = interaction.client.get_channel(GENERAL_CHANNEL_ID) or interaction.channel
        await target_channel.send(res)
        await interaction.followup.send("✅ #一般 チャンネルへ出力しました！", ephemeral=True)

class InstitutionalBoardView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="🔍 銘柄詳細解析", style=discord.ButtonStyle.success, custom_id="search_stock_modal_perm")
    async def search_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockSearchModal())

    @discord.ui.button(label="🌐 各業界 ニュース・資金動向", style=discord.ButtonStyle.primary, custom_id="fetch_sector_flow_perm")
    async def sector_button(self, interaction: discord.Interaction, button: Button):
        global LAST_INTERACTION_TIME
        LAST_INTERACTION_TIME = time.time()
        
        # 即座に応答を返す（3秒タイムアウトを完全に回避）
        await interaction.response.defer(ephemeral=True)

        main_driver = await asyncio.to_thread(fetch_market_driver_context)
        full_report = (
            f"🌐 **【10大業界 株価変動解析】**\n"
            f"📌 **現在の相場主導要因**: `{main_driver}`\n"
            f"─────────────────────────\n\n"
        )

        for sector_name, tickers in SECTORS.items():
            changes, line_items = [], []
            for code in tickers:
                tech = DATA_CACHE.get(code)
                if tech:
                    changes.append(tech['change'])
                    tag = "🟢" if tech['change'] > 0 else ("🔴" if tech['change'] < 0 else "🟡")
                    line_items.append(f"`{tech['code']}`:{tag}{tech['change']:+.2f}%")
            
            avg_change = float(np.mean(changes)) if changes else 0.0
            impact_story = generate_sector_impact_analysis(sector_name, avg_change, main_driver)

            full_report += (
                f"**🔹 {sector_name}** （平均騰落率: `{avg_change:+.2f}%`）\n"
                f"> " + " | ".join(line_items) + f"\n"
                f"└ {impact_story}\n\n"
            )

        target_channel = interaction.client.get_channel(GENERAL_CHANNEL_ID) or interaction.channel
        await target_channel.send(full_report)
        await interaction.followup.send("✅ #一般 チャンネルへ出力しました！", ephemeral=True)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.add_view(InstitutionalBoardView())
    if not auto_refresh_and_memory_clean.is_running():
        auto_refresh_and_memory_clean.start()

@bot.event
async def on_message(message):
    if message.author.bot: return
    if message.content.strip() in ["!k", "!panel"]:
        await message.channel.send("📌 **【常設ダッシュボード】多角株式分析 Bot**", view=InstitutionalBoardView())
        return
    await bot.process_commands(message)

bot.run(TOKEN)
