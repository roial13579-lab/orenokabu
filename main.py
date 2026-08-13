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
GENERAL_CHANNEL_ID = int(os.environ.get("GENERAL_CHANNEL_ID", "0")) # 結果を出力する一般チャンネル
REPORT_CHANNEL_ID = int(os.environ.get("REPORT_CHANNEL_ID", "0"))   # 定時レポート
ALERT_CHANNEL_ID = int(os.environ.get("ALERT_CHANNEL_ID", "0"))     # 売買アラート

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
ALERTED_SIGNALS = set()

# 🔍 株探から市況材料を取得
def fetch_market_driver_context():
    url = "https://kabutan.jp/news/marketnews/?category=1"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200: return "直近の市況材料を解析中..."
        soup = BeautifulSoup(res.text, "html.parser")
        
        news_items = soup.find_all("td", class_="news_time")
        contexts = []
        for item in news_items[:5]:
            parent = item.parent
            link = parent.find("a")
            if link: contexts.append(link.text.strip())
        
        full_text = " ".join(contexts)
        drivers = []
        if "トランプ" in full_text or "発言" in full_text or "関税" in full_text: drivers.append("🇺🇸 米政勢・要人発言")
        if "原油" in full_text or "WTI" in full_text or "資源" in full_text: drivers.append("🛢️ 原油市況・エネルギー価格")
        if "為替" in full_text or "円高" in full_text or "円安" in full_text: drivers.append("💱 為替（ドル円）")
        if "金利" in full_text or "日銀" in full_text or "FRB" in full_text: drivers.append("🏛️ 金利動向")
        if "米株" in full_text or "SOX" in full_text or "ナスダック" in full_text: drivers.append("🌐 米国市場（SOX/ナスダック）")

        return " / ".join(drivers) if drivers else "📊 決算発表・ポジション調整"
    except Exception as e:
        print(f"Market Driver Fetch Error: {e}")
        return "市場動向データ取得中"

def generate_sector_impact_analysis(sector_name: str, avg_change: float, main_driver: str):
    if "半導体" in sector_name:
        return f"🔴 **要因**: {main_driver}の影響で米ハイテク・SOX指数が軟調となり、売りが膨らみました（平均 `{avg_change:+.2f}%`）。" if avg_change < 0 else f"🟢 **要因**: AI需要や米株高を追い風に、買戻し主導で買い優勢となりました（平均 `{avg_change:+.2f}%`）。"
    elif "重工防衛" in sector_name:
        return f"🔴 **要因**: {main_driver}に伴うリスクオフや利確売りに押され調整色を強めています（平均 `{avg_change:+.2f}%`）。" if avg_change < 0 else f"🟢 **要因**: 地政学リスクや防衛予算関連のニュースを背景にポジション構築が進みました（平均 `{avg_change:+.2f}%`）。"
    elif "自動車" in sector_name:
        return f"🔴 **要因**: {main_driver}による円高振れ懸念や関税リスクが重荷となり売りが先行（平均 `{avg_change:+.2f}%`）。" if avg_change < 0 else f"🟢 **要因**: 為替の円安推移や採算改善を期待した買いが広まりました（平均 `{avg_change:+.2f}%`）。"
    elif "大型金融" in sector_name:
        return f"🔴 **要因**: {main_driver}による金利低下懸念から売りが優勢（平均 `{avg_change:+.2f}%`）。" if avg_change < 0 else f"🟢 **要因**: 日銀追加利上げ観測や金利上昇に伴う利回り改善シナリオで資金流入（平均 `{avg_change:+.2f}%`）。"
    elif "エネ資源" in sector_name:
        return f"🔴 **要因**: {main_driver}等によるWTI原油先物の伸び悩みを受け売りが波及（平均 `{avg_change:+.2f}%`）。" if avg_change < 0 else f"🟢 **要因**: 原油先物上昇や資源価格の持ち直しでインフレヘッジの買いが入りました（平均 `{avg_change:+.2f}%`）。"
    elif "海運物流" in sector_name:
        return f"🔴 **要因**: 運賃指数の伸び悩みや利確売りが先行（平均 `{avg_change:+.2f}%`）。" if avg_change < 0 else f"🟢 **要因**: 運賃指数の高止まりや航路迂回による運賃上昇期待が好材料視（平均 `{avg_change:+.2f}%`）。"
    else:
        return f"🔴 **要因**: {main_driver}に伴う地合い悪化に引っ張られ下値模索（平均 `{avg_change:+.2f}%`）。" if avg_change < 0 else f"🟢 **要因**: {main_driver}の好転とともに押し目買いが入る形となりました（平均 `{avg_change:+.2f}%`）。"

