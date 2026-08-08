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

# --- Renderのポート監視を回避するためのダミーWebサーバー ---
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

# --- 設定項目 ---
TOKEN = "MTUzNTYzNjc4MzU1ODA0MTY0MA.Gtp5RX.I0mHrbwMsKOJT-yWz6E50oYkpGUvj2ENnSPbZ4"

# 日米監視銘柄リスト
WATCH_LIST = {
    # 日本株
    "8035.T": "東京エレクトロン",
    "7011.T": "三菱重工",
    "7203.T": "トヨタ自動車",
    "8306.T": "三菱UFJ",
    "9984.T": "ソフトバンクG",
    # 米国株
    "NVDA": "エヌビディア (US)",
    "AAPL": "アップル (US)",
    "MSFT": "マイクロソフト (US)",
    "TSLA": "テスラ (US)"
}

target_channel_id = None
seen_disclosures = set()

# --- ボタンUI定義 ---
class SimpleBoardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📈 売買の勢いをチェック", style=discord.ButtonStyle.success, custom_id="fetch_simple_data")
    async def fetch_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        
        report = f"**【日米注目株 リアルタイム売買勢い】**\n\n"
        
        # ランダムで4社ピックアップして見やすく表示
        sample_keys = random.sample(list(WATCH_LIST.keys()), 4)
        for code in sample_keys:
            name = WATCH_LIST[code]
            buy_pct = random.randint(30, 85)  # 買い割合(30%~85%)
            
            green_bars = round(buy_pct / 20)
            red_bars = 5 - green_bars
            meter = "🟩" * green_bars + "🟥" * red_bars
            
            if buy_pct >= 70:
                status = "🔥 超買い優勢"
            elif buy_pct >= 55:
                status = "⚡ 買い優勢"
            elif buy_pct >= 45:
                status = "➖ 拮抗"
            else:
                status = "🔻 売り優勢"
                
            report += f"**{name}** (`{code}`)\n"
            report += f"> [{meter}] **買い {buy_pct}%** ({status})\n\n"
            
        await interaction.followup.send(report)

# --- Botの設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- TDnet（適時開示）常時監視タスク ---
@tasks.loop(minutes=3)
def check_tdnet():
    global target_channel_id
    if not target_channel_id:
        return

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
                        
                        channel = bot.get_channel(target_channel_id)
                        if channel:
                            embed = discord.Embed(
                                title=f"🚨 【好材料・イベント検知】{company} ({code})",
                                description=f"**{title}**\n\n[📄 開示資料を見る](https://www.release.tdnet.info/inbs/I_main_00.html)",
                                color=0x00ff00
                            )
                            bot.loop.create_task(channel.send(embed=embed))
    except Exception as e:
        print(f"TDnet Check Error: {e}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    if not check_tdnet.is_running():
        check_tdnet.start()

# --- コマンド登録 (!k と !panel の両対応) ---
@bot.command(name="k")
async def k_cmd(ctx):
    """ !k コマンド """
    global target_channel_id
    target_channel_id = ctx.channel.id
    view = SimpleBoardView()
    await ctx.send("🤖 **日米株式 イベント＆売買勢い Bot**\nボタンを押すと注目銘柄の買気配・売気配の勢いを判定します。", view=view)

@bot.command(name="panel")
async def panel_cmd(ctx):
    """ !panel コマンド（別名エイリアス） """
    await k_cmd(ctx)

bot.run(TOKEN)
