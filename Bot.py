import discord
from discord.ext import commands
import requests
import json
from datetime import datetime, timedelta
import asyncio
import re
import io
import time
from typing import Optional, Dict, Any
from datetime import timezone

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

AUTHGUARD_API_URL = "https://api.authguard.org"
API_TOKEN = "YOUR_API_TOKEN" # Found in Settings/API Token
SERVICE_ID = YOUR_SERVICE_ID # Found in the URL of ur Service | exemple : 123
CRAVEX_PROMO_LINK = "Developed by Cravex Team: https://discord.gg/NPzzhqTMvq"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S UTC"

def get_auth_headers():
    return {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://authguard.org",
        "Referer": "https://authguard.org/"
    }

def parse_duration(duration_str):
    match = re.match(r'^(\d+)([dhm])$', duration_str.lower().strip())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    if value <= 0:
        return None
    if unit == 'd':
        return value * 86400
    elif unit == 'h':
        return value * 3600
    elif unit == 'm':
        return value * 60
    return None

def get_key_details(key_id):
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/service/{SERVICE_ID}/key/{key_id}"
        response = requests.get(url, headers=get_auth_headers())
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("data", {})
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key/{key_id}"
        response = requests.get(url, headers=get_auth_headers())
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("data", {})
        return None
    except Exception:
        return None