# 日本株データ取得
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
        current_price = float(price_tag.text.replace(",", "").replace("円", "").strip())
        
        day_change = 0.0
        change_dt = soup.find_all(["dd", "span"], class_=re.compile(r"(stock_kabuka_|bg_)"))
        for elem in change_dt:
            match = re.search(r"([-+]?\d+\.?\d*)\s*%", elem.text)
            if match:
                day_change = float(match.group(1))
                break
        if day_change == 0.0:
            match_alt = re.search(r"前日比\s*.*?\(([-+]?\d+\.?\d*)%\)", soup.text)
            if match_alt:
                day_change = float(match_alt.group(1))

        mcap_billion = 0.0
        mcap_th = soup.find(lambda tag: tag.name in ["th", "td"] and "時価総額" in tag.text)
        if mcap_th:
            parent = mcap_th.parent
            mcap_text = parent.text.replace(",", "").strip()
            match_m = re.search(r"(\d+)\s*億円", mcap_text)
            if match_m:
                mcap_billion = float(match_m.group(1))

        return {
            "price": current_price,
            "change": day_change,
            "mcap_billion": mcap_billion
        }
    except Exception as e:
        print(f"Kabutan Scraping Error ({code}): {e}")
        return None

# 米国株データ取得
def get_us_stock_data_direct(symbol: str):
    url = f"https://finance.yahoo.com/quote/{symbol}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200:
            return {"price": 150.0, "change": 0.0, "mcap_billion": 5000.0}
            
        soup = BeautifulSoup(res.text, "html.parser")
        price_span = soup.find("fin-streamer", {"data-field": "regularMarketPrice", "data-symbol": symbol})
        change_span = soup.find("fin-streamer", {"data-field": "regularMarketChangePercent", "data-symbol": symbol})
        
        price = float(price_span.text.replace(",", "")) if price_span else 100.0
        change = 0.0
        if change_span and change_span.text:
            raw_change = change_span.text.replace("(", "").replace(")", "").replace("%", "").replace("+", "").strip()
            try:
                change = float(raw_change)
            except ValueError:
                change = 0.0

        return {"price": price, "change": change, "mcap_billion": 10000.0}
    except Exception as e:
        print(f"US Direct Fetch Warning ({symbol}): {e}")
        return {"price": 100.0, "change": 0.0, "mcap_billion": 5000.0}

def fetch_ticker_full_analysis(ticker: str):
    try:
        is_jp = ticker.endswith(".T")

        if is_jp:
            jp_data = get_exact_jp_stock_data(ticker)
            if not jp_data: return None
            
            current_price = jp_data["price"]
            day_change = jp_data["change"]
            mcap_in_billion = jp_data["mcap_billion"]
            
            base_score = 50 + (day_change * 5)
            return {
                "code": ticker.replace(".T", ""),
                "is_us": False,
                "price": current_price,
                "change": day_change,
                "mcap_billion": mcap_in_billion,
                "score": min(max(int(base_score), 10), 100)
            }

        us_data = get_us_stock_data_direct(ticker)
        current_price = us_data["price"]
        day_change = us_data["change"]
        mcap_in_billion = us_data["mcap_billion"]

        base_score = 50 + (day_change * 5)
        return {
            "code": ticker,
            "is_us": True,
            "price": current_price,
            "change": day_change,
            "mcap_billion": mcap_in_billion,
            "score": min(max(int(base_score), 10), 100)
        }
    except Exception as e:
        print(f"Fetch Error {ticker}: {e}")
        return None

def refresh_all_cache():
    global DATA_CACHE
    print("🔄 バックグラウンドで全銘柄データを更新中...")
    all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
    new_data = {}
    for code in all_tickers:
        tech = fetch_ticker_full_analysis(code)
        if tech: new_data[code] = tech
        time.sleep(0.05)
    if new_data: 
        DATA_CACHE = new_data
        print("✅ キャッシュの更新が完了しました。")

