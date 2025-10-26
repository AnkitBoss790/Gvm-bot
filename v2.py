import logging
import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import discord
from discord.ext import commands
from discord import ui
from discord.ui import View, Button

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = 'YOUR_BOT_TOKEN'  # Replace with your Discord bot token
ADMIN_USER_ID = '1405866008127864852'  # Your admin ID
PANEL_URL = 'http://103.174.247.155:3000'
PANEL_USER = 'admin'
PANEL_PASS = ''

# Global session for HTTP requests
session = None

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def is_admin(user_id: str) -> bool:
    return user_id == ADMIN_USER_ID

async def login_to_panel():
    """Async login to GVM Panel."""
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    login_url = f'{PANEL_URL}/login'
    data = {'username': PANEL_USER, 'password': PANEL_PASS}
    async with session.post(login_url, data=data) as resp:
        text = await resp.text()
        logger.info(f"Login response: {resp.status} - {text[:500]}...")
        return resp.status == 200 and ('dashboard' in str(resp.url).lower() or 'success' in text.lower())

async def create_vps(name: str, ram: int, cpu: int, disk: int, os: str, user: str, tags: str) -> dict:
    """Create VPS and return dict of details."""
    if not await login_to_panel():
        return {"error": "❌ Failed to authenticate with panel. Please check credentials."}

    create_url = f'{PANEL_URL}/create_vps'
    form_data = {
        'name': name,
        'memory': str(ram),
        'cpu': str(cpu),
        'disk': str(disk),
        'os': os,
        'expiration': '30',
        'bandwidth': '0',
        'additional_ports': '',
        'user': user,
        'tags': tags,
        'custom_docker': ''
    }
    logger.info(f"Sending create request with data: {form_data}")
    async with session.post(create_url, data=form_data) as resp:
        text = await resp.text()
        logger.info(f"Create response: {resp.status} - {text[:500]}...")

        if resp.status == 200:
            if any(keyword in text.lower() for keyword in ['successfully', 'created', 'success']):
                # Extract details with precise regex based on panel format
                details = {
                    'vps_id': re.search(r'VPS ID:\s*([A-Z0-9]+)', text).group(1),
                    'username': re.search(r'Username:\s*(\w+)', text).group(1),
                    'password': re.search(r'Password:\s*([^\s<]+)', text).group(1),
                    'ssh_host': re.search(r'SSH Host:\s*([\d.]+)', text).group(1),
                    'ssh_port': re.search(r'SSH Port:\s*(\d+)', text).group(1),
                    'status': re.search(r'Status:\s*(\w+)', text).group(1),
                    'memory': f"{ram} GB",
                    'cpu': f"{cpu} Cores",
                    'disk': f"{disk} GB",
                    'os': os
                }
                ssh_command = f"ssh {details['username']}@{details['ssh_host']} -p {details['ssh_port']}"
                details['ssh_command'] = ssh_command
                return details
            return {"error": "❌ Failed to create VPS. Response indicates success but no 'successfully', 'created', or 'success' found. Check logs."}
        return {"error": f"❌ Failed to create VPS. Status: {resp.status}"}

async def list_vps(own_only: bool = True) -> str:
    """List VPS with full details."""
    if not await login_to_panel():
        return "❌ Failed to authenticate."
    
    list_url = f'{PANEL_URL}/list_vps'
    async with session.get(list_url) as resp:
        if resp.status != 200:
            return "❌ Failed to fetch VPS list."
        text = await resp.text()
        soup = BeautifulSoup(text, 'html.parser')
        vps_rows = soup.find_all('tr')
        if not vps_rows:
            return "No VPS found."
        
        message = "📋 VPS List:\n"
        for row in vps_rows[1:]:
            cells = row.find_all('td')
            if len(cells) >= 6:
                vps_id = cells[0].text.strip()
                name = cells[1].text.strip()
                status = cells[2].text.strip()
                memory = cells[3].text.strip()
                cpu = cells[4].text.strip()
                disk = cells[5].text.strip()
                message += f"• **ID:** {vps_id} | **Name:** {name} | **Status:** {status} | **RAM:** {memory} | **CPU:** {cpu} | **Disk:** {disk}\n"
                if own_only:
                    break
        return message if message != "📋 VPS List:\n" else "No VPS to show."

async def manage_action(vps_id: str, action: str) -> str:
    """Perform action on VPS (start, stop, etc.)."""
    if not await login_to_panel():
        return "❌ Failed to authenticate."
    
    action_url = f'{PANEL_URL}/vps/{vps_id}/{action}'
    async with session.post(action_url) as resp:
        text = await resp.text()
        if resp.status == 200 and 'success' in text.lower():
            return f"✅ VPS {vps_id} {action}ed successfully."
        return f"❌ Failed to {action} VPS {vps_id}."

async def get_ssh_info(vps_id: str) -> str:
    """Get SSH details for VPS."""
    if not await login_to_panel():
        return "❌ Failed to authenticate."
    
    info_url = f'{PANEL_URL}/vps/{vps_id}/ssh'
    async with session.get(info_url) as resp:
        text = await resp.text()
        host = re.search(r'SSH Host:\s*([\d.]+)', text).group(1)
        port = re.search(r'SSH Port:\s*(\d+)', text).group(1)
        return f"🔑 SSH for {vps_id}:\nHost: {host}\nPort: {port}\nCommand: ssh root@{host} -p {port}"

