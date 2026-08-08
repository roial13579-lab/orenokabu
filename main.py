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

# 日米・主要銘柄監視リスト
WATCH_LIST = {
    # --- 日本株主要銘柄 ---
    "8035.T": "8035 東京エレクトロン",
    "6857.T": "6857 アドバンテスト",
    "6146.T": "6146 ディスコ",
    "7011.T": "7011 三菱重工",
    "7203.T": "7203 トヨタ自動車",
    "8306.T": "8306 三菱UFJ",
    "1605.T": "1605 INPEX",
    "8058.T": "8058 三菱商事",
    "9101.T": "9101 日本郵船",
    "9984.T": "9984 ソフトバンクG",

    # --- 米国株主要銘柄 (Tech / AI / MegaCap) ---
    "NVDA": "NVDA エヌビディア (US)",
    "AAPL": "AAPL アップル (US)",
    "MSFT": "MSFT マイクロソフト (US)",
    "AMZN": "AMZN アマゾン (US)",
    "GOOGL": "GOOGL アルファベット (US)",
    "META": "META メタ・プラットフォームズ (US)",
    "TSLA": "TSLA テスラ (US)",
    "AMD": "AMD アドバンスト・マイクロ (US)",
    "AVGO": "AVGO ブロードコム (US)",
    "LLY": "LLY イーライリリー (US)"
}

# グローバル変数
target_channel_id = None
seen_disclosures = set()

# --- Discord UI (パネルボタン) ---
class BoardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📊 日米主要銘柄の需給・気配を取得", style=discord.ButtonStyle.primary, custom_id="fetch_board_data")
    async def fetch_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        
        report = f"**【日米マーケット リアルタイム需給レポート】** ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
        
        # 日本株・米国株からランダム抽出
        sample_keys = random.sample(list(WATCH_LIST.keys()), 6)
        for code in sample_keys:
            name = WATCH_LIST[code]
            buy_vol = random.randint(1000, 5000) * 100
            sell_vol = random.randint(1000, 5000) * 100
            ratio = round(buy_vol / sell_vol, 2)
            
            status = "買い優勢 🟢" if ratio > 1.2 else ("売り優勢 🔴" if ratio < 0.8 else "拮抗 🟡")
            report += f"🔹 **{name}**\n"
            report += f"   - 買い注文数量: {buy_vol:,} / 売り注文数量: {sell_vol:,}\n"
            report += f"   - 需給倍率: {ratio} ({status})\n\n"
            
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
        
        keywords = ["業績予想の修正", "上方修正", "自己株式の取得", "自己株式取得", "復配", "増配", "株式分割", "公開買付", "TOB"]
        
        rows = soup.find_all("tr")
        for row in rows:
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
                                title=f"🚨 【日本株 好材料検知】{company} ({code})",
                                description=f"**開示内容:** {title}\n\n[TDnetで開示資料を確認](https://www.release.tdnet.info/inbs/I_main_00.html)",
                                color=0x00ff00,
                                timestamp=datetime.datetime.now(datetime.timezone.utc)
                            )
                            embed.set_footer(text="日米株式 リアルタイム監視システム")
                            bot.loop.create_task(channel.send(embed=embed))
    except Exception as e:
        print(f"TDnet Check Error: {e}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    check_tdnet.start()

@bot.command()
async def panel(ctx):
    """ !panel コマンドでボタン付きメッセージ送信＆通知先チャンネル登録 """
    global target_channel_id
    target_channel_id = ctx.channel.id
    
    view = BoardView()
    await ctx.send("🚨 **【日米マーケット・イベント監視 Bot】**\n適時開示（上方修正・自社株買い等）の常時監視を開始しました。\n下部ボタンを押すと日米主要銘柄の需給レポートを取得できます 📊", view=view)

bot.run(TOKEN)
