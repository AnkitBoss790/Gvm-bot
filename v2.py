import logging
import re
import requests
from bs4 import BeautifulSoup
import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = 'YOUR_BOT_TOKEN'  # Replace with your Discord bot token
ADMIN_USER_ID = YOUR_ADMIN_USER_ID  # Replace with your Discord user ID (int)
PANEL_URL = 'http://103.174.247.155:3000'
PANEL_USER = 'admin'
PANEL_PASS = 'Ankit790$'

# Global session for HTTP requests
session = requests.Session()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def is_admin(user_id: int) -> bool:
    return str(user_id) == str(ADMIN_USER_ID)

def login_to_panel():
    """Login to GVM Panel and return True if successful."""
    login_url = f'{PANEL_URL}/login'  # Assumed endpoint
    login_data = {'username': PANEL_USER, 'password': PANEL_PASS}
    response = session.post(login_url, data=login_data)
    if response.status_code == 200 and ('dashboard' in response.url.lower() or 'success' in response.text.lower()):
        logger.info("Logged in successfully")
        return True
    logger.error("Login failed")
    return False

def create_vps(name: str, ram: int, cpu: int, disk: int, os: str, user: str, tags: str) -> str:
    """Create a new VPS via form submission with custom specs."""
    if not login_to_panel():
        return "❌ Failed to authenticate with panel."
    
    create_url = f'{PANEL_URL}/create_vps'  # Assumed endpoint
    form_data = {
        'name': name,
        'memory': ram,
        'cpu': cpu,
        'disk': disk,
        'os': os,
        'expiration': 30,  # Default from screenshot
        'bandwidth': 0,    # Default from screenshot
        'additional_ports': '',
        'user': user,
        'tags': tags,
        'custom_docker': ''  # Optional file not supported
    }
    response = session.post(create_url, data=form_data)
    if response.status_code == 200 and 'successfully' in response.text.lower():
        vps_id_match = re.search(r'VPS ID: ([A-Z0-9]+)', response.text)
        host_match = re.search(r'SSH Host: ([\d.]+)', response.text)
        if vps_id_match and host_match:
            vps_id = vps_id_match.group(1)
            host = host_match.group(1)
            ssh_command = f"ssh root@{host} -p 23470"
            return f"✅ VPS '{name}' created!\nID: {vps_id}\nHost: {host}\nSSH: {ssh_command}"
        return "✅ VPS created successfully! Check panel for details."
    return f"❌ Failed to create VPS. Status: {response.status_code}"

def list_vps(own_only: bool = True) -> str:
    """List VPS instances."""
    if not login_to_panel():
        return "❌ Failed to authenticate."
    
    list_url = f'{PANEL_URL}/list_vps'  # Assumed endpoint
    response = session.get(list_url)
    if response.status_code != 200:
        return "❌ Failed to fetch VPS list."
    
    soup = BeautifulSoup(response.text, 'html.parser')
    vps_rows = soup.find_all('tr')  # Assume table rows for VPS
    if not vps_rows:
        return "No VPS found."
    
    message = "📋 VPS List:\n"
    for row in vps_rows[1:]:  # Skip header
        cells = row.find_all('td')
        if len(cells) >= 3:
            vps_id = cells[0].text.strip()
            name = cells[1].text.strip()
            status = cells[2].text.strip()
            message += f"• ID: {vps_id} | Name: {name} | Status: {status}\n"
            if own_only and not is_admin(int(bot.user.id)):  # Pseudo-check
                break
    return message if message != "📋 VPS List:\n" else "No VPS to show."

def delete_vps(vps_id: str) -> str:
    """Delete a VPS."""
    if not login_to_panel():
        return "❌ Failed to authenticate."
    
    delete_url = f'{PANEL_URL}/delete_vps/{vps_id}'  # Assumed endpoint
    response = session.post(delete_url)
    if response.status_code == 200 and 'deleted' in response.text.lower():
        return f"✅ VPS {vps_id} deleted."
    return f"❌ Failed to delete VPS {vps_id}."