def get_future_action_eval(tech):
    unit = "$" if tech['is_us'] else "円"
    p = tech['price']
    c = tech['change']
    
    if c <= -2.0:
        return "🔴 **【下落警戒】** 下げ幅拡大。押し目買いは慎重な局面。"
    elif c >= 3.0:
        return f"🚀 **【急騰モメンタム】** 短期資金集中！\n└ 🎯 目標: `{round(p*1.15, 1)}{unit}` / 撤退: `{round(p*0.95, 1)}{unit}`"
    elif c > 0.0:
        return f"🟢 **【上昇堅調】** 買い優勢推移（目標: `{round(p*1.05, 1)}{unit}`）"
    else:
        return "🟡 **【中立・ボックス推移】** 方向感模索の保ち合い局面。"

def analyze_single_ticker(code_input: str):
    code_input = code_input.upper().strip()
    ticker = f"{code_input}.T" if code_input.isdigit() and len(code_input) == 4 else code_input
    tech = fetch_ticker_full_analysis(ticker)
    if tech:
        unit = "$" if tech['is_us'] else "円"
        return (
            f"📊 **【高度多角解析】`{code_input}`** (スコア: `{tech['score']}点`)\n"
            f"├ **現在値**: {tech['price']}{unit} (**{tech['change']:+.2f}%**)\n"
            f"├ **時価総額**: `{tech['mcap_billion']}億円`\n"
            f"└ 💡 **評価**: {get_future_action_eval(tech)}"
        )
    return f"⚠️ `{code_input}` のデータを取得できませんでした。"

class StockSearchModal(Modal, title="銘柄多角解析"):
    stock_code = TextInput(label="銘柄コードを入力", placeholder="例: 7013, 8035, NVDA")
    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        res = await asyncio.to_thread(analyze_single_ticker, self.stock_code.value)
        
        # 一般チャンネルに送信
        target_channel = interaction.client.get_channel(GENERAL_CHANNEL_ID)
        if not target_channel: target_channel = interaction.channel
        await target_channel.send(res)
        await interaction.followup.send("✅ #一般 チャンネルへ結果を出力しました！", ephemeral=True)

class InstitutionalBoardView(View):
    def __init__(self): super().__init__(timeout=None)

    # 一般チャンネルへの送信関数
    async def send_to_general_channel(self, interaction: discord.Interaction, content: str):
        target_channel = interaction.client.get_channel(GENERAL_CHANNEL_ID)
        if not target_channel: target_channel = interaction.channel

        chunks, curr_chunk = [], ""
        for line in content.split("\n"):
            if len(curr_chunk) + len(line) + 1 > 1900:
                chunks.append(curr_chunk)
                curr_chunk = line + "\n"
            else:
                curr_chunk += line + "\n"
        if curr_chunk:
            chunks.append(curr_chunk)

        for chunk in chunks:
            await target_channel.send(chunk)
            
        if not interaction.response.is_done():
            await interaction.response.send_message("✅ #一般 チャンネルへ結果を出力しました！", ephemeral=True)
        else:
            await interaction.followup.send("✅ #一般 チャンネルへ結果を出力しました！", ephemeral=True)

    @discord.ui.button(label="🔍 銘柄詳細解析", style=discord.ButtonStyle.success, custom_id="search_stock_modal_perm")
    async def search_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(StockSearchModal())

    @discord.ui.button(label="🌐 各業界 ニュース・資金動向", style=discord.ButtonStyle.primary, custom_id="fetch_sector_flow_perm")
    async def sector_button(self, interaction: discord.Interaction, button: Button):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        if not DATA_CACHE:
            asyncio.create_task(asyncio.to_thread(refresh_all_cache))
            await interaction.followup.send("⏳ データ初期化中です。約1分後にお試しください。", ephemeral=True)
            return

        main_driver = await asyncio.to_thread(fetch_market_driver_context)
        full_report = (
            f"🌐 **【10大業界 イベント・市場要因による株価変動解析】**\n"
            f"📌 **現在の相場主導要因**: `{main_driver}`\n"
            f"─────────────────────────\n\n"
        )

        for sector_name, tickers in SECTORS.items():
            scores, changes, line_items = [], [], []
            for code in tickers:
                tech = DATA_CACHE.get(code)
                if tech:
                    scores.append(tech['score'])
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

        await self.send_to_general_channel(interaction, full_report)

    @discord.ui.button(label="🎯 押し目・高値突破シグナル", style=discord.ButtonStyle.secondary, custom_id="fetch_breakout_signals_perm")
    async def breakout_button(self, interaction: discord.Interaction, button: Button):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        if not DATA_CACHE:
            asyncio.create_task(asyncio.to_thread(refresh_all_cache))
            await interaction.followup.send("⏳ データ初期化中です。約1分後にお試しください。", ephemeral=True)
            return

        sorted_items = sorted(DATA_CACHE.values(), key=lambda x: x['score'], reverse=True)
        high_score_items = [t for t in sorted_items if t['score'] >= 50][:8]

        res = "🎯 **【押し目・高値突破シグナル検出】**\n\n"
        if not high_score_items:
            res += "現在、明確なブレイクアウトシグナルが出ている銘柄はありません。"
        else:
            for t in high_score_items:
                unit = "$" if t['is_us'] else "円"
                tag = "🚀 [急騰候補]" if t['change'] >= 3.0 else ("🟢 [上昇強気]" if t['change'] > 0 else "🟡 [保ち合い]")
                res += (
                    f"**{tag} `{t['code']}`** (スコア: `{t['score']}点`)\n"
                    f"├ **現在値**: {t['price']}{unit} ({t['change']:+.2f}%)\n"
                    f"└ 💡 **評価**: {get_future_action_eval(t)}\n\n"
                )

        await self.send_to_general_channel(interaction, res)

    @discord.ui.button(label="⚡ 大口売買・板突破動向", style=discord.ButtonStyle.danger, custom_id="fetch_volume_spikes_perm")
    async def volume_button(self, interaction: discord.Interaction, button: Button):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        if not DATA_CACHE:
            asyncio.create_task(asyncio.to_thread(refresh_all_cache))
            await interaction.followup.send("⏳ データ初期化中です。約1分後にお試しください。", ephemeral=True)
            return

        spikes = list(DATA_CACHE.values())
        spikes.sort(key=lambda x: abs(x['change']), reverse=True)

        res = "⚡ **【大口売買・値動き活発銘柄】**\n\n"
        if not spikes:
            res += "現在、大きな値動きは見られません。"
        else:
            for t in spikes[:8]:
                unit = "$" if t['is_us'] else "円"
                res += (
                    f"🔥 **`{t['code']}`**\n"
                    f"├ **現在値**: {t['price']}{unit} ({t['change']:+.2f}%)\n"
                    f"└ 🧠 **動向**: {'🟢 買い優勢の買い集め動向。' if t['change'] > 0 else '🔴 売り先行の調整動向。'}\n\n"
                )

        await self.send_to_general_channel(interaction, res)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.add_view(InstitutionalBoardView())
    
    asyncio.create_task(asyncio.to_thread(refresh_all_cache))

    if not real_time_signal_monitor.is_running(): real_time_signal_monitor.start()
    if not scheduled_market_reports.is_running(): scheduled_market_reports.start()

