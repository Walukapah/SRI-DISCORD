import discord
from discord.ext import commands
import platform
import time

class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name="ping", description="Check bot latency")
    async def ping(self, ctx: commands.Context):
        """Check bot response time"""
        start = time.time()
        msg = await ctx.send("🏓 Pinging...")
        end = time.time()
        
        ws_latency = round(self.bot.latency * 1000, 2)
        msg_latency = round((end - start) * 1000, 2)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="WebSocket", value=f"`{ws_latency}ms`", inline=True)
        embed.add_field(name="Message", value=f"`{msg_latency}ms`", inline=True)
        embed.add_field(name="API", value=f"`{round((ws_latency + msg_latency) / 2, 2)}ms`", inline=True)
        
        bot_name = getattr(self.bot, 'bot_config', {}).get('BOT_NAME', 'SRI-BOT')
        embed.set_footer(text=f"{bot_name} | Discord.py v{discord.__version__}")
        
        await msg.edit(content=None, embed=embed)
    
    @commands.hybrid_command(name="botinfo", description="Show bot information")
    async def botinfo(self, ctx: commands.Context):
        """Show bot info"""
        cfg = getattr(self.bot, 'bot_config', {})
        is_sub = cfg.get('IS_SUB_BOT', False)
        
        embed = discord.Embed(
            title=f"🤖 {cfg.get('BOT_NAME', 'SRI-BOT')}",
            color=discord.Color.blue(),
            description="Multi-number Discord Bot System"
        )
        
        embed.add_field(name="Version", value=f"`{cfg.get('VERSION', '1.0.0')}`", inline=True)
        embed.add_field(name="Prefix", value=f"`{cfg.get('PREFIX', '.')}`", inline=True)
        embed.add_field(name="Mode", value=f"`{cfg.get('MODE', 'public')}`", inline=True)
        embed.add_field(name="Type", value="Sub Bot" if is_sub else "Main Bot", inline=True)
        embed.add_field(name="Python", value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="Discord.py", value=f"`{discord.__version__}`", inline=True)
        
        if is_sub:
            embed.add_field(name="Bot ID", value=f"`{cfg.get('BOT_ID', 'N/A')}`", inline=False)
            embed.add_field(name="Connected", value=f"`{cfg.get('CONNECTED_AT', 'N/A')}`", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="help", description="Show help menu")
    async def help_command(self, ctx: commands.Context):
        """Show available commands"""
        prefix = getattr(self.bot, 'bot_config', {}).get('PREFIX', '.')
        
        embed = discord.Embed(
            title="📜 Command List",
            color=discord.Color.gold(),
            description=f"Use `{prefix}command` or `/command`"
        )
        
        commands_list = [
            ("ping", "Check bot latency"),
            ("botinfo", "Show bot information"),
            ("help", "Show this menu"),
        ]
        
        # Add sub-bot specific commands
        cfg = getattr(self.bot, 'bot_config', {})
        if not cfg.get('IS_SUB_BOT'):
            commands_list.extend([
                ("(Slash) /pair <token>", "Connect your own bot"),
                ("(Slash) /bots", "List connected bots"),
                ("(Slash) /unpair [bot_id]", "Disconnect your bot"),
            ])
        
        for name, desc in commands_list:
            embed.add_field(name=f"`{name}`", value=desc, inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Ping(bot))