def add_user(username: str, password: str) -> str:
    """Add a new user."""
    if not login_to_panel():
        return "❌ Failed to authenticate."
    
    add_url = f'{PANEL_URL}/add_user'
    form_data = {'username': username, 'password': password}
    response = session.post(add_url, data=form_data)
    return "✅ User added." if 'success' in response.text.lower() else "❌ Failed to add user."

def add_admin(username: str) -> str:
    """Promote to admin."""
    if not login_to_panel():
        return "❌ Failed to authenticate."
    
    admin_url = f'{PANEL_URL}/add_admin'
    form_data = {'username': username}
    response = session.post(admin_url, data=form_data)
    return "✅ User promoted to admin." if 'success' in response.text.lower() else "❌ Failed."

def remove_admin(username: str) -> str:
    """Demote admin."""
    if not login_to_panel():
        return "❌ Failed to authenticate."
    
    remove_url = f'{PANEL_URL}/remove_admin'
    form_data = {'username': username}
    response = session.post(remove_url, data=form_data)
    return "✅ Admin removed." if 'success' in response.text.lower() else "❌ Failed."

def manage_vps(vps_id: str) -> str:
    """Get management link."""
    return f"🔧 Manage VPS {vps_id}:\nDashboard: {PANEL_URL}/dashboard/{vps_id}\nUse !deletevps {vps_id} to remove."

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    if not login_to_panel():
        logger.error("Initial login failed. Check credentials.")

@bot.command()
async def ping(ctx):
    """Check bot latency."""
    await ctx.send('🏓 Pong!')

@bot.command()
async def botinfo(ctx):
    """Display bot information."""
    await ctx.send('🤖 GVM VPS Bot\nVersion: 1.0\nMade by PowerDev')

@bot.command()
async def listvps(ctx):
    """List your VPS instances."""
    await ctx.send(list_vps())

@bot.command()
async def listall(ctx):
    """List all VPS instances (admin only)."""
    if is_admin(ctx.author.id):
        await ctx.send(list_vps(own_only=False))
    else:
        await ctx.send("❌ Access denied. Admin only.")

@bot.command()
async def createvps(ctx, name: str, ram: int, cpu: int, disk: int, os: str, user: str, *, tags: str = ""):
    """Create a new VPS (admin only). Usage: !createvps <name> <ram> <cpu> <disk> <os> <user> [tags]"""
    if not is_admin(ctx.author.id):
        await ctx.send("❌ Access denied. Admin only.")
        return
    result = create_vps(name, ram, cpu, disk, os, user, tags)
    await ctx.send("✅ VPS creation initiated. Check your DMs for details!")
    await ctx.author.send(result)

@bot.command()
async def deletevps(ctx, vps_id: str):
    """Delete a VPS (admin only). Usage: !deletevps <vps_id>"""
    if not is_admin(ctx.author.id):
        await ctx.send("❌ Access denied. Admin only.")
        return
    await ctx.send(delete_vps(vps_id))

@bot.command()
async def adduser(ctx, username: str, password: str):
    """Add a new user (admin only). Usage: !adduser <user> <pass>"""
    if not is_admin(ctx.author.id):
        await ctx.send("❌ Access denied. Admin only.")
        return
    await ctx.send(add_user(username, password))

@bot.command()
async def addadmin(ctx, username: str):
    """Promote a user to admin (admin only). Usage: !addadmin <user>"""
    if not is_admin(ctx.author.id):
        await ctx.send("❌ Access denied. Admin only.")
        return
    await ctx.send(add_admin(username))

@bot.command()
async def removeadmin(ctx, username: str):
    """Demote an admin (admin only). Usage: !removeadmin <user>"""
    if not is_admin(ctx.author.id):
        await ctx.send("❌ Access denied. Admin only.")
        return
    await ctx.send(remove_admin(username))

@bot.command()
async def manage(ctx, vps_id: str):
    """Manage a VPS. Usage: !manage <vps_id>"""
    await ctx.send(manage_vps(vps_id))

def main():
    """Start the bot."""
    bot.run(BOT_TOKEN)

if __name__ == '__main__':
    main()
