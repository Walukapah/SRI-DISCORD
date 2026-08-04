import os
import sys
import discord
from discord.ext import commands
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ============================================
# CONFIG - Environment variable එකෙන් ගන්නවා
# ============================================
TOKEN = os.getenv("DISCORD_TOKEN", "MTQzMzExMDMwNzM1NzcyMDY5Nw.GFKSjG.8DI8-72_EKiE7IYkhddWh_5RKDogCKYX8Z4Eq8").strip()

# ============================================
# HTTP SERVER - Render එක happy තියන්න
# ============================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        status = "🟢 Online" if bot_ready else "🔴 Offline"
        html = f"""<!DOCTYPE html>
<html>
<head><title>SRI Bot</title><meta charset="utf-8"></head>
<body style="font-family:Arial;padding:40px;background:#1a1a2e;color:#fff">
    <h1>🤖 SRI Discord Bot</h1>
    <h2>Status: {status}</h2>
    <p>Prefix: <code>!</code></p>
    <p>Commands: <code>!ping</code></p>
</body></html>"""
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        pass

def start_server():
    port = int(os.getenv("PORT", "7860"))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"[HTTP] Server running on port {port}")
    server.serve_forever()

# ============================================
# DISCORD BOT
# ============================================
bot_ready = False

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    global bot_ready
    bot_ready = True
    print(f"=" * 50)
    print(f"✅ BOT IS ONLINE!")
    print(f"✅ Name: {bot.user}")
    print(f"✅ ID: {bot.user.id}")
    print(f"✅ Prefix: !")
    print(f"=" * 50)
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, name="!ping"))

@bot.command()
async def ping(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! `{latency}ms`")

@bot.command()
async def hello(ctx):
    """Say hello"""
    await ctx.send(f"👋 Hello {ctx.author.mention}! Bot is working!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"[ERROR] {error}")

# ============================================
# START
# ============================================
def run_bot():
    if not TOKEN:
        print("\n" + "=" * 50)
        print("❌ ERROR: DISCORD_TOKEN not set!")
        print("=" * 50)
        print("\n👉 Render Dashboard → Environment")
        print("👉 Add: DISCORD_TOKEN = your_bot_token")
        print("👉 Redeploy!")
        print("\n📝 Get token: https://discord.com/developers/applications")
        print("=" * 50 + "\n")
        return
    
    # Quick token format check
    parts = TOKEN.split('.')
    if len(parts) != 3 or len(TOKEN) < 50:
        print(f"\n❌ Token format looks wrong! Length: {len(TOKEN)}")
        print(f"❌ Token: {TOKEN[:20]}...")
        print("❌ Make sure you copied the FULL token!\n")
        return
    
    print(f"[BOT] Token found (length: {len(TOKEN)})")
    print(f"[BOT] Starting bot...")
    
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("\n" + "=" * 50)
        print("❌ LOGIN FAILED: Invalid token!")
        print("=" * 50)
        print("\n👉 Go to Discord Developer Portal")
        print("👉 Bot → Reset Token → Copy NEW token")
        print("👉 Update DISCORD_TOKEN in Render and redeploy")
        print("=" * 50 + "\n")
    except Exception as e:
        print(f"\n❌ Bot error: {e}\n")

if __name__ == "__main__":
    # Start HTTP server in background
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Start Discord bot in main thread
    run_bot()
