import os
import sys
import asyncio
import discord
from discord.ext import commands
from pathlib import Path

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
        # Load plugins
        await self.load_plugins()
        
        # Sync slash commands
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
        # Load plugins for main bot too
        plugins_dir = Path(__file__).parent / "plugin"
        if plugins_dir.exists():
            for file in plugins_dir.glob("*.py"):
                if file.name.startswith("_"):
                    continue
                try:
                    await self.load_extension(f"plugin.{file.stem}")
                except Exception as e:
                    print(f"[MAIN] Plugin load error: {e}")
        
        # Add slash commands
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
        """Connect a sub-bot with your token"""
        await interaction.response.defer(ephemeral=True)
        
        # Validate token format
        if not token or len(token) < 50:
            await interaction.followup.send("❌ Invalid bot token! Token must be at least 50 characters.", ephemeral=True)
            return
        
        bot_id = config_manager.get_bot_id(token)
        
        # Check if already connected
        if bot_id in active_bots:
            await interaction.followup.send(
                f"⚠️ This bot is already connected! (ID: `{bot_id}`)",
                ephemeral=True
            )
            return
        
        # Create config
        config = config_manager.create_config(
            token=token,
            owner_id=str(interaction.user.id),
            extra={
                "PAIRED_BY": str(interaction.user.id),
                "PAIRED_BY_NAME": interaction.user.name,
                "GUILD_ID": str(interaction.guild_id) if interaction.guild_id else None
            }
        )
        
        # Start sub-bot
        try:
            bot = SubBot(config)
            await bot.start(token)
            active_bots[bot_id] = bot
            
            await interaction.followup.send(
                f"✅ **Sub-bot connected successfully!**\n\n"
                f"🆔 Bot ID: `{bot_id}`\n"
                f"👤 Owner: <@{interaction.user.id}>\n"
                f"🔧 Prefix: `{config['PREFIX']}`\n"
                f"📁 Config saved & backed up to GitHub\n\n"
                f"Use `{config['PREFIX']}help` to see commands!",
                ephemeral=True
            )
            
            # Backup to GitHub
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
        """List all connected bots"""
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
        """Disconnect a sub-bot"""
        await interaction.response.defer(ephemeral=True)
        
        if bot_id:
            # Disconnect specific bot
            if bot_id not in active_bots:
                await interaction.followup.send("❌ Bot not found!", ephemeral=True)
                return
            
            bot = active_bots[bot_id]
            
            # Check ownership
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
            # Find bot owned by user
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
    """Basic token validation"""
    if not token:
        return False
    # Discord tokens are typically 59+ chars and have 2 dots
    parts = token.split('.')
    if len(parts) != 3:
        return False
    if len(token) < 50:
        return False
    return True

def run_main_bot():
    token = BASE_CONFIG.get("MAIN_BOT_TOKEN", "")
    
    if not token:
        print("=" * 60)
        print("[MAIN] ERROR: MAIN_BOT_TOKEN not set!")
        print("[MAIN] Please set the MAIN_BOT_TOKEN environment variable.")
        print("[MAIN] Get your token from: https://discord.com/developers/applications")
        print("=" * 60)
        sys.exit(1)
    
    if not validate_token(token):
        print("=" * 60)
        print("[MAIN] ERROR: MAIN_BOT_TOKEN format looks invalid!")
        print("[MAIN] Token should be like: Mxxxxxxxxxxxxxxxxxxxxxxxxxx.xxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print("[MAIN] Please check your token.")
        print("=" * 60)
        sys.exit(1)
    
    bot = MainBot()
    
    @bot.command(name="reload")
    @commands.is_owner()
    async def reload(ctx, extension: str):
        """Reload a plugin"""
        try:
            await bot.reload_extension(f"plugin.{extension}")
            await ctx.send(f"✅ Reloaded `{extension}`")
        except Exception as e:
            await ctx.send(f"❌ Error: `{e}`")
    
    @bot.command(name="shutdown")
    @commands.is_owner()
    async def shutdown(ctx):
        """Shutdown all bots"""
        await ctx.send("🔴 Shutting down all bots...")
        
        for bot_id, sub_bot in list(active_bots.items()):
            try:
                await sub_bot.close()
                print(f"[MAIN] Closed sub-bot {bot_id}")
            except:
                pass
        
        await bot.close()
    
    bot.run(token)

if __name__ == "__main__":
    run_main_bot()