class ManageView(View):
    """Interactive buttons for manage command."""
    def __init__(self, vps_id: str):
        super().__init__(timeout=300)
        self.vps_id = vps_id

    @ui.button(label='Start', style=discord.ButtonStyle.green)
    async def start_button(self, interaction: discord.Interaction, button: Button):
        result = await manage_action(self.vps_id, 'start')
        await interaction.response.send_message(result, ephemeral=True)

    @ui.button(label='Stop', style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: Button):
        result = await manage_action(self.vps_id, 'stop')
        await interaction.response.send_message(result, ephemeral=True)

    @ui.button(label='Restart', style=discord.ButtonStyle.blurple)
    async def restart_button(self, interaction: discord.Interaction, button: Button):
        result = await manage_action(self.vps_id, 'restart')
        await interaction.response.send_message(result, ephemeral=True)

    @ui.button(label='Reinstall', style=discord.ButtonStyle.grey)
    async def reinstall_button(self, interaction: discord.Interaction, button: Button):
        result = await manage_action(self.vps_id, 'reinstall')
        await interaction.response.send_message(result, ephemeral=True)

    @ui.button(label='SSH Info', style=discord.ButtonStyle.primary)
    async def ssh_button(self, interaction: discord.Interaction, button: Button):
        result = await get_ssh_info(self.vps_id)
        await interaction.response.send_message(result, ephemeral=True)

@bot.event
async def on_ready():
    global session
    session = aiohttp.ClientSession()
    logger.info(f'{bot.user} has connected to Discord!')
    if not await login_to_panel():
        logger.error("Initial login failed. Check credentials.")
    else:
        logger.info("🖥️ GVM Panel CMD Running - Bot online!")

@bot.command()
async def ping(ctx):
    await ctx.send('🏓 Pong!')

@bot.command()
async def botinfo(ctx):
    await ctx.send('🤖 GVM VPS Bot\nVersion: 1.0')

@bot.command()
async def listvps(ctx):
    await ctx.send(await list_vps())

@bot.command()
async def listall(ctx):
    if is_admin(str(ctx.author.id)):
        await ctx.send(await list_vps(own_only=False))
    else:
        await ctx.send("❌ Access denied. Admin only.")

@bot.command()
async def createvps(ctx, name: str, ram: int, cpu: int, disk: int, os: str, user: str, *, tags: str = ""):
    if not is_admin(str(ctx.author.id)):
        await ctx.send("❌ Access denied. Admin only.")
        return
    
    msg = await ctx.send("🔄 Creating VPS... (Processing)")
    await asyncio.sleep(10)
    
    details = await create_vps(name, ram, cpu, disk, os, user, tags)
    if "error" in details:
        await msg.edit(content=details["error"])
        return
    
    success_msg = f"✅ VPS '{name}' Created Successfully!\nRAM: {details['memory']} | CPU: {details['cpu']} | Disk: {details['disk']} | OS: {details['os']}"
    await msg.edit(content=success_msg)
    
    dm_embed = discord.Embed(title=f"🔒 VPS Details for {name}", color=0x00ff00)
    dm_embed.add_field(name="VPS ID", value=details['vps_id'], inline=True)
    dm_embed.add_field(name="Username", value=details['username'], inline=True)
    dm_embed.add_field(name="Password", value=details['password'], inline=True)
    dm_embed.add_field(name="SSH Host", value=details['ssh_host'], inline=True)
    dm_embed.add_field(name="SSH Port", value=details['ssh_port'], inline=True)
    dm_embed.add_field(name="Status", value=details['status'], inline=True)
    dm_embed.add_field(name="SSH Command", value=details['ssh_command'], inline=False)
    await ctx.author.send(embed=dm_embed)

@bot.command()
async def deletevps(ctx, vps_id: str):
    if not is_admin(str(ctx.author.id)):
        await ctx.send("❌ Access denied. Admin only.")
        return
    result = await manage_action(vps_id, 'delete')
    await ctx.send(result)

@bot.command()
async def adduser(ctx, username: str, password: str):
    if not is_admin(str(ctx.author.id)):
        await ctx.send("❌ Access denied. Admin only.")
        return
    await ctx.send("✅ User added.")  # Placeholder

@bot.command()
async def addadmin(ctx, username: str):
    if not is_admin(str(ctx.author.id)):
        await ctx.send("❌ Access denied. Admin only.")
        return
    await ctx.send("✅ User promoted to admin.")

@bot.command()
async def removeadmin(ctx, username: str):
    if not is_admin(str(ctx.author.id)):
        await ctx.send("❌ Access denied. Admin only.")
        return
    await ctx.send("✅ Admin removed.")

@bot.command()
async def manage(ctx, vps_id: str):
    view = ManageView(vps_id)
    embed = discord.Embed(title=f"🔧 Manage VPS {vps_id}", description="Click a button below:", color=0x0099ff)
    await ctx.send(embed=embed, view=view)

async def close_session():
    if session and not session.closed:
        await session.close()

@bot.event
async def on_close():
    await close_session()

def main():
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
    finally:
        asyncio.run(close_session())

if __name__ == '__main__':
    main()
