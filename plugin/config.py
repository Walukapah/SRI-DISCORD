import discord
from discord.ext import commands
from discord import app_commands, ui
import aiohttp
from config import config_manager


# ============================================================
# MODALS - Text Input Dialogs
# ============================================================

class NameModal(ui.Modal, title="🏷️ Change Bot Name"):
    name_input = ui.TextInput(
        label="New Bot Name",
        placeholder="Enter new name...",
        max_length=32,
        required=True
    )
    
    def __init__(self, bot, current_name):
        super().__init__()
        self.bot = bot
        self.name_input.default = current_name
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.bot.user.edit(username=self.name_input.value)
            self.bot.bot_config['BOT_NAME'] = self.name_input.value
            config_manager.update_config(
                self.bot.bot_config['BOT_ID'], 
                {'BOT_NAME': self.name_input.value}
            )
            await interaction.response.send_message(
                f"✅ Bot name changed to **{self.name_input.value}**", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed: `{e}`", 
                ephemeral=True
            )


class AvatarModal(ui.Modal, title="🖼️ Change Bot Avatar"):
    url_input = ui.TextInput(
        label="Image URL",
        placeholder="https://i.imgur.com/example.png",
        max_length=500,
        required=True
    )
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    async def on_submit(self, interaction: discord.Interaction):
        url = self.url_input.value
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await interaction.response.send_message(
                            "❌ Failed to download image.", 
                            ephemeral=True
                        )
                        return
                    data = await resp.read()
                    if len(data) > 8 * 1024 * 1024:
                        await interaction.response.send_message(
                            "❌ Image too large! Max: 8MB", 
                            ephemeral=True
                        )
                        return
                    await self.bot.user.edit(avatar=data)
                    await interaction.response.send_message(
                        "✅ Bot avatar updated!", 
                        ephemeral=True
                    )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: `{e}`", 
                ephemeral=True
            )


class DescriptionModal(ui.Modal, title="📝 Change Bot Description"):
    desc_input = ui.TextInput(
        label="Bot Description (About Me)",
        placeholder="Enter description...",
        style=discord.TextStyle.paragraph,
        max_length=400,
        required=True
    )
    
    def __init__(self, bot, current):
        super().__init__()
        self.bot = bot
        self.desc_input.default = current or ""
    
    async def on_submit(self, interaction: discord.Interaction):
        desc = self.desc_input.value
        try:
            token = self.bot.bot_config.get('TOKEN')
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bot {token}",
                    "Content-Type": "application/json"
                }
                async with session.patch(
                    "https://discord.com/api/v10/applications/@me",
                    headers=headers,
                    json={"description": desc}
                ) as resp:
                    if resp.status == 200:
                        self.bot.bot_config['DESCRIPTION'] = desc
                        config_manager.update_config(
                            self.bot.bot_config['BOT_ID'],
                            {'DESCRIPTION': desc}
                        )
                        await interaction.response.send_message(
                            "✅ Bot description updated!", 
                            ephemeral=True
                        )
                    else:
                        text = await resp.text()
                        await interaction.response.send_message(
                            f"❌ API Error {resp.status}", 
                            ephemeral=True
                        )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: `{e}`", 
                ephemeral=True
            )


class PrefixModal(ui.Modal, title="⌨️ Change Prefix"):
    prefix_input = ui.TextInput(
        label="New Prefix",
        placeholder=".",
        max_length=5,
        required=True
    )
    
    def __init__(self, bot, current):
        super().__init__()
        self.bot = bot
        self.prefix_input.default = current or "."
    
    async def on_submit(self, interaction: discord.Interaction):
        prefix = self.prefix_input.value
        self.bot.bot_config['PREFIX'] = prefix
        config_manager.update_config(
            self.bot.bot_config['BOT_ID'],
            {'PREFIX': prefix}
        )
        self.bot.command_prefix = prefix
        await interaction.response.send_message(
            f"✅ Prefix changed to `{prefix}`", 
            ephemeral=True
        )


class ModeModal(ui.Modal, title="🌐 Change Mode"):
    mode_input = ui.TextInput(
        label="Mode (public / private / admin)",
        placeholder="public",
        max_length=10,
        required=True
    )
    
    def __init__(self, bot, current):
        super().__init__()
        self.bot = bot
        self.mode_input.default = current or "public"
    
    async def on_submit(self, interaction: discord.Interaction):
        mode = self.mode_input.value.lower()
        if mode not in ('public', 'private', 'admin'):
            await interaction.response.send_message(
                "❌ Mode must be: public, private, or admin", 
                ephemeral=True
            )
            return
        self.bot.bot_config['MODE'] = mode
        config_manager.update_config(
            self.bot.bot_config['BOT_ID'],
            {'MODE': mode}
        )
        await interaction.response.send_message(
            f"✅ Mode changed to `{mode}`", 
            ephemeral=True
        )


# ============================================================
# EMBED HELPERS
# ============================================================