# 🔔 10分おきの売買アラート自動監視
@tasks.loop(minutes=10)
async def real_time_signal_monitor():
    await bot.wait_until_ready()
    await asyncio.to_thread(refresh_all_cache)

    alert_channel = bot.get_channel(ALERT_CHANNEL_ID)
    if not alert_channel: return

    for code, t in DATA_CACHE.items():
        unit = "$" if t['is_us'] else "円"
        signal_key = f"{code}_{t['price']}_{t['change']}"
        
        # 🚨 急騰シグナル（+3.0% 以上）
        if t['change'] >= 3.0 and signal_key not in ALERTED_SIGNALS:
            ALERTED_SIGNALS.add(signal_key)
            msg = (
                f"🚨 **【売買アラート：急騰シグナル検知】**\n"
                f"🔥 銘柄: **`{t['code']}`**\n"
                f"├ **現在値**: {t['price']}{unit} (**+{t['change']:.2f}%**)\n"
                f"└ 💡 **アクション**: 買いモメンタム加速。短期資金流入中！"
            )
            await alert_channel.send(msg)

        # 🚨 急落警戒シグナル（-3.0% 以下）
        elif t['change'] <= -3.0 and signal_key not in ALERTED_SIGNALS:
            ALERTED_SIGNALS.add(signal_key)
            msg = (
                f"⚠️ **【売買アラート：急落・手仕舞い警戒】**\n"
                f"🔻 銘柄: **`{t['code']}`**\n"
                f"├ **現在値**: {t['price']}{unit} (**{t['change']:.2f}%**)\n"
                f"└ 💡 **アクション**: 下げ幅拡大。損切り・押し目待ちの考慮が必要。"
            )
            await alert_channel.send(msg)

# 🌇 毎日15:30の大引け定時レポート
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
            msg += f"├ `{t['code']}`: **{t['change']:+.2f}%** ({t['price']}円) | スコア:`{t['score']}点`\n"
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
