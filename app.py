import os
import sys
import asyncio
import discord
from discord.ext import commands
from pathlib import Path
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from config import config_manager, BASE_CONFIG
from github_backup import backup

# Bot storage
active_bots = {}
main_bot_instance = None

# ============================================
# HTTP SERVER FOR RENDER (PORT 7860)
# ============================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        main_status = "🟢 Online" if (main_bot_instance and main_bot_instance.is_ready()) else "🔴 Offline"
        
        html = f"""<!DOCTYPE html>
<html>
<head><title>SRI Discord Bot</title></head>
<body style="font-family: Arial; padding: 40px;">
    <h1>🤖 SRI Discord Bot Service</h1>
    <p><b>Main Bot:</b> {main_status}</p>
    <p><b>Sub Bots:</b> {len(active_bots)}</p>
    <p><b>Uptime:</b> Running</p>
    <hr>
    <p>Use <code>/pair</code> in Discord to connect your bot!</p>
</body>
</html>"""
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        pass

def start_http_server():
    port = int(os.getenv("PORT", "7860"))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"[HTTP] Health server running on http://0.0.0.0:{port}")
    server.serve_forever()

# ============================================
# DISCORD BOT
# ============================================
class SubBot(commands.Bot):
    def __init__(self, config: dict, **kwargs):
        self.bot_config = config
        self.bot_id = config.get("BOT_ID", "unknown")
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        
        super().__init__(
            command_prefix=config.get("PREFIX", "."),
            intents=intents,
            help_command=None,
            **kwargs
        )
    
    async def setup_hook(self):
        await self.load_plugins()
        try:
            synced = await self.tree.sync()
            print(f"[BOT {self.bot_id}] Synced {len(synced)} slash commands")
        except Exception as e:
            print(f"[BOT {self.bot_id}] Sync error: {e}")
    
    async def load_plugins(self):
        plugins_dir = Path(__file__).parent / "plugin"
        if not plugins_dir.exists():
            return
        for file in plugins_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue
            try:
                await self.load_extension(f"plugin.{file.stem}")
                print(f"[BOT {self.bot_id}] Loaded plugin: {file.stem}")
            except Exception as e:
                print(f"[BOT {self.bot_id}] Failed to load {file.stem}: {e}")
    
    async def on_ready(self):
        print(f"[BOT {self.bot_id}] ✅ Logged in as {self.user} (ID: {self.user.id})")
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{self.bot_config.get('BOT_NAME', 'SRI-BOT')} | {self.command_prefix}help"
        )
        await self.change_presence(activity=activity)
    
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: `{error.param.name}`")
        else:
            print(f"[BOT {self.bot_id}] Command error: {error}")
            await ctx.send("❌ An error occurred while processing the command.")

class MainBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix=BASE_CONFIG.get("PREFIX", "."),
            intents=intents,
            help_command=None
        )
    
    async def setup_hook(self):
        plugins_dir = Path(__file__).parent / "plugin"
        if plugins_dir.exists():
            for file in plugins_dir.glob("*.py"):
                if file.name.startswith("_"):
                    continue
                try:
                    await self.load_extension(f"plugin.{file.stem}")
                except Exception as e:
                    print(f"[MAIN] Plugin load error: {e}")
        
        self.tree.add_command(discord.app_commands.Command(
            name="pair", description="Connect your own bot token as a sub-bot",
            callback=self.pair_command
        ))
        self.tree.add_command(discord.app_commands.Command(
            name="bots", description="List all connected sub-bots",
            callback=self.bots_command
        ))
        self.tree.add_command(discord.app_commands.Command(
            name="unpair", description="Disconnect your sub-bot",
            callback=self.unpair_command
        ))
        
        try:
            synced = await self.tree.sync()
            print(f"[MAIN] Synced {len(synced)} slash commands")
        except Exception as e:
            print(f"[MAIN] Sync error: {e}")
    
    async def pair_command(self, interaction: discord.Interaction, token: str):
        await interaction.response.defer(ephemeral=True)
        
        if not token or len(token) < 50:
            await interaction.followup.send("❌ Invalid bot token! Must be 50+ chars.", ephemeral=True)
            return
        
        bot_id = config_manager.get_bot_id(token)
        if bot_id in active_bots:
            await interaction.followup.send(f"⚠️ Bot already connected! (ID: `{bot_id}`)", ephemeral=True)
            return
        
        config = config_manager.create_config(
            token=token, owner_id=str(interaction.user.id),
            extra={"PAIRED_BY": str(interaction.user.id), "PAIRED_BY_NAME": interaction.user.name,
                   "GUILD_ID": str(interaction.guild_id) if interaction.guild_id else None}
        )
        
        try:
            bot = SubBot(config)
            await bot.start(token)
            active_bots[bot_id] = bot
            await interaction.followup.send(
                f"✅ **Sub-bot connected!**\n🆔 `{bot_id}` | Prefix: `{config['PREFIX']}`", ephemeral=True
            )
            backup.save_file(f"bot_{bot_id}.json",
                {"status": "connected", "owner": str(interaction.user.id), "bot_id": bot_id},
                f"Bot {bot_id} connected")
        except discord.LoginFailure:
            config_manager.delete_config(bot_id)
            await interaction.followup.send("❌ **Invalid token!** Check https://discord.com/developers/applications", ephemeral=True)
        except Exception as e:
            config_manager.delete_config(bot_id)
            await interaction.followup.send(f"❌ Error: `{str(e)}`", ephemeral=True)
    
    async def bots_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not active_bots:
            await interaction.followup.send("📭 No sub-bots connected.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🤖 Connected Sub-Bots", color=discord.Color.blue(),
                              description=f"Total: {len(active_bots)}")
        for bot_id, bot in active_bots.items():
            cfg = bot.bot_config
            status = "🟢 Online" if bot.is_ready() else "🟡 Connecting"
            embed.add_field(name=f"Bot `{bot_id}`",
                value=f"Status: {status}\nName: `{bot.user}`\nPrefix: `{cfg.get('PREFIX', '.')}`", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def unpair_command(self, interaction: discord.Interaction, bot_id: str = None):
        await interaction.response.defer(ephemeral=True)
        
        if bot_id:
            if bot_id not in active_bots:
                await interaction.followup.send("❌ Bot not found!", ephemeral=True)
                return
            bot = active_bots[bot_id]
            cfg = bot.bot_config
            if str(interaction.user.id) != cfg.get("OWNER_ID") and str(interaction.user.id) != BASE_CONFIG.get("OWNER_ID"):
                await interaction.followup.send("❌ You don't own this bot!", ephemeral=True)
                return
            await bot.close()
            del active_bots[bot_id]
            config_manager.delete_config(bot_id)
            await interaction.followup.send(f"✅ Bot `{bot_id}` disconnected!", ephemeral=True)
        else:
            user_bot = None
            for bid, bot in active_bots.items():
                if bot.bot_config.get("OWNER_ID") == str(interaction.user.id):
                    user_bot = (bid, bot)
                    break
            if not user_bot:
                await interaction.followup.send("❌ You have no bots! Use `/unpair <bot_id>`", ephemeral=True)
                return
            bid, bot = user_bot
            await bot.close()
            del active_bots[bid]
            config_manager.delete_config(bid)
            await interaction.followup.send(f"✅ Your bot `{bid}` disconnected!", ephemeral=True)
    
    async def on_ready(self):
        print(f"[MAIN] ✅ Bot logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name="Sub-bots | /pair"))
    
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        print(f"[MAIN] Error: {error}")

# ============================================
# TOKEN VALIDATION & STARTUP
# ============================================
async def check_token_valid(token: str):
    """Check if Discord token is valid before starting bot"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bot {token}"}
        async with session.get("https://discord.com/api/v10/users/@me", headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return True, data.get("username", "Unknown"), data.get("id", "Unknown")
            elif resp.status == 401:
                return False, "INVALID TOKEN (401 Unauthorized)", None
            else:
                return False, f"HTTP Error {resp.status}", None

def run_discord_bot(token: str):
    global main_bot_instance
    
    # Step 1: Validate token via HTTP API
    print("[MAIN] Validating Discord token...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        valid, msg, bot_id = loop.run_until_complete(check_token_valid(token))
    except Exception as e:
        print(f"[MAIN] Token validation failed: {e}")
        return
    
    if not valid:
        print("\n" + "=" * 60)
        print("  ❌ TOKEN ERROR:", msg)
        print("=" * 60)
        print("\n  👉 Go to https://discord.com/developers/applications")
        print("  👉 Your Application → Bot → Reset Token → Copy")
        print("  👉 In Render: Environment → Add MAIN_BOT_TOKEN → Paste")
        print("  👉 Redeploy!")
        print("\n  ⚠️  Make sure you copied the FULL token (no quotes, no spaces)")
        print("=" * 60 + "\n")
        return
    
    print(f"[MAIN] ✅ Token valid! Bot: {msg} (ID: {bot_id})")
    print("[MAIN] Starting bot...")
    
    # Step 2: Start bot
    bot = MainBot()
    main_bot_instance = bot
    
    @bot.command(name="reload")
    @commands.is_owner()
    async def reload(ctx, extension: str):
        try:
            await bot.reload_extension(f"plugin.{extension}")
            await ctx.send(f"✅ Reloaded `{extension}`")
        except Exception as e:
            await ctx.send(f"❌ Error: `{e}`")
    
    @bot.command(name="shutdown")
    @commands.is_owner()
    async def shutdown(ctx):
        await ctx.send("🔴 Shutting down...")
        for bid, sub in list(active_bots.items()):
            try: await sub.close()
            except: pass
        await bot.close()
    
    try:
        bot.run(token)
    except discord.LoginFailure as e:
        print(f"[MAIN] ❌ Login failed: {e}")
    except Exception as e:
        print(f"[MAIN] ❌ Bot error: {e}")

def main():
    token = BASE_CONFIG.get("MAIN_BOT_TOKEN", "").strip()
    
    if not token:
        print("\n" + "=" * 60)
        print("  ❌ MAIN_BOT_TOKEN not set!")
        print("=" * 60)
        print("\n  Set it in Render Environment Variables and redeploy.")
        print("=" * 60 + "\n")
    
    # Start Discord bot in background thread
    print("[MAIN] Starting Discord bot thread...")
    bot_thread = threading.Thread(target=run_discord_bot, args=(token,), daemon=True)
    bot_thread.start()
    
    # Start HTTP server in main thread (keeps Render alive)
    start_http_server()

if __name__ == "__main__":
    main()
