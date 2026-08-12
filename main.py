import os
import time
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import yfinance as yf
from curl_cffi import requests as cffi_requests
import pandas as pd

# --- Render用ダミーサーバー & スリープ防止 (Self-Ping) ---
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
    """10分ごとに自分自身へアクセスしてRenderの15分スリープを回避"""
    time.sleep(30)
    service_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not service_url:
        port = os.environ.get("PORT", "10000")
        service_url = f"http://127.0.0.1:{port}"

    print(f"🔄 Self-ping loop started. Target: {service_url}")

    while True:
        try:
            req = urllib.request.Request(
                service_url,
                headers={'User-Agent': 'Mozilla/5.0 (Render Keep-Alive Loop)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                pass
            print(f"⏰ [Keep-Alive] Ping sent to {service_url} - Status: 200 OK")
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

STOCK_CACHE = {}
CACHE_TTL = 300  # キャッシュ 5分

def get_session():
    try:
        session = cffi_requests.Session(impersonate="chrome110")
        return session
    except Exception:
        return None

def fetch_single_ticker_data(ticker: str):
    """テクニカルおよび財務指標を取得（フォールバック強化・N/A激減版）"""
    now = time.time()
    if ticker in STOCK_CACHE:
        cached_time, cached_data = STOCK_CACHE[ticker]
        if now - cached_time < CACHE_TTL:
            return cached_data

    try:
        session = get_session()
        ticker_obj = yf.Ticker(ticker, session=session) if session else yf.Ticker(ticker)
        
        # 6ヶ月分取得して計算精度を担保
        df = ticker_obj.history(period="6mo", interval="1d")
        
        if df.empty or len(df['Close']) < 25:
            return None

        close = df['Close'].dropna()
        volume = df['Volume'].dropna() if 'Volume' in df else pd.Series()
        current_price = close.iloc[-1]
        
        # テクニカル指標計算
        sma5 = close.rolling(window=5).mean()
        sma25 = close.rolling(window=25).mean()
        bias = ((current_price - sma25.iloc[-1]) / sma25.iloc[-1]) * 100 if sma25.iloc[-1] != 0 else 0

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        last_loss = loss.iloc[-1] if not loss.empty else 0
        if last_loss == 0:
            rsi = 100.0
        else:
            rs = gain.iloc[-1] / last_loss
            rsi = 100 - (100 / (1 + rs))

        is_gc = (sma5.iloc[-2] <= sma25.iloc[-2]) and (sma5.iloc[-1] > sma25.iloc[-1])

        std25 = close.rolling(window=25).std()
        upper_band = sma25 + (std25 * 2)
        bb_breakout = current_price > upper_band.iloc[-1]

        vol_ma = volume.rolling(window=25).mean().iloc[-1] if len(volume) >= 25 else 0
        vol_ratio = (volume.iloc[-1] / vol_ma) if vol_ma > 0 else 1.0

        # --- 財務データ取得・フォールバック設計 ---
        info = {}
        try:
            info = ticker_obj.info or {}
        except Exception:
            pass

        # 1. 時価総額
        market_cap = info.get("marketCap")
        if not market_cap:
            try:
                market_cap = getattr(ticker_obj.fast_info, 'market_cap', None)
            except Exception:
                pass

        # 2. PER
        per = info.get("trailingPE") or info.get("forwardPE")

        # 3. ROE
        roe = info.get("returnOnEquity")

        # 4. 増収率
        revenue_growth = info.get("revenueGrowth")

        # --- 財務データの直接計算・補完（infoで取れない場合） ---
        if roe is None or revenue_growth is None:
            try:
                q_fin = ticker_obj.quarterly_financials
                if not q_fin.empty and q_fin.shape[1] >= 2:
                    # 売上高増収率計算
                    rev_rows = [r for r in q_fin.index if 'Total Revenue' in str(r) or 'Revenue' in str(r)]
                    if rev_rows:
                        rev_curr = q_fin.loc[rev_rows[0]].iloc[0]
                        rev_prev = q_fin.loc[rev_rows[0]].iloc[1]
                        if rev_prev and rev_prev > 0 and revenue_growth is None:
                            revenue_growth = (rev_curr - rev_prev) / rev_prev

                    # ROE試算（当期純利益 / 純資産）
                    net_inc_rows = [r for r in q_fin.index if 'Net Income' in str(r)]
                    bs = ticker_obj.quarterly_balance_sheet
                    if net_inc_rows and not bs.empty:
                        equity_rows = [r for r in bs.index if 'Stockholders Equity' in str(r) or 'Equity' in str(r)]
                        if equity_rows:
                            annualized_net_inc = q_fin.loc[net_inc_rows[0]].iloc[0] * 4
                            equity = bs.loc[equity_rows[0]].iloc[0]
                            if equity and equity > 0 and roe is None:
                                roe = annualized_net_inc / equity
            except Exception:
                pass

        # 10倍株判定
        market_cap_ok = False
        if market_cap:
            if ticker.endswith(".T"):
                market_cap_ok = (market_cap / 1e8) < 1000  # 1,000億円未満
            else:
                market_cap_ok = (market_cap / 1e6) < 1000  # 10億ドル未満相当

        has_rev = (revenue_growth is not None) and (revenue_growth >= 0.20)
        has_roe = (roe is not None) and (roe >= 0.15)
        has_per = (per is not None) and (0 < per < 100)

        is_tenbagger_candidate = market_cap_ok and has_rev and has_roe and has_per
        is_dip = (rsi <= 35) and (bias <= -5.0)

        result = {
            "price": round(float(current_price), 1),
            "bias": round(float(bias), 1),
            "rsi": round(float(rsi), 1),
            "vol_ratio": round(float(vol_ratio), 2),
            "is_gc": is_gc,
            "bb_breakout": bb_breakout,
            "is_dip": is_dip,
            "is_tenbagger": is_tenbagger_candidate,
            "per": round(float(per), 1) if per else "N/A",
            "roe": round(float(roe * 100), 1) if roe else "N/A",
            "rev_growth": round(float(revenue_growth * 100), 1) if revenue_growth else "N/A"
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
        status_str = "🎯 **押し目買いシグナル点灯中！（売られ過ぎ）**" if tech['is_dip'] else "⚡ レンジ内"
        gc_str = "✅ 発生" if tech['is_gc'] else "➖ なし"
        bb_str = "🚀 +2σ上抜け" if tech['bb_breakout'] else "➖ 正常値"
        tb_str = "🌟 10倍株基準クリア（高成長・適正評価）" if tech['is_tenbagger'] else "➖ 基準外"

        return (
            f"📊 **【多角的銘柄・罫線解析】`{code_input}`**\n"
            f"├ **現在値**: {tech['price']}円\n"
            f"├ **25日乖離率**: {tech['bias']}%\n"
            f"├ **RSI(14)**: {tech['rsi']}%\n"
            f"├ **ゴールデンクロス**: {gc_str}\n"
            f"├ **ボリンジャーバンド**: {bb_str}\n"
            f"├ **10倍株スクリーニング**: {tb_str}\n"
            f"├ **指標情報**: PER `{tech['per']}倍` | ROE `{tech['roe']}%` | 増収率 `{tech['rev_growth']}%` \n"
            f"└ **判定**: {status_str}"
        )
    else:
        return f"⚠️ `{code_input}` の株価データを取得できませんでした。コードが正しいか確認の上、少し時間をおいて再試行してください。"

class StockSearchModal(Modal, title="銘柄テクニカル＆10倍株判定検索"):
    stock_code = TextInput(
        label="銘柄コード または ティッカーを入力",
        placeholder="例: 7011, 8035, 3905, NVDA",
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
        time.sleep(0.1)
    return results

class InstitutionalBoardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔍 銘柄詳細解析", style=discord.ButtonStyle.success, custom_id="search_stock_modal_perm")
    async def search_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockSearchModal())

    @discord.ui.button(label="🌐 各業界 資金流入力学", style=discord.ButtonStyle.primary, custom_id="fetch_sector_flow_perm")
    async def sector_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        tech_data = fetch_all_technical_data()
        full_report = "📊 **【全10セクター 資金流入力学・シグナル解析】**\n\n"
        for sector_name, tickers in SECTORS.items():
            full_report += f"**🔹 {sector_name}**\n"
            line_items = []
            for code in tickers:
                tech = tech_data.get(code)
                clean_code = code.replace('.T','')
                if tech:
                    score = min(max(int((tech['vol_ratio'] * 30) + (tech['rsi'] * 0.5) + (20 if tech['is_gc'] else 0)), 10), 100)
                    status = "🔥" if score >= 65 else ("⚡" if score >= 40 else "🔻")
                    line_items.append(f"`{clean_code}`:{status}{score}")
                else:
                    line_items.append(f"`{clean_code}`:取得中")
            full_report += "> " + " | ".join(line_items) + "\n\n"

        await interaction.followup.send(full_report)
        await send_or_move_panel(interaction.channel)

    @discord.ui.button(label="📉 押し目・大化けシグナル検出", style=discord.ButtonStyle.danger, custom_id="fetch_dip_signals_perm")
    async def dip_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        tech_data = fetch_all_technical_data()
        report = "🎯 **【注目銘柄・テクニカル＋大化けシグナル抽出レポート】**\n\n"
        found_count = 0
        for code, tech in tech_data.items():
            if tech and (tech['is_dip'] or tech['is_gc'] or tech['bb_breakout'] or tech['is_tenbagger']):
                found_count += 1
                signals = []
                if tech['is_dip']: signals.append("押し目買い(売られ過ぎ)")
                if tech['is_gc']: signals.append("ゴールデンクロス")
                if tech['bb_breakout']: signals.append("+2σブレイクアウト")
                if tech['is_tenbagger']: signals.append("10倍株財務クリア")

                report += f"💡 **銘柄**: `{code}` | **検出**: {', '.join(signals)}\n"
                report += f"├ **現在値**: {tech['price']}円 / **25日乖離**: {tech['bias']}%\n"
                report += f"└ **RSI**: {tech['rsi']}% | **PER**: {tech['per']}倍 | **ROE**: {tech['roe']}%\n\n"
        
        if found_count == 0:
            report += "現在、シグナル条件に合致する注目銘柄はありません。"
        
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
        "※ `🔍 銘柄詳細解析` ボタンを押すか、`!c 銘柄コード` で個別にチェックできます。",
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

bot.run(TOKEN)
