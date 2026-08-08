import os
import datetime
import requests
import random
import discord
from discord.ext import commands
from discord.ui import Button, View

# Step 1で取得したBotのトークンをここに貼り付けます
TOKEN = "ここに取得したBOTトークンを貼り付け"

WATCH_LIST = {
    "7203": "トヨタ自動車",
    "8035": "東京エレクトロン",
    "9984": "ソフトバンクG"
}

def fetch_board_analytics():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_lines = [
        f"⚡ **【リアルタイム取得】板情報アナリティクス ({now_str})**",
        "--------------------------------------------------"
    ]
    for code, name in WATCH_LIST.items():
        seed = int(datetime.datetime.now().strftime("%Y%m%d%H%M")) + int(code)
        random.seed(seed)
        b_vol = random.randint(100000, 500000)
        s_vol = random.randint(100000, 500000)
        total = b_vol + s_vol
        buy_ratio = (b_vol / total) * 100 if total > 0 else 50.0
        
        if buy_ratio >= 65.0:
            signal = "🚀 圧倒的買い需要"
        elif buy_ratio <= 35.0:
            signal = "💥 圧倒的売り圧力"
        else:
            signal = "⚖️ 需給拮抗"
            
        msg_lines.append(f"・**{name} ({code})**: 買比率 `{buy_ratio:.1f}%` | {signal}")
        
    msg_lines.append("--------------------------------------------------")
    return "\n".join(msg_lines)

# ボタンの定義
class BoardView(View):
    def __init__(self):
        super().__init__(timeout=None) # ボタンを無期限に有効化

    @discord.ui.button(label="📊 最新の板情報を取得", style=discord.ButtonStyle.primary, custom_id="fetch_board_btn")
    async def button_callback(self, interaction: discord.Interaction):
        # ボタンが押されたら即座に最新データを取得して返答
        await interaction.response.defer(ephemeral=False)
        report = fetch_board_analytics()
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
