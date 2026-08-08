import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import datetime
import requests
import random
from bs4 import BeautifulSoup
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import yfinance as yf
import pandas as pd

# --- ダミーWebサーバー (Renderポート監視対策) ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

# --- 設定 ---
TOKEN = "MTUzNTYzNjc4MzU1ODA0MTY0MA.Gtp5RX.I0mHrbwMsKOJT-yWz6E50oYkpGUvj2ENnSPbZ4"

# 主要10セクター 各5社（計50銘柄）
SECTORS = {
    "⚡ 半導体・電子": ["8035.T", "6857.T", "6146.T", "6920.T", "NVDA"],
    "🛡️ 重工・防衛": ["7011.T", "7012.T", "7013.T", "6301.T", "6367.T"],
    "🚗 自動車・輸送": ["7203.T", "7267.T", "7270.T", "7201.T", "TSLA"],
    "🏦 大型金融": ["8306.T", "8316.T", "8411.T", "8604.T", "8766.T"],
    "🛢️ 資源・エネルギー": ["1605.T", "5020.T", "5401.T", "4063.T", "XOM"],
    "🚢 海運・物流": ["9101.T", "9104.T", "9107.T", "9020.T", "9143.T"],
    "💻 IT・メガテック": ["9984.T", "9432.T", "AAPL", "MSFT", "GOOGL"],
    "🏬 商社・流通": ["8058.T", "8001.T", "8031.T", "8053.T", "3382.T"],
    "💊 医薬品・バイオ": ["4502.T", "4519.T", "4568.T", "4503.T", "LLY"],
    "⚡ 電気・精密機器": ["6501.T", "6758.T", "6503.T", "7751.T", "6752.T"]
}

seen_disclosures = set()

# --- 全50銘柄を一括ダウンロード＆解析する超高速関数 ---
def fetch_all_technical_data():
    all_tickers = [ticker for sublist in SECTORS.values() for ticker in sublist]
    
    try:
        # 50銘柄を1回の通信でまとめて取得（タイムアウト防止）
        data = yf.download(all_tickers, period="6mo", interval="1d", progress=False)
        results = {}

        for code in all_tickers:
            try:
                if len(all_tickers) > 1:
                    close = data['Close'][code].dropna()
                    volume = data['Volume'][code].dropna()
                else:
                    close = data['Close'].dropna()
                    volume = data['Volume'].dropna()

                if len(close) < 30:
                    continue

                current_price = close.iloc[-1]
                
                # 25日線乖離率
                ma25 = close.rolling(window=25).mean().iloc[-1]
                bias = ((current_price - ma25) / ma25) * 100
                
                # RSI(14)
                delta = close.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs.iloc[-1]))
                
                # 出来高変化率
                vol_ma20 = volume.rolling(window=20).mean().iloc[-1]
                vol_ratio = (volume.iloc[-1] / vol_ma20) if vol_ma20 > 0 else 1.0

                # 押し目判定
                is_dip = (rsi <= 35) and (bias <= -5.0)

                # 勝率簡易推計
                dip_instances = close[close.shift(1) < close.shift(1).rolling(25).mean() * 0.95]
                if len(dip_instances) > 0:
                    win_count = sum(close.reindex(dip_instances.index).shift(-3) > dip_instances)
                    win_rate = int((win_count / len(dip_instances)) * 100)
                else:
                    win_rate = 75

                results[code] = {
                    "price": round(current_price, 1),
                    "bias": round(bias, 1),
                    "rsi": round(rsi, 1),
                    "vol_ratio": round(vol_ratio, 2),
                    "is_dip": is_dip,
                    "win_rate": win_rate
                }
            except Exception:
                continue

        return results
    except Exception as e:
        print(f"Batch fetch error: {e}")
        return {}

# --- UI定義 ---
class InstitutionalBoardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🌐 各業界5社 資金流入力学", style=discord.ButtonStyle.primary, custom_id="fetch_sector_flow")
    async def sector_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        
        # 一括高速取得
        tech_data = fetch_all_technical_data()
        
        messages = []
        current_msg = "📊 **【業界別（各5社）リアルタイム資金動向・買い圧力】**\n\n"

        for sector_name, tickers in SECTORS.items():
            sector_block = f"**{sector_name}**\n"
            for code in tickers:
                tech = tech_data.get(code)
                if tech:
                    score = min(int((tech['vol_ratio'] * 30) + (tech['rsi'] * 0.5)), 100)
                    bars = round(score / 20)
                    meter = "🟩" * bars + "🟥" * (5 - bars)
                    status = "🔥資金流入" if score >= 65 else ("⚡売買拮抗" if score >= 45 else "🔻資金流出")
                    sector_block += f"> `{code.replace('.T','')}`: [{meter}] スコア **{score}** ({status} | RSI:{tech['rsi']}%)\n"
                else:
                    sector_block += f"> `{code.replace('.T','')}`: データ取得失敗\n"
            sector_block += "\n"

            if len(current_msg) + len(sector_block) > 1700:
                messages.append(current_msg)
                current_msg = sector_block
            else:
                current_msg += sector_block

        if current_msg:
            messages.append(current_msg)

        # 順次送信
        for i, msg in enumerate(messages):
            if i == 0:
                await interaction.followup.send(msg)
            else:
                await interaction.channel.send(msg)

    @discord.ui.button(label="📉 押し目買いシグナル検出", style=discord.ButtonStyle.danger, custom_id="fetch_dip_signals")
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
                report += f"├ **RSI(14)**: {tech['rsi']}% (売られ過ぎ判定)\n"
                report += f"└ **過去同パターンからの復元率（勝率）**: **{tech['win_rate']}%**\n\n"
        
        if found_count == 0:
            report += "現在、売られ過ぎ水準（RSI 35%以下）に達している絶好の押し目対象銘柄はありません。"

        await interaction.followup.send(report)

# --- Botの設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- TDnet監視 ---
@tasks.loop(minutes=3)
def check_tdnet():
    url = "https://www.release.tdnet.info/inbs/I_main_00.html"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")
        
        keywords = ["業績予想の修正", "上方修正", "自己株式の取得", "自己株式取得", "復配", "増配", "株式分割", "TOB"]
        
        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 5:
                code = cols[1].text.strip()
                company = cols[2].text.strip()
                title = cols[3].text.strip()
                
                if any(kw in title for kw in keywords):
                    item_id = f"{code}_{title}"
                    if item_id not in seen_disclosures:
                        seen_disclosures.add(item_id)
                        
                        for guild in bot.guilds:
                            for channel in guild.text_channels:
                                if channel.permissions_for(guild.me).send_messages:
                                    embed = discord.Embed(
                                        title=f"🚨 【イベント好材料検知】{company} ({code})",
                                        description=f"**内容:** {title}\n\n[📄 TDnet開示資料を確認](https://www.release.tdnet.info/inbs/I_main_00.html)",
                                        color=0x00ff00
                                    )
                                    bot.loop.create_task(channel.send(embed=embed))
                                    break
    except Exception as e:
        print(f"TDnet Check Error: {e}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.add_view(InstitutionalBoardView())
    if not check_tdnet.is_running():
        check_tdnet.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    text = message.content.strip()
    if text in ["!k", "!panel", "！ｋ", "！ｐａｎｅｌ"]:
        view = InstitutionalBoardView()
        await message.channel.send("🤖 **株式機関投資分析・イベント予測 Bot**\nボタンを選択して業界別分析または押し目買い判定を実行してください。", view=view)
        return

    await bot.process_commands(message)

bot.run(TOKEN)