def get_key_data_by_name(key_name):
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key"
        response = requests.get(url, headers=get_auth_headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            default_keys_list = data.get("data", {}).get("defaultKeys")
            if not isinstance(default_keys_list, list):
                return None
            for key_data in default_keys_list:
                if key_data.get("key") == key_name:
                    return key_data
            return None
        return None
    except Exception:
        return None

def create_24h_key():
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key"
        payload = {
            "expiredAt": int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        }
        response = requests.post(url, headers=get_auth_headers(), json=payload)
        if response.status_code == 201:
            return response.json()
        return None
    except Exception:
        return None

def create_premium_key(duration_seconds):
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/premium-key"
        expired_at = int((datetime.utcnow() + timedelta(seconds=duration_seconds)).timestamp())
        payload = {"expiredAt": expired_at}
        response = requests.post(url, headers=get_auth_headers(), json=payload)
        if response.status_code == 201:
            return response.json()
        return None
    except Exception:
        return None

def change_key_hwid(key_id):
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key/{key_id}"
        payload = {"hwid": ""}
        response = requests.patch(url, headers=get_auth_headers(), json=payload)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("success"):
                return True
            return False
        return False
    except Exception:
        return False

def blacklist_key(key_id, duration_seconds=604800, reason="No reason provided"):
    key_data = get_key_details(key_id)
    if not key_data:
        return False
    hwid = key_data.get("hwid")
    if not hwid:
        return disable_key(key_id, duration_seconds, reason)
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/blacklist"
        expired_at = int((datetime.utcnow() + timedelta(seconds=duration_seconds)).timestamp())
        payload = {"hwid": hwid, "ip": None, "reason": reason, "expiredAt": expired_at}
        response = requests.post(url, headers=get_auth_headers(), json=payload)
        if response.status_code == 201:
            response_data = response.json()
            if response_data.get("success"):
                return True
            return False
        return False
    except Exception:
        return False

def disable_key(key_id, duration_seconds, reason):
    try:
        expired_at = int((datetime.utcnow() + timedelta(seconds=duration_seconds)).timestamp())
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key/{key_id}"
        payload = {"expiredAt": expired_at}
        response = requests.patch(url, headers=get_auth_headers(), json=payload)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("success"):
                return True
            return False
        return False
    except Exception:
        return False

def get_blacklist_entry(hwid):
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/blacklist"
        params = {"hwid": hwid, "serviceId": SERVICE_ID}
        response = requests.get(url, headers=get_auth_headers(), params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data", {}).get("blacklist"):
                for entry in data["data"]["blacklist"]:
                    if entry.get("hwid") == hwid:
                        return entry.get("id")
            return None
        return None
    except Exception:
        return None

def whitelist_key(key_id, reason="No reason provided"):
    try:
        key_data = get_key_details(key_id)
        if not key_data:
            return False
        hwid = key_data.get("hwid")
        if not hwid:
            return restore_key_expiration(key_id, reason)
        blacklist_id = get_blacklist_entry(hwid)
        if not blacklist_id:
            return restore_key_expiration(key_id, reason)
        url = f"{AUTHGUARD_API_URL}/key-manager/blacklist/{blacklist_id}"
        response = requests.delete(url, headers=get_auth_headers())
        if response.status_code in (200, 204):
            return True
        return False
    except Exception:
        return False

def restore_key_expiration(key_id, reason):
    try:
        expired_at = int((datetime.utcnow() + timedelta(days=365)).timestamp())
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key/{key_id}"
        payload = {"expiredAt": expired_at}
        response = requests.patch(url, headers=get_auth_headers(), json=payload)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("success"):
                return True
            return False
        return False
    except Exception:
        return False

def format_timestamp(timestamp_s):
    if timestamp_s is None or timestamp_s == 0:
        return "N/A (Never Expires)"
    try:
        dt_object = datetime.fromtimestamp(timestamp_s, tz=timezone.utc)
        return dt_object.strftime(DATE_FORMAT)
    except Exception:
        return f"Invalid Timestamp ({timestamp_s})"

def check_key_expiration(key_info):
    expired_at_ts = key_info.get('expiredAt')
    current_ts = int(time.time())
    if expired_at_ts is None or expired_at_ts == 0:
        return "Permanent ✅"
    elif expired_at_ts <= current_ts:
        return "Expired 🔴"
    else:
        return "Valid 🟢"

@bot.tree.command(name="help", description="Shows information about available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 AuthGuard Bot Commands",
        description="Below is a list of all available commands for managing AuthGuard keys. These commands are restricted to server administrators.",
        color=0x00ff00,
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name="/createkey",
        value="Creates a 24-hour default key.\n**Usage**: `/createkey`\n**Example**: `/createkey`",
        inline=False
    )
    embed.add_field(
        name="/createpremiumkey",
        value="Creates a premium key with a custom expiration duration (e.g., 24d, 1h, 20m).\n**Usage**: `/createpremiumkey <duration>`\n**Example**: `/createpremiumkey 24d`",
        inline=False
    )
    embed.add_field(
        name="/resethwid",
        value="Resets the HWID for a specific key to empty.\n**Usage**: `/resethwid <key_id>`\n**Example**: `/resethwid 126b2503-1f79-4db5-beee-468f9b45862f`",
        inline=False
    )
    embed.add_field(
        name="/blacklistkey",
        value="Blacklists a key for a specified duration (default 7d) with an optional reason.\n**Usage**: `/blacklistkey <key_id> [duration] [reason]`\n**Example**: `/blacklistkey 126b2503-1f79-4db5-beee-468f9b45862f 1h Test ban`",
        inline=False
    )
    embed.add_field(
        name="/whitelistkey",
        value="Whitelists (unbans) a key with an optional reason.\n**Usage**: `/whitelistkey <key_id> [reason]`\n**Example**: `/whitelistkey 126b2503-1f79-4db5-beee-468f9b45862f Test unban`",
        inline=False
    )
    embed.add_field(
        name="/getkeysjson",
        value="Generates and uploads a JSON file with details for specified keys.\n**Usage**: `/getkeysjson <key_ids>`\n**Example**: `/getkeysjson 126b2503-1f79-4db5-beee-468f9b45862f 2a3b4c5d-6e7f-8g9h-0i1j-2k3l4m5n6o7p`",
        inline=False
    )
    embed.add_field(
        name="/getkeyid",
        value="Retrieves the Key ID for a given key name.\n**Usage**: `/getkeyid <key_name>`\n**Example**: `/getkeyid Cravex::Hub_1234567890`",
        inline=False
    )
    embed.add_field(
        name="/getkeyinfo",
        value="Retrieves detailed information for a given key name.\n**Usage**: `/getkeyinfo <key_name>`\n**Example**: `/getkeyinfo Cravex::Hub_1234567890`",
        inline=False
    )
    embed.add_field(
        name="/iskeyexpired",
        value="Checks if a key is expired by its Key ID.\n**Usage**: `/iskeyexpired <key_id>`\n**Example**: `/iskeyexpired 126b2503-1f79-4db5-beee-468f9b45862f`",
        inline=False
    )
    embed.add_field(
        name="⚠️ Note",
        value="All commands require Administrator permissions. Duration formats: `Xd` (days), `Xh` (hours), `Xm` (minutes). For /getkeysjson, provide key IDs separated by spaces.",
        inline=False
    )
    embed.set_footer(text=CRAVEX_PROMO_LINK)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="createkey", description="Creates a 24-hour key for administrators only")
@commands.has_permissions(administrator=True)
async def createkey(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    key_data = create_24h_key()
    if key_data:
        key_info = key_data['data']['defaultKey']
        key = key_info['key']
        key_id = key_info['id']
        created_at = key_info['createdAt']
        expires_at = key_info.get('expiredAt')
        embed = discord.Embed(title="🔑 24-Hour Key Created Successfully!", color=0x00ff00, timestamp=datetime.utcnow())
        embed.add_field(name="Key ID", value=f"`{key_id}`", inline=False)
        embed.add_field(name="Key", value=f"`{key}`", inline=False)
        if isinstance(created_at, str):
            created_ts = int(datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp())
        else:
            created_ts = int(created_at / 1000)
        embed.add_field(name="Created At", value=f"<t:{created_ts}:F>", inline=True)
        if expires_at:
            if isinstance(expires_at, str):
                expires_ts = int(datetime.fromisoformat(expires_at.replace('Z', '+00:00')).timestamp())
            else:
                expires_ts = int(expires_at / 1000)
            embed.add_field(name="Expires At", value=f"<t:{expires_ts}:F>", inline=True)
        else:
            embed.add_field(name="Expires At", value="24 hours from creation", inline=True)
        embed.add_field(name="⚠️ Important", value="Store this key securely; it cannot be retrieved again!", inline=False)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Failed to Create Key", description="Failed to create key. Please try again later.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="getkeysjson", description="Generates and uploads a JSON file with details for specified keys")
@commands.has_permissions(administrator=True)
async def getkeysjson(interaction: discord.Interaction, key_ids: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    key_id_list = [kid.strip() for kid in key_ids.split() if kid.strip()]
    if not key_id_list:
        embed = discord.Embed(title="❌ No Key IDs Provided", description="Please provide at least one valid key ID.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    keys = []
    failed_keys = []
    for key_id in key_id_list:
        key_data = get_key_details(key_id)
        if key_data:
            keys.append({
                "key_id": key_data.get("id", ""),
                "key": key_data.get("key", ""),
                "created_at": key_data.get("createdAt", ""),
                "expired_at": key_data.get("expiredAt", ""),
                "hwid": key_data.get("hwid", "")
            })
        else:
            failed_keys.append(key_id)
    if not keys:
        embed = discord.Embed(title="❌ Failed to Fetch Keys", description="Could not retrieve details for any of the provided key IDs. Please check the IDs and try again.", color=0xff0000, timestamp=datetime.utcnow())
        if failed_keys:
            embed.add_field(name="Failed Key IDs", value="```\n" + "\n".join(failed_keys) + "\n```", inline=False)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    json_str = json.dumps(keys, indent=2)
    file_buffer = io.StringIO(json_str)
    file = discord.File(file_buffer, filename=f"authguard_keys_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    embed = discord.Embed(title="📄 Keys JSON Generated Successfully!", description=f"Found details for {len(keys)} key(s). The JSON file is attached below.", color=0x00ff00, timestamp=datetime.utcnow())
    embed.add_field(name="Status", value="✅ File generated", inline=True)
    embed.add_field(name="Number of Keys", value=f"{len(keys)}", inline=True)
    if failed_keys:
        embed.add_field(name="Failed Key IDs", value="```\n" + "\n".join(failed_keys) + "\n```", inline=False)
        embed.add_field(name="⚠️ Note", value="Some keys could not be retrieved. Check the failed key IDs above.", inline=False)
    embed.set_footer(text=CRAVEX_PROMO_LINK)
    await interaction.followup.send(embed=embed, file=file, ephemeral=True)
    file_buffer.close()

@bot.tree.command(name="createpremiumkey", description="Creates a premium key with custom expiration for administrators only")
@commands.has_permissions(administrator=True)
async def createpremiumkey(interaction: discord.Interaction, duration: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        embed = discord.Embed(title="❌ Invalid Duration", description="Invalid duration format. Please use format like `24d`, `1h`, or `20m`.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    key_data = create_premium_key(duration_seconds)
    if key_data:
        key_info = key_data['data']['premiumKey']
        key = key_info['key']
        key_id = key_info['id']
        created_at = key_info['createdAt']
        expires_at = key_info.get('expiredAt')
        embed = discord.Embed(title="🔑 Premium Key Created Successfully!", color=0x00ff00, timestamp=datetime.utcnow())
        embed.add_field(name="Key ID", value=f"`{key_id}`", inline=False)
        embed.add_field(name="Key", value=f"`{key}`", inline=False)
        if isinstance(created_at, str):
            created_ts = int(datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp())
        else:
            created_ts = int(created_at / 1000)
        embed.add_field(name="Created At", value=f"<t:{created_ts}:F>", inline=True)
        if expires_at:
            if isinstance(expires_at, str):
                expires_ts = int(datetime.fromisoformat(expires_at.replace('Z', '+00:00')).timestamp())
            else:
                expires_ts = int(expires_at / 1000)
            embed.add_field(name="Expires At", value=f"<t:{expires_ts}:F>", inline=True)
        else:
            duration_display = f"{duration_seconds // 86400}d" if duration_seconds >= 86400 else \
                             f"{duration_seconds // 3600}h" if duration_seconds >= 3600 else \
                             f"{duration_seconds // 60}m"
            embed.add_field(name="Expires At", value=f"{duration_display} from creation", inline=True)
        embed.add_field(name="⚠️ Important", value="Store this key securely; it cannot be retrieved again!", inline=False)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Failed to Create Premium Key", description="Failed to create premium key. Please try again later.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="resethwid", description="Resets HWID for a key to empty for administrators only")
@commands.has_permissions(administrator=True)
async def resethwid(interaction: discord.Interaction, key_id: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    success = change_key_hwid(key_id.strip())
    if success:
        embed = discord.Embed(title="🔄 HWID Reset Successfully!", description=f"The HWID for key ID `{key_id.strip()}` has been reset to empty.", color=0x00ff00, timestamp=datetime.utcnow())
        embed.add_field(name="Key ID", value=f"`{key_id.strip()}`", inline=False)
        embed.add_field(name="Status", value="✅ Reset complete", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Failed to Reset HWID", description=f"Could not reset HWID for key ID `{key_id.strip()}`. Check the key ID and try again.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="blacklistkey", description="Blacklists a key for administrators only")
@commands.has_permissions(administrator=True)
async def blacklistkey(interaction: discord.Interaction, key_id: str, duration: str = "7d", reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        duration_seconds = 604800
    success = blacklist_key(key_id.strip(), duration_seconds, reason)
    if success:
        embed = discord.Embed(title="🚫 Key Blacklisted Successfully!", description=f"The key `{key_id.strip()}` has been blacklisted.", color=0xff0000, timestamp=datetime.utcnow())
        embed.add_field(name="Key ID", value=f"`{key_id.strip()}`", inline=False)
        embed.add_field(name="Duration", value=f"`{duration}`", inline=True)
        embed.add_field(name="Reason", value=f"`{reason}`", inline=True)
        embed.add_field(name="Status", value="✅ Blacklist complete", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Failed to Blacklist Key", description=f"Could not blacklist key `{key_id.strip()}`. Check the key ID and try again.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="whitelistkey", description="Whitelists (unbans) a key for administrators only")
@commands.has_permissions(administrator=True)
async def whitelistkey(interaction: discord.Interaction, key_id: str, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    success = whitelist_key(key_id.strip(), reason)
    if success:
        embed = discord.Embed(title="✅ Key Whitelisted Successfully!", description=f"The key `{key_id.strip()}` has been whitelisted.", color=0x00ff00, timestamp=datetime.utcnow())
        embed.add_field(name="Key ID", value=f"`{key_id.strip()}`", inline=False)
        embed.add_field(name="Reason", value=f"`{reason}`", inline=True)
        embed.add_field(name="Status", value="✅ Whitelist complete", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Failed to Whitelist Key", description=f"Could not whitelist key `{key_id.strip()}`. Check the key ID and try again.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="getkeyid", description="Retrieves the Key ID for a given key name")
@commands.has_permissions(administrator=True)
async def getkeyid(interaction: discord.Interaction, key_name: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    key_info = get_key_data_by_name(key_name.strip())
    if key_info and key_info.get("id"):
        embed = discord.Embed(title="✅ Key ID Found!", description=f"The Key ID for the provided key name.", color=0x00ff00, timestamp=datetime.utcnow())
        embed.add_field(name="Key Name", value=f"`{key_name.strip()}`", inline=False)
        embed.add_field(name="Key ID", value=f"`{key_info['id']}`", inline=False)
        embed.add_field(name="Status", value="✅ ID retrieved", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Key ID Not Found", description=f"Could not find Key ID for key name `{key_name.strip()}`.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="getkeyinfo", description="Retrieves detailed information for a given key name")
@commands.has_permissions(administrator=True)
async def getkeyinfo(interaction: discord.Interaction, key_name: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    key_info = get_key_data_by_name(key_name.strip())
    if key_info:
        embed = discord.Embed(title="✅ Key Information Found!", description="Detailed information for the provided key.", color=0x00ff00, timestamp=datetime.utcnow())
        embed.add_field(name="Key Name", value=f"`{key_info.get('key', 'N/A')}`", inline=False)
        embed.add_field(name="Key ID", value=f"`{key_info.get('id', 'N/A')}`", inline=False)
        embed.add_field(name="Service ID", value=f"`{key_info.get('serviceId', 'N/A')}`", inline=True)
        embed.add_field(name="Expires At", value=f"`{format_timestamp(key_info.get('expiredAt'))}`", inline=True)
        embed.add_field(name="HWID", value=f"`{key_info.get('hwid', 'None')}`", inline=True)
        embed.add_field(name="IP Address", value=f"`{key_info.get('ip', 'None')}`", inline=True)
        embed.add_field(name="Session ID", value=f"`{key_info.get('sessionId', 'None')}`", inline=True)
        embed.add_field(name="Discord ID", value=f"`{key_info.get('discordId', 'None')}`", inline=True)
        embed.add_field(name="Provider ID", value=f"`{key_info.get('providerId', 'None')}`", inline=True)
        embed.add_field(name="Created At", value=f"`{key_info.get('createdAt', 'N/A')}`", inline=True)
        embed.add_field(name="Blacklisted", value=f"`{'Yes' if key_info.get('isBlacklisted') else 'No'}`", inline=True)
        embed.add_field(name="Status", value="✅ Information retrieved", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Key Information Not Found", description=f"Could not find information for key name `{key_name.strip()}`.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="iskeyexpired", description="Checks if a key is expired by its Key ID")
@commands.has_permissions(administrator=True)
async def iskeyexpired(interaction: discord.Interaction, key_id: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    key_info = get_key_details(key_id.strip())
    if key_info:
        status_text = check_key_expiration(key_info)
        embed = discord.Embed(title="✅ Key Status Checked!", description=f"The status of the key `{key_id.strip()}`.", color=0x00ff00, timestamp=datetime.utcnow())
        embed.add_field(name="Key ID", value=f"`{key_id.strip()}`", inline=False)
        embed.add_field(name="Status", value=f"`{status_text}`", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Key Not Found", description=f"Could not find key `{key_id.strip()}`.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    max_retries = 5
    retry_delay = 5
    for attempt in range(max_retries):
        try:
            synced = await bot.tree.sync()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            else:
                raise e

if __name__ == "__main__":
    bot.run('BOT_TOKEN_HERE')
