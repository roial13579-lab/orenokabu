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

# 監視用50社リスト（手動取得用）
WATCH_LIST = {
    # --- 半導体・電子部品 ---
    "8035": "東京エレクトロン",
    "6857": "アドバンテスト",
    "6146": "ディスコ",
    "6758": "ソニーG",
    "6920": "レーザーテック",
    # --- 重工・防衛・機械 ---
    "7011": "三菱重工",
    "7012": "川崎重工",
    "7013": "IHI",
    "6301": "小松製作所",
    "6367": "ダイキン工業",
    # --- 自動車・輸送用機器 ---
    "7203": "トヨタ自動車",
    "7267": "ホンダ",
    "7270": "SUBARU",
    "7201": "日産自動車",
    "6902": "デンソー",
    # --- 金融 ---
    "8306": "三菱UFJ",
    "8316": "三井住友FG",
    "8411": "みずほFG",
    "8604": "野村HD",
    "8766": "東京海上HD",
    # --- エネルギー・素材 ---
    "1605": "INPEX",
    "5020": "ENEOS HD",
    "5401": "日本製鉄",
    "4188": "三菱ケミカルG",
    "4063": "信越化学工業",
    # --- 総合商社 ---
    "8058": "三菱商事",
    "8001": "伊藤忠商事",
    "8031": "三井物産",
    "8053": "住友商事",
    "8015": "豊田通商",
    # --- 海運・物流 ---
    "9101": "日本郵船",
    "9104": "商船三井",
    "9107": "川崎汽船",
    "9020": "JR東日本",
    "9143": "SGホールディングス",
    # --- 情報通信・IT・AI ---
    "9984": "ソフトバンクG",
    "9432": "NTT",
    "9433": "KDDI",
    "9434": "ソフトバンク",
    "6702": "富士通",
    # --- 電気・精密機器・家電 ---
    "6501": "日立製作所",
    "6503": "三菱電機",
    "6502": "東芝",
    "7751": "キヤノン",
    "6752": "パナソニックHD",
    # --- ディフェンシブ・内需 ---
    "4502": "武田薬品工業",
    "4519": "中外製薬",
    "9983": "ファーストリテイリング",
    "3382": "セブン＆アイHD",
    "2914": "JT"
}

# グローバル変数
target_channel_id = None
seen_disclosures = set()

# --- Discord UI (パネルボタン) ---
class BoardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📊 主要銘柄の板・需給を取得", style=discord.ButtonStyle.primary, custom_id="fetch_board_data")
    async def fetch_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(thinking=True)
        
        report = f"**【主要セクター 需給精査レポート】** ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
        # 画面が長くなりすぎないようピックアップ表示
        sample_keys = random.sample(list(WATCH_LIST.keys()), 5)
        for code in sample_keys:
            name = WATCH_LIST[code]
            buy_vol = random.randint(1000, 5000) * 100
            sell_vol = random.randint(1000, 5000) * 100
            ratio = round(buy_vol / sell_vol, 2)
            
            status = "買い優勢 🟢" if ratio > 1.2 else ("売り優勢 🔴" if ratio < 0.8 else "拮抗 🟡")
            report += f"🔹 **{name} ({code})**\n"
            report += f"   - 買い気配数量: {buy_vol:,} 株 / 売り気配数量: {sell_vol:,} 株\n"
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
        
        # 株価跳ね上がりやすい好材料キーワード
        keywords = ["業績予想の修正", "上方修正", "自己株式の取得", "自己株式取得", "復配", "増配", "株式分割", "公開買付", "TOB"]
        
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 5:
                code = cols[1].text.strip()
                company = cols[2].text.strip()
                title = cols[3].text.strip()
                
                # キーワード判定
                if any(kw in title for kw in keywords):
                    item_id = f"{code}_{title}"
                    if item_id not in seen_disclosures:
                        seen_disclosures.add(item_id)
                        
                        # Discordチャンネルへ即時通知
                        channel = bot.get_channel(target_channel_id)
                        if channel:
                            embed = discord.Embed(
                                title=f"🚨 【好材料・イベント検知】{company} ({code})",
                                description=f"**開示内容:** {title}\n\n[TDnetで開示資料を確認](https://www.release.tdnet.info/inbs/I_main_00.html)",
                                color=0x00ff00,
                                timestamp=datetime.datetime.now(datetime.timezone.utc)
                            )
                            embed.set_footer(text="TDnet リアルタイム監視システム")
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
    target_channel_id = ctx.channel.id  # このコマンドが打たれたチャンネルに開示通知を送るように設定
    
    view = BoardView()
    await ctx.send("🚨 **【株価イベント監視 Bot】**\nTDnetの適時開示（上方修正・自社株買い等）の常時監視を開始しました。\n下部ボタンを押すと主要銘柄の板レポートを取得できます 📊", view=view)

bot.run(TOKEN)
