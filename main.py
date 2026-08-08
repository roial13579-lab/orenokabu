import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import datetime
import requests
import random
import discord
from discord.ext import commands
from discord.ui import Button, View

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

# Step 1で取得したBotのトークンをここに貼り付けます
TOKEN = "MTUzNTYzNjc4MzU1ODA0MTY0MA.Gtp5RX.I0mHrbwMsKOJT-yWz6E50oYkpGUvj2ENnSPbZ4"

WATCH_LIST = {
    "7203": "トヨタ自動車",
    "8035": "東京エレクトロン",
    "9984": "ソフトバンクG"
}

class BoardView(View):
    def __init__(self):
        super().__init__(timeout=None)  # 永続ボタン

    @discord.ui.button(label="📊 最新の板情報を取得", style=discord.ButtonStyle.primary, custom_id="fetch_board_data")
    async def fetch_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        
        # 板情報の模擬レポート生成
        report = f"**【リアルタイム板精査レポート】** ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
        for code, name in WATCH_LIST.items():
            buy_vol = random.randint(1000, 5000) * 100
            sell_vol = random.randint(1000, 5000) * 100
            ratio = round(buy_vol / sell_vol, 2)
            
            status = "買い優勢 🟢" if ratio > 1.2 else ("売り優勢 🔴" if ratio < 0.8 else "拮抗 🟡")
            report += f"🔹 **{name} ({code})**\n"
            report += f"   - 買い気配数量: {buy_vol:,} 株\n"
            report += f"   - 売り気配数量: {sell_vol:,} 株\n"
            report += f"   - 需給倍率: {ratio} ({status})\n\n"
            
        await interaction.followup.send(report)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

@bot.command()
async def panel(ctx):
    """ !panel コマンドでボタン付きメッセージをDiscordに送信 """
    view = BoardView()
    await ctx.send("下部ボタンを押すと、いつでもリアルタイムの板情報を精査・取得します 📊", view=view)

bot.run(TOKEN)
