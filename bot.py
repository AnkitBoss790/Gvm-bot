import os
import time
import discord
import platform
import psutil
import aiohttp
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Load .env file
load_dotenv()

DISCORD_TOKEN = ""
CLOUDFLARE_API_TOKEN = "x7FWyMax7iQdDwszVJoZvwGumPhRmjLsk0tXVvWZ"

# Multiple domains and zones support
DOMAINS = "dragoncloud.qzz.io"
ZONES = "0a7737b368f6caf89925a949086d2513"

if len(DOMAINS) != len(ZONES):
    raise ValueError("DOMAINS and ZONES must be in same order and count in .env file!")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Track uptime
start_time = time.time()

def get_uptime():
    sec = int(time.time() - start_time)
    mins, sec = divmod(sec, 60)
    hrs, mins = divmod(mins, 60)
    days, hrs = divmod(hrs, 24)
    return f"{days}d {hrs}h {mins}m {sec}s"


# ----------- Cloudflare Functions -----------

async def create_record(zone_id, name, ip):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}
    json_data = {"type": "A", "name": name, "content": ip, "ttl": 120, "proxied": False}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=json_data) as resp:
            return await resp.json()

async def delete_record(zone_id, record_id):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=headers) as resp:
            return await resp.json()

async def get_record(zone_id, name):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?name={name}"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json()


# ----------- Events -----------

@bot.event
async def on_ready():
    await bot.tree.sync()
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="PowerDev | /help"
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print(f"✅ Logged in as {bot.user}")
    print(f"💻 Loaded {len(bot.tree.get_commands())} slash commands.")


# ----------- Slash Commands -----------

@bot.tree.command(name="subdomain_create", description="Create a new subdomain in Cloudflare DNS")
@app_commands.describe(domain="Select domain", name="Subdomain name", ip="IP address")
async def create(interaction: discord.Interaction, domain: str, name: str, ip: str):
    await interaction.response.defer(thinking=True)

    try:
        zone_index = DOMAINS.index(domain)
        zone_id = ZONES[zone_index]
    except ValueError:
        await interaction.followup.send(f"❌ Domain `{domain}` not found in bot config.")
        return

    data = await create_record(zone_id, f"{name}.{domain}", ip)

    if data.get("success"):
        result = data.get("result", {})
        embed = discord.Embed(
            title="✅ Subdomain Created Successfully!",
            color=discord.Color.green()
        )
        embed.add_field(name="🌐 Name", value=f"`{result['name']}`", inline=False)
        embed.add_field(name="🏠 Domain", value=f"`{domain}`", inline=False)
        embed.add_field(name="💾 IP", value=f"`{result['content']}`", inline=False)
        embed.set_footer(text="Made by PowerDev | Cloudflare DNS Manager")
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"❌ Error: {data.get('errors', 'Unknown error')}")


@bot.tree.command(name="subdomain_delete", description="Delete a subdomain from Cloudflare DNS")
@app_commands.describe(domain="Select domain", name="Subdomain name")
async def delete(interaction: discord.Interaction, domain: str, name: str):
    await interaction.response.defer(thinking=True)

    try:
        zone_index = DOMAINS.index(domain)
        zone_id = ZONES[zone_index]
    except ValueError:
        await interaction.followup.send(f"❌ Domain `{domain}` not found in bot config.")
        return

    full_name = f"{name}.{domain}"
    records = await get_record(zone_id, full_name)

    if records.get("success") and records["result"]:
        record_id = records["result"][0]["id"]
        deleted = await delete_record(zone_id, record_id)

        if deleted.get("success"):
            embed = discord.Embed(
                title="🗑️ Subdomain Deleted",
                color=discord.Color.red()
            )
            embed.add_field(name="🌐 Name", value=f"`{full_name}`", inline=False)
            embed.add_field(name="🏠 Domain", value=f"`{domain}`", inline=False)
            embed.set_footer(text="Made by PowerDev | Cloudflare DNS Manager")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ Failed to delete DNS record.")
    else:
        await interaction.followup.send("⚠️ No record found for that subdomain.")


@bot.tree.command(name="botinfo", description="Show bot information and stats")
async def botinfo(interaction: discord.Interaction):
    uptime = get_uptime()
    ping = round(bot.latency * 1000)
    cpu = psutil.cpu_percent()
    memory = psutil.virtual_memory().percent
    total_guilds = len(bot.guilds)

    embed = discord.Embed(title="🤖 Bot Information", color=discord.Color.blurple())
    embed.add_field(name="🧑‍💻 Developer", value="**PowerDev**", inline=True)
    embed.add_field(name="📡 Ping", value=f"{ping} ms", inline=True)
    embed.add_field(name="🌐 Servers", value=f"{total_guilds}", inline=True)
    embed.add_field(name="⚙️ System", value=platform.system(), inline=True)
    embed.add_field(name="🕒 Uptime", value=uptime, inline=True)
    embed.add_field(name="💽 CPU / RAM", value=f"{cpu}% / {memory}%", inline=True)
    embed.set_footer(text="Made by PowerDev | Cloudflare DNS Manager")

    await interaction.response.send_message(embed=embed)


# ----------- Run Bot -----------

bot.run(DISCORD_TOKEN)