def get_main_embed(bot):
    cfg = bot.bot_config
    disabled = cfg.get('DISABLED_COMMANDS', [])
    total = len([c for c in bot.commands if not c.hidden])
    
    embed = discord.Embed(
        title="🛠️ Bot Configuration",
        description="Select a category below to configure your sub-bot.",
        color=discord.Color.blurple()
    )
    embed.add_field(name="🏷️ Name", value=f"`{bot.user.name}`", inline=True)
    embed.add_field(name="⌨️ Prefix", value=f"`{cfg.get('PREFIX', '.')}`", inline=True)
    embed.add_field(name="🌐 Mode", value=f"`{cfg.get('MODE', 'public')}`", inline=True)
    embed.add_field(
        name="📝 Commands", 
        value=f"`{total - len(disabled)}` enabled / `{len(disabled)}` disabled", 
        inline=True
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=f"Bot ID: {cfg.get('BOT_ID', 'N/A')}")
    return embed


def get_profile_embed(bot):
    cfg = bot.bot_config
    embed = discord.Embed(title="🖼️ Bot Profile", color=discord.Color.blue())
    embed.add_field(name="Current Name", value=f"`{bot.user.name}`", inline=False)
    embed.add_field(
        name="Current Avatar", 
        value=f"[Click to View]({bot.user.display_avatar.url})", 
        inline=False
    )
    embed.add_field(
        name="Description", 
        value=f"```{cfg.get('DESCRIPTION', 'Not set')}```", 
        inline=False
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    return embed


def get_general_embed(bot):
    cfg = bot.bot_config
    embed = discord.Embed(title="⚙️ General Settings", color=discord.Color.green())
    embed.add_field(name="Prefix", value=f"`{cfg.get('PREFIX', '.')}`", inline=True)
    embed.add_field(name="Mode", value=f"`{cfg.get('MODE', 'public')}`", inline=True)
    embed.add_field(
        name="Auto Status", 
        value=f"`{cfg.get('AUTO_STATUS', 'true')}`", 
        inline=True
    )
    return embed


def get_commands_embed(bot):
    cfg = bot.bot_config
    disabled = cfg.get('DISABLED_COMMANDS', [])
    
    embed = discord.Embed(
        title="📝 Command Toggles",
        description="Click a command button to enable/disable it.\n✅ = Enabled | ❌ = Disabled",
        color=discord.Color.gold()
    )
    
    cmds = [c for c in bot.commands if not c.hidden and c.name != 'config']
    for cmd in cmds[:20]:
        status = "❌ Disabled" if cmd.name in disabled else "✅ Enabled"
        embed.add_field(name=f"`{cmd.name}`", value=status, inline=True)
    
    if not cmds:
        embed.description = "No toggleable commands found."
    
    return embed


# ============================================================
# VIEWS
# ============================================================

class ProfileView(ui.View):
    def __init__(self, bot, owner_id):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
    
    async def interaction_check(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("❌ You don't own this bot!", ephemeral=True)
            return False
        return True
    
    @ui.button(label="Change Name", style=discord.ButtonStyle.primary, emoji="🏷️")
    async def change_name(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(NameModal(self.bot, self.bot.user.name))
    
    @ui.button(label="Change Avatar", style=discord.ButtonStyle.primary, emoji="🖼️")
    async def change_avatar(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AvatarModal(self.bot))
    
    @ui.button(label="Change Description", style=discord.ButtonStyle.primary, emoji="📝")
    async def change_desc(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(DescriptionModal(self.bot, self.bot.bot_config.get('DESCRIPTION', '')))
    
    @ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
    async def go_back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(embed=get_main_embed(self.bot), view=MainView(self.bot, self.owner_id))


class GeneralView(ui.View):
    def __init__(self, bot, owner_id):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
    
    async def interaction_check(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("❌ You don't own this bot!", ephemeral=True)
            return False
        return True
    
    @ui.button(label="Change Prefix", style=discord.ButtonStyle.primary, emoji="⌨️")
    async def change_prefix(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(PrefixModal(self.bot, self.bot.bot_config.get('PREFIX', '.')))
    
    @ui.button(label="Change Mode", style=discord.ButtonStyle.primary, emoji="🌐")
    async def change_mode(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ModeModal(self.bot, self.bot.bot_config.get('MODE', 'public')))
    
    @ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
    async def go_back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(embed=get_main_embed(self.bot), view=MainView(self.bot, self.owner_id))


class CommandsView(ui.View):
    def __init__(self, bot, owner_id, page=0):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.page = page
        self._add_cmd_buttons()
    
    def _add_cmd_buttons(self):
        cfg = self.bot.bot_config
        disabled = cfg.get('DISABLED_COMMANDS', [])
        cmds = [c for c in self.bot.commands if not c.hidden and c.name != 'config']
        
        # Pagination: 20 commands per page (4 rows x 5)
        per_page = 20
        start = self.page * per_page
        end = start + per_page
        page_cmds = cmds[start:end]
        
        for cmd in page_cmds:
            is_disabled = cmd.name in disabled
            btn = ui.Button(
                label=cmd.name,
                emoji="❌" if is_disabled else "✅",
                style=discord.ButtonStyle.danger if is_disabled else discord.ButtonStyle.success,
                row=None
            )
            btn.callback = self._make_toggle_callback(cmd.name)
            self.add_item(btn)
        
        # Pagination controls
        if len(cmds) > per_page:
            if self.page > 0:
                prev_btn = ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=4)
                prev_btn.callback = self._prev_page
                self.add_item(prev_btn)
            
            if end < len(cmds):
                next_btn = ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, row=4)
                next_btn.callback = self._next_page
                self.add_item(next_btn)
        
        back_btn = ui.Button(label="⬅️ Back", style=discord.ButtonStyle.secondary, row=4)
        back_btn.callback = self._go_back
        self.add_item(back_btn)
    
    def _make_toggle_callback(self, cmd_name):
        async def callback(interaction: discord.Interaction):
            cfg = self.bot.bot_config
            disabled = set(cfg.get('DISABLED_COMMANDS', []))
            
            if cmd_name in disabled:
                disabled.discard(cmd_name)
                msg = f"✅ Command `{cmd_name}` is now **ENABLED**"
            else:
                disabled.add(cmd_name)
                msg = f"❌ Command `{cmd_name}` is now **DISABLED**"
            
            cfg['DISABLED_COMMANDS'] = list(disabled)
            config_manager.update_config(cfg['BOT_ID'], {'DISABLED_COMMANDS': list(disabled)})
            
            await interaction.response.edit_message(
                embed=get_commands_embed(self.bot), 
                view=CommandsView(self.bot, self.owner_id, self.page)
            )
            await interaction.followup.send(msg, ephemeral=True)
        return callback
    
    async def _prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        await interaction.response.edit_message(
            embed=get_commands_embed(self.bot), 
            view=CommandsView(self.bot, self.owner_id, self.page)
        )
    
    async def _next_page(self, interaction: discord.Interaction):
        self.page += 1
        await interaction.response.edit_message(
            embed=get_commands_embed(self.bot), 
            view=CommandsView(self.bot, self.owner_id, self.page)
        )
    
    async def _go_back(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=get_main_embed(self.bot), 
            view=MainView(self.bot, self.owner_id)
        )
    
    async def interaction_check(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("❌ You don't own this bot!", ephemeral=True)
            return False
        return True


class MainView(ui.View):
    def __init__(self, bot, owner_id):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
    
    async def interaction_check(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("❌ You don't own this bot!", ephemeral=True)
            return False
        return True
    
    @ui.select(
        placeholder="Select a category...",
        options=[
            discord.SelectOption(label="Bot Profile", value="profile", emoji="🖼️", description="Name, Avatar, Description"),
            discord.SelectOption(label="General Settings", value="general", emoji="⚙️", description="Prefix, Mode, Auto Status"),
            discord.SelectOption(label="Command Toggles", value="commands", emoji="📝", description="Enable/Disable commands"),
        ]
    )
    async def category_select(self, interaction: discord.Interaction, select: ui.Select):
        value = select.values[0]
        if value == "profile":
            await interaction.response.edit_message(embed=get_profile_embed(self.bot), view=ProfileView(self.bot, self.owner_id))
        elif value == "general":
            await interaction.response.edit_message(embed=get_general_embed(self.bot), view=GeneralView(self.bot, self.owner_id))
        elif value == "commands":
            await interaction.response.edit_message(embed=get_commands_embed(self.bot), view=CommandsView(self.bot, self.owner_id))


# ============================================================
# COG
# ============================================================

class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_load(self):
        # Global check to respect disabled commands
        self.bot.add_check(self._global_check)
    
    async def cog_unload(self):
        self.bot.remove_check(self._global_check)
    
    async def _global_check(self, ctx):
        # Skip if not a sub-bot
        if not getattr(ctx.bot, 'bot_config', {}).get('IS_SUB_BOT', False):
            return True
        
        cfg = ctx.bot.bot_config
        disabled = cfg.get('DISABLED_COMMANDS', [])
        
        # Always allow config command
        if ctx.command and ctx.command.name == 'config':
            return True
        
        if ctx.command and ctx.command.name in disabled:
            return False
        return True
    
    @app_commands.command(name="config", description="Configure your sub-bot settings")
    async def config_cmd(self, interaction: discord.Interaction):
        # Owner check
        cfg = getattr(self.bot, 'bot_config', {})
        owner_id = cfg.get('OWNER_ID', '')
        is_sub = cfg.get('IS_SUB_BOT', False)
        
        # Main bot owner can use too, but this is mainly for sub bots
        if not is_sub:
            await interaction.response.send_message(
                "❌ This command is for sub-bots only!", 
                ephemeral=True
            )
            return
        
        if str(interaction.user.id) != owner_id:
            await interaction.response.send_message(
                "❌ You don't own this bot!", 
                ephemeral=True
            )
            return
        
        embed = get_main_embed(self.bot)
        view = MainView(self.bot, owner_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    # Only load for sub-bots
    if not getattr(bot, 'bot_config', {}).get('IS_SUB_BOT', False):
        return
    await bot.add_cog(ConfigCog(bot))
