import os
import sys
import asyncio
import discord
from discord.ext import commands
from pathlib import Path
import time

from config import config_manager, BASE_CONFIG
from github_backup import backup

# Bot storage
active_bots = {}  # bot_id -> bot instance

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
            
            module_name = f"plugin.{file.stem}"
            try:
                await self.load_extension(module_name)
                print(f"[BOT {self.bot_id}] Loaded plugin: {file.stem}")
            except Exception as e:
                print(f"[BOT {self.bot_id}] Failed to load {file.stem}: {e}")
    
    async def on_ready(self):
        print(f"[BOT {self.bot_id}] Logged in as {self.user} (ID: {self.user.id})")
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
            name="pair",
            description="Connect your own bot token as a sub-bot",
            callback=self.pair_command
        ))
        
        self.tree.add_command(discord.app_commands.Command(
            name="bots",
            description="List all connected sub-bots",
            callback=self.bots_command
        ))
        
        self.tree.add_command(discord.app_commands.Command(
            name="unpair",
            description="Disconnect your sub-bot",
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
            await interaction.followup.send("❌ Invalid bot token! Token must be at least 50 characters.", ephemeral=True)
            return
        
        bot_id = config_manager.get_bot_id(token)
        
        if bot_id in active_bots:
            await interaction.followup.send(
                f"⚠️ This bot is already connected! (ID: `{bot_id}`)",
                ephemeral=True
            )
            return
        
        config = config_manager.create_config(
            token=token,
            owner_id=str(interaction.user.id),
            extra={
                "PAIRED_BY": str(interaction.user.id),
                "PAIRED_BY_NAME": interaction.user.name,
                "GUILD_ID": str(interaction.guild_id) if interaction.guild_id else None
            }
        )
        
        try:
            bot = SubBot(config)
            await bot.start(token)
            active_bots[bot_id] = bot
            
            await interaction.followup.send(
                f"✅ **Sub-bot connected successfully!**\n\n"
                f"🆔 Bot ID: `{bot_id}`\n"
                f"👤 Owner: <@{interaction.user.id}>\n"
                f"🔧 Prefix: `{config['PREFIX']}`\n\n"
                f"Use `{config['PREFIX']}help` to see commands!",
                ephemeral=True
            )
            
            backup.save_file(
                f"bot_{bot_id}.json",
                {"status": "connected", "owner": str(interaction.user.id), "bot_id": bot_id},
                f"Bot {bot_id} connected by {interaction.user.name}"
            )
            
        except discord.LoginFailure:
            config_manager.delete_config(bot_id)
            await interaction.followup.send(
                f"❌ **Invalid bot token!** Please check your token and try again.\n"
                f"Get your token from: https://discord.com/developers/applications",
                ephemeral=True
            )
        except Exception as e:
            print(f"[MAIN] Failed to start sub-bot: {e}")
            config_manager.delete_config(bot_id)
            await interaction.followup.send(
                f"❌ Failed to connect bot: `{str(e)}`",
                ephemeral=True
            )
    
    async def bots_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not active_bots:
            await interaction.followup.send("📭 No sub-bots connected.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🤖 Connected Sub-Bots",
            color=discord.Color.blue(),
            description=f"Total: {len(active_bots)} bot(s)"
        )
        
        for bot_id, bot in active_bots.items():
            cfg = bot.bot_config
            status = "🟢 Online" if bot.is_ready() else "🟡 Connecting"
            embed.add_field(
                name=f"Bot `{bot_id}`",
                value=f"Status: {status}\nName: `{bot.user}`\nPrefix: `{cfg.get('PREFIX', '.')}`",
                inline=False
            )
        
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
            
            await interaction.followup.send(
                f"✅ Bot `{bot_id}` disconnected and config deleted!",
                ephemeral=True
            )
        else:
            user_bot = None
            for bid, bot in active_bots.items():
                if bot.bot_config.get("OWNER_ID") == str(interaction.user.id):
                    user_bot = (bid, bot)
                    break
            
            if not user_bot:
                await interaction.followup.send(
                    "❌ You don't have any connected bots! Use `/unpair <bot_id>` to specify.",
                    ephemeral=True
                )
                return
            
            bid, bot = user_bot
            await bot.close()
            del active_bots[bid]
            config_manager.delete_config(bid)
            
            await interaction.followup.send(
                f"✅ Your bot `{bid}` has been disconnected!",
                ephemeral=True
            )
    
    async def on_ready(self):
        print(f"[MAIN] Bot logged in as {self.user} (ID: {self.user.id})")
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="Sub-bots | /pair"
        )
        await self.change_presence(activity=activity)
    
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        print(f"[MAIN] Error: {error}")

def validate_token(token: str) -> bool:
    if not token:
        return False
    parts = token.split('.')
    if len(parts) != 3:
        return False
    if len(token) < 50:
        return False
    return True

def print_token_help():
    print("\n" + "=" * 70)
    print("  ❌  MAIN_BOT_TOKEN IS MISSING OR INVALID!")
    print("=" * 70)
    print("\n  👉 Step 1: Go to https://discord.com/developers/applications")
    print("  👉 Step 2: Create New Application → Bot tab → Add Bot")
    print("  👉 Step 3: Click 'Reset Token' → Copy the token")
    print("  👉 Step 4: In Render Dashboard, go to Environment Variables")
    print("  👉 Step 5: Add: MAIN_BOT_TOKEN = your_copied_token_here")
    print("  👉 Step 6: Redeploy the service")
    print("\n  ⚠️  DO NOT put the token directly in config.py!")
    print("  ⚠️  The token MUST be set as an environment variable!")
    print("=" * 70 + "\n")

def keep_alive():
    """Keep process alive so Render doesn't restart endlessly"""
    print("[MAIN] Keeping process alive for debugging...")
    while True:
        time.sleep(60)

def run_main_bot():
    token = BASE_CONFIG.get("MAIN_BOT_TOKEN", "")
    
    # Check if token exists
    if not token:
        print_token_help()
        print("[MAIN] ERROR: MAIN_BOT_TOKEN environment variable is empty!")
        keep_alive()
        return
    
    # Check token format
    if not validate_token(token):
        print_token_help()
        print(f"[MAIN] ERROR: Token format is invalid! (Length: {len(token)})")
        print(f"[MAIN] Token looks like: {token[:10]}... (should have 3 parts separated by dots)")
        keep_alive()
        return
    
    bot = MainBot()
    
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
        await ctx.send("🔴 Shutting down all bots...")
        for bot_id, sub_bot in list(active_bots.items()):
            try:
                await sub_bot.close()
                print(f"[MAIN] Closed sub-bot {bot_id}")
            except:
                pass
        await bot.close()
    
    # Try to start bot with proper error handling
    try:
        bot.run(token)
    except discord.LoginFailure as e:
        print("\n" + "=" * 70)
        print("  ❌  DISCORD LOGIN FAILED - TOKEN IS INVALID!")
        print("=" * 70)
        print(f"\n  Error: {e}")
        print(f"\n  Your token: {token[:15]}...{token[-5:]}")
        print("\n  Possible reasons:")
        print("  • Token was reset in Discord Developer Portal")
        print("  • Token was copied incorrectly (missing characters)")
        print("  • Bot was deleted from Developer Portal")
        print("\n  Fix: Get a NEW token from https://discord.com/developers/applications")
        print("       and update the MAIN_BOT_TOKEN environment variable.")
        print("=" * 70 + "\n")
        keep_alive()
    except Exception as e:
        print(f"[MAIN] Unexpected error: {e}")
        keep_alive()

if __name__ == "__main__":
    run_main_bot()
