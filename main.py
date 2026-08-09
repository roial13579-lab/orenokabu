import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import yfinance as yf
from curl_cffi import requests as cffi_requests

# --- Render用ダミーサーバー ---
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

threading.Thread(target=run_dummy_server, daemon=True).start()

# --- Discord Bot 設定 ---
TOKEN = "MTUzNTYzNjc4MzU1ODA0MTY0MA.GBw8SB.9TSIbUXCWXJZJN5tn0h3sUfKALHRFCDs4yO5Dg"
PANEL_CHANNEL_ID = 1535613064056152247
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

# キャッシュ保持用辞書 (キー: ticker, 値: (timestamp, data_dict))
STOCK_CACHE = {}
CACHE_TTL = 300  # キャッシュ有効期限: 5分 (300秒)

def get_session():
    # curl_cffiを利用してブラウザアクセスを模倣
    try:
        session = cffi_requests.Session(impersonate="chrome110")
        return session
    except Exception:
        return None

def fetch_single_ticker_data(ticker: str):
    now = time.time()
    if ticker in STOCK_CACHE:
        cached_time, cached_data = STOCK_CACHE[ticker]
        if now - cached_time < CACHE_TTL:
            return cached_data

    try:
        session = get_session()
        ticker_obj = yf.Ticker(ticker, session=session) if session else yf.Ticker(ticker)
        df = ticker_obj.history(period="1mo", interval="1d")
        
        if df.empty or len(df['Close']) == 0:
            return None

        close = df['Close'].dropna()
        volume = df['Volume'].dropna() if 'Volume' in df else []

        if len(close) == 0:
            return None

        current_price = close.iloc[-1]
        ma25 = close.mean()
        bias = ((current_price - ma25) / ma25) * 100 if ma25 != 0 else 0

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).mean()
        loss = (-delta.where(delta < 0, 0)).mean()
        rs = gain / loss if loss != 0 else 1
        rsi = 100 - (100 / (1 + rs)) if (1 + rs) != 0 else 50

        vol_ma = volume.mean() if len(volume) > 0 else 0
        vol_ratio = (volume.iloc[-1] / vol_ma) if vol_ma > 0 else 1.0

        is_dip = (rsi <= 35) and (bias <= -5.0)

        result = {
            "price": round(float(current_price), 1),
            "bias": round(float(bias), 1),
            "rsi": round(float(rsi), 1),
            "vol_ratio": round(float(vol_ratio), 2),
            "is_dip": is_dip
        }

        STOCK_CACHE[ticker] = (now, result)
        return result
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def analyze_single_ticker(code_input: str):
    code_input = code_input.upper().strip()
    ticker = f"{code_input}.T" if code_input.isdigit() and len(code_input) == 4 else code_input

    tech = fetch_single_ticker_data(ticker)
    if tech:
        status_str = "🎯 **押し目買いシグナル点灯中！（売られ過ぎ）**" if tech['is_dip'] else "⚡ 正常範囲内（押し目水準ではありません）"
        return (
            f"📊 **【個別銘柄解析】`{code_input}`**\n"
            f"├ **現在値**: {tech['price']}\n"
            f"├ **25日乖離率**: {tech['bias']}%\n"
            f"├ **RSI(14)**: {tech['rsi']}%\n"
            f"└ **判定**: {status_str}"
        )
    else:
        return f"⚠️ `{code_input}` の株価データを取得できませんでした。アクセス制限中か、コードが誤っている可能性があります。少し時間をおいて再試行してください。"

class StockSearchModal(Modal, title="銘柄テクニカル判定検索"):
    stock_code = TextInput(
        label="銘柄コード または ティッカーを入力",
        placeholder="例: 7011, 8035, 4052, NVDA",
        min_length=1,
        max_length=10,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        res_msg = analyze_single_ticker(self.stock_code.value)
        await interaction.followup.send(res_msg)

def fetch_all_technical_data():
    all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
    results = {}
    for code in all_tickers:
        tech = fetch_single_ticker_data(code)
        if tech:
            results[code] = tech
        time.sleep(0.1)  # 連続アクセス対策のマイクロウェイト
    return results

class InstitutionalBoardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔍 銘柄検索", style=discord.ButtonStyle.success, custom_id="search_stock_modal_perm")
    async def search_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockSearchModal())

    @discord.ui.button(label="🌐 各業界5社 資金流入力学", style=discord.ButtonStyle.primary, custom_id="fetch_sector_flow_perm")
    async def sector_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        tech_data = fetch_all_technical_data()
        full_report = "📊 **【全10セクター 資金流入力学リアルタイム解析】**\n\n"
        for sector_name, tickers in SECTORS.items():
            full_report += f"**🔹 {sector_name}**\n"
            line_items = []
            for code in tickers:
                tech = tech_data.get(code)
                clean_code = code.replace('.T','')
                if tech:
                    score = min(max(int((tech['vol_ratio'] * 30) + (tech['rsi'] * 0.5)), 10), 100)
                    status = "🔥" if score >= 60 else ("⚡" if score >= 40 else "🔻")
                    line_items.append(f"`{clean_code}`:{status}{score}")
                else:
                    line_items.append(f"`{clean_code}`:取得中")
            full_report += "> " + " | ".join(line_items) + "\n\n"

        await interaction.followup.send(full_report)
        await send_or_move_panel(interaction.channel)

    @discord.ui.button(label="📉 押し目買いシグナル検出", style=discord.ButtonStyle.danger, custom_id="fetch_dip_signals_perm")
    async def dip_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        tech_data = fetch_all_technical_data()
        report = "🎯 **【大型株 一時的下落（押し目買い）判定レポート】**\n\n"
        found_count = 0
        for code, tech in tech_data.items():
            if tech and tech['is_dip']:
                found_count += 1
                report += f"💡 **銘柄**: `{code}`\n"
                report += f"├ **現在値**: {tech['price']} / **25日乖離率**: {tech['bias']}%\n"
                report += f"└ **RSI(14)**: {tech['rsi']}% (売られ過ぎ判定)\n\n"
        if found_count == 0:
            report += "現在、売られ過ぎ水準（RSI 35%以下）に達している絶好の押し目対象銘柄はありません。"
        await interaction.followup.send(report)
        await send_or_move_panel(interaction.channel)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

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
        "※ `🔍 銘柄検索` ボタンを押すか、`!c 銘柄コード` で個別にチェックできます。",
        view=view
    )

async def setup_permanent_panel():
    target_channel = None
    if PANEL_CHANNEL_ID != 0:
        target_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if not target_channel:
        for guild in bot.guilds:
            for channel in guild.text_channels:
                perms = channel.permissions_for(guild.me)
                if perms.send_messages and perms.read_message_history:
                    target_channel = channel
                    break
            if target_channel:
                break
    if target_channel:
        await send_or_move_panel(target_channel)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.add_view(InstitutionalBoardView())
    await setup_permanent_panel()

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
                res_msg = analyze_single_ticker(parts[1])
                await message.channel.send(res_msg)
        return

    await bot.process_commands(message)

# Bot起動
bot.run(TOKEN)
