import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import threading
import aiohttp


async def check_token_valid(token: str):
    """Discord token එක Valid ද කියලා Check කරන Function එක"""
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


def run_sub_bot(token, config, active_bots, bot_id, SubBotClass):
    """Sub Bot එක වෙනම Thread එකක Run කරන Function එක"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        bot = SubBotClass(config)
        active_bots[bot_id] = bot
        bot.run(token)
    except Exception as e:
        print(f"[SUB BOT {bot_id}] Error: {e}")
        if bot_id in active_bots:
            del active_bots[bot_id]


class ConnectBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="pair", description="Connect your own bot token as a sub-bot")
    @app_commands.describe(token="Your Discord bot token")
    async def pair_command(self, interaction: discord.Interaction, token: str):
        await interaction.response.defer(ephemeral=True)
        
        if not token or len(token) < 50:
            await interaction.followup.send("❌ Invalid bot token! Must be 50+ chars.", ephemeral=True)
            return
        
        # Token එක Valid ද කියලා Check කරමු
        valid, msg, bot_user_id = await check_token_valid(token)
        if not valid:
            embed = discord.Embed(
                title="❌ Invalid Token!",
                color=discord.Color.red(),
                description=f"{msg}\n\n👉 [Discord Developer Portal](https://discord.com/developers/applications)\n👉 Your Application → Bot → Reset Token → Copy"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        bot_id = self.bot.config_manager.get_bot_id(token)
        
        if bot_id in self.bot.active_bots:
            await interaction.followup.send(f"⚠️ Bot already connected! (ID: `{bot_id}`)", ephemeral=True)
            return
        
        # Config එක හදමු
        config = self.bot.config_manager.create_config(
            token=token, 
            owner_id=str(interaction.user.id),
            extra={
                "PAIRED_BY": str(interaction.user.id), 
                "PAIRED_BY_NAME": interaction.user.name,
                "GUILD_ID": str(interaction.guild_id) if interaction.guild_id else None,
                "DISCORD_BOT_ID": bot_user_id
            }
        )
        
        # Sub Bot එක වෙනම Thread එකක Start කරමු (Main Bot එක Block වෙන්නැ)
        thread = threading.Thread(
            target=run_sub_bot,
            args=(token, config, self.bot.active_bots, bot_id, self.bot.SubBot),
            daemon=True
        )
        thread.start()
        
        # OAuth2 Invite URL එක Generate කරමු
        invite_url = f"https://discord.com/oauth2/authorize?client_id={bot_user_id}&permissions=8&scope=bot%20applications.commands"
        
        embed = discord.Embed(
            title="✅ Sub-Bot Connected!",
            color=discord.Color.green(),
            description=f"Your bot **{msg}** is now starting up..."
        )
        embed.add_field(name="🆔 Bot ID", value=f"`{bot_id}`", inline=True)
        embed.add_field(name="⌨️ Prefix", value=f"`{config['PREFIX']}`", inline=True)
        embed.add_field(name="🤖 Bot Name", value=f"`{msg}`", inline=True)
        embed.add_field(
            name="➕ Add Bot to Server", 
            value=f"[**Click Here to Add Bot**]({invite_url})", 
            inline=False
        )
        embed.set_footer(text="Use the link above to invite your bot to any server")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # GitHub Backup
        try:
            from github_backup import backup
            backup.save_file(
                f"bot_{bot_id}.json",
                {"status": "connected", "owner": str(interaction.user.id), "bot_id": bot_id, "bot_name": msg},
                f"Bot {bot_id} ({msg}) connected by {interaction.user.name}"
            )
        except Exception as e:
            print(f"[PAIR] Backup error: {e}")
    
    @app_commands.command(name="bots", description="List all connected sub-bots")
    async def bots_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not self.bot.active_bots:
            await interaction.followup.send("📭 No sub-bots connected.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🤖 Connected Sub-Bots", 
            color=discord.Color.blue(),
            description=f"Total: **{len(self.bot.active_bots)}**"
        )
        for bot_id, bot in self.bot.active_bots.items():
            cfg = bot.bot_config
            status = "🟢 Online" if bot.is_ready() else "🟡 Connecting"
            bot_name = bot.user.name if bot.user else "Loading..."
            embed.add_field(
                name=f"Bot `{bot_id}`",
                value=f"Status: {status}\nName: `{bot_name}`\nPrefix: `{cfg.get('PREFIX', '.')}`", 
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="unpair", description="Disconnect your sub-bot")
    @app_commands.describe(bot_id="The bot ID to disconnect (optional - disconnects your bot if not specified)")
    async def unpair_command(self, interaction: discord.Interaction, bot_id: str = None):
        await interaction.response.defer(ephemeral=True)
        
        if bot_id:
            if bot_id not in self.bot.active_bots:
                await interaction.followup.send("❌ Bot not found!", ephemeral=True)
                return
            
            bot = self.bot.active_bots[bot_id]
            cfg = bot.bot_config
            
            # Owner හෝ Main Owner විතරයි Unpair කරන්න පුලුවන්
            if str(interaction.user.id) != cfg.get("OWNER_ID") and str(interaction.user.id) != self.bot.base_config.get("OWNER_ID"):
                await interaction.followup.send("❌ You don't own this bot!", ephemeral=True)
                return
            
            # Sub Bot එකේ Loop එකේ Close කරමු
            try:
                if hasattr(bot, 'loop') and bot.loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
                    future.result(timeout=10)
            except Exception as e:
                print(f"[UNPAIR] Error closing bot: {e}")
            
            if bot_id in self.bot.active_bots:
                del self.bot.active_bots[bot_id]
            self.bot.config_manager.delete_config(bot_id)
            
            await interaction.followup.send(f"✅ Bot `{bot_id}` disconnected!", ephemeral=True)
        
        else:
            # Userගේ Bot එක Automatically හොයාගෙන Unpair කරමු
            user_bot = None
            for bid, bot in self.bot.active_bots.items():
                if bot.bot_config.get("OWNER_ID") == str(interaction.user.id):
                    user_bot = (bid, bot)
                    break
            
            if not user_bot:
                await interaction.followup.send("❌ You have no bots! Use `/bots` to see available bots.", ephemeral=True)
                return
            
            bid, bot = user_bot
            
            try:
                if hasattr(bot, 'loop') and bot.loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
                    future.result(timeout=10)
            except Exception as e:
                print(f"[UNPAIR] Error closing bot: {e}")
            
            if bid in self.bot.active_bots:
                del self.bot.active_bots[bid]
            self.bot.config_manager.delete_config(bid)
            
            await interaction.followup.send(f"✅ Your bot `{bid}` disconnected!", ephemeral=True)


async def setup(bot):
    # Sub Bot වලට මෙ Plugin එක Load නොවෙන විදියට
    if getattr(bot, 'bot_config', {}).get('IS_SUB_BOT', False):
        return
    await bot.add_cog(ConnectBot(bot))
