import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

# 讀取 .env 檔案裡的金鑰
load_dotenv()

# 設定機器人基本架構
class SummarizerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    # 當機器人連線時，將斜線指令（/summarize）同步給 Discord 伺服器
    async def setup_hook(self):
        await self.tree.sync()
        print(" 斜線指令已成功同步至伺服器！")

bot = SummarizerBot()

# 建立 Google Gemini 連線客戶端
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 機器人成功開機通知
@bot.event
async def on_ready():
    print(f" 哈哈是我啦，機器人已上線！目前登入身分：{bot.user}")

# === 定義 /summarize 指令 ===
# 設定冷卻規則：同一個頻道 (channel_id) 60 秒內只能執行 1 次
@bot.tree.command(name="summarize", description="統整本文字頻道的近期聊天內容")
@app_commands.checks.cooldown(1, 60.0, key=lambda i: i.channel_id)
async def summarize(interaction: discord.Interaction, limit: int = 50):
    # 先告訴 Discord「機器人思考中」，避免因 AI 運算超過 3 秒而跳出錯誤
    await interaction.response.defer()

    # 1. 抓取頻道近期訊息
    messages = []
    async for msg in interaction.channel.history(limit=limit):
        # 過濾掉機器人自己發的訊息與空白訊息
        if not msg.author.bot and msg.content.strip():
            messages.append(f"{msg.author.display_name}: {msg.content}")

    # 2. 將訊息按時間反轉（從舊到新排列）
    messages.reverse()
    chat_log = "\n".join(messages)

    # 若抓不到有效文字則停止
    if not chat_log:
        await interaction.followup.send("此頻道最近沒有足夠的文字內容可供摘要。")
        return

    # 3. 組裝發給 Gemini 的提示詞
    prompt = (
        "請扮演專業的繁體中文社群助理，仔細閱讀以下 Discord 聊天紀錄，"
        "並條列整理出「討論核心重點」與「待處理事項/決策結論」：\n\n"
        f"{chat_log}"
    )

    # 4. 呼叫 Gemini AI 進行分析
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )
        # 將 AI 生成的摘要發送到頻道中
        await interaction.followup.send(response.text)

    except genai_errors.APIError as e:
        await interaction.followup.send(f" 特緊繃Google API 掛了：{e.message}")
    except Exception as e:
        await interaction.followup.send(f" 統整失敗，發生未預期錯誤，但也不排除錯在你身上：{e}")

# === 錯誤處理機制（攔截冷卻提示） ===
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        # 只有按指令的人看得到這則冷卻提示（ephemeral=True）
        await interaction.response.send_message(
            f" 兄弟別洗頻阿!頻道冷卻中，為避免觸發 API 頻率限制，請在 **{error.retry_after:.1f} 秒**後再試。",
            ephemeral=True
        )
    else:
        print(f"發生未預期錯誤: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("執行指令時發生錯誤，請稍後再試。", ephemeral=True)

# 啟動機器人
bot.run(os.getenv("DISCORD_TOKEN"))