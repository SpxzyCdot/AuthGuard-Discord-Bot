import discord
from discord.ext import commands
import requests
import json
from datetime import datetime, timedelta, timezone
import asyncio
import re
import io
import os
import time
from typing import Optional, Dict, Any, List
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(script_dir, 'data.json')

try:
    with open(json_path, 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    print("Error: data.json not found. Please create it.")
    sys.exit()
except json.JSONDecodeError:
    print("Error: data.json contains invalid JSON.")
    sys.exit()

AUTHGUARD_API_URL = "https://api.authguard.org"
API_TOKEN: str = config.get("API_TOKEN")
SERVICE_ID: int = config.get("SERVICE_ID")
CRAVEX_PROMO_LINK: str = config.get("PROMO_LINK")
BOT_TOKEN: str = config.get("BOT_TOKEN")
DATE_FORMAT = "%Y-%m-%d %H:%M:%S UTC"

if not all([API_TOKEN, SERVICE_ID, CRAVEX_PROMO_LINK, BOT_TOKEN]):
    print("Error: Missing one or more required configuration values in data.json.")
    exit()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def get_auth_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://authguard.org",
        "Referer": "https://authguard.org/"
    }

def parse_duration(duration_str: str) -> Optional[int]:
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

def get_key_details(key_id: str) -> Optional[Dict[str, Any]]:
    endpoints = [
        f"{AUTHGUARD_API_URL}/key-manager/premium-key/{key_id}",
        f"{AUTHGUARD_API_URL}/key-manager/default-key/{key_id}",
        f"{AUTHGUARD_API_URL}/key-manager/service/{SERVICE_ID}/key/{key_id}"
    ]
    for url in endpoints:
        try:
            response = requests.get(url, headers=get_auth_headers(), timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("data", {}).get("defaultKey") or data.get("data", {}).get("premiumKey") or data.get("data", {})
        except Exception:
            continue
    return None

def get_key_data_by_name(key_name: str) -> Optional[Dict[str, Any]]:
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

def create_24h_key() -> Optional[Dict[str, Any]]:
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

def create_premium_key(duration_seconds: int) -> Optional[Dict[str, Any]]:
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

def change_key_hwid(key_id: str) -> bool:
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

def blacklist_key(key_id: str, duration_seconds: int = 604800, reason: str = "No reason provided") -> bool:
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

def disable_key(key_id: str, duration_seconds: int, reason: str) -> bool:
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

def get_blacklist_entry(hwid: str) -> Optional[str]:
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

def restore_key_expiration(key_id: str, reason: str) -> bool:
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

def whitelist_key(key_id: str, reason: str = "No reason provided") -> bool:
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

def format_timestamp(timestamp_s: Optional[int]) -> str:
    if timestamp_s is None or timestamp_s == 0:
        return "N/A (Never Expires)"
    try:
        if len(str(timestamp_s)) > 10:
             dt_object = datetime.fromtimestamp(timestamp_s / 1000, tz=timezone.utc)
        else:
             dt_object = datetime.fromtimestamp(timestamp_s, tz=timezone.utc)
        return dt_object.strftime(DATE_FORMAT)
    except Exception:
        return f"Invalid Timestamp ({timestamp_s})"

def check_key_expiration(key_info: Dict[str, Any]) -> str:
    expired_at_ts = key_info.get('expiredAt')
    current_ts = int(time.time())
    if expired_at_ts is None or expired_at_ts == 0:
        return "Permanent ✅"
    
    if len(str(expired_at_ts)) > 10:
        expired_at_ts = int(expired_at_ts / 1000)
        
    if expired_at_ts <= current_ts:
        return "Expired 🔴"
    else:
        return "Valid 🟢"

def get_premium_key_details(key_id: str) -> Optional[Dict[str, Any]]:
    url = f"{AUTHGUARD_API_URL}/key-manager/premium-key/{key_id}"
    
    try:
        response = requests.get(url, headers=get_auth_headers(), timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            premium_key_info = data.get("data", {}).get("premiumKey")
            
            if premium_key_info:
                return premium_key_info
            
            return None
        else:
            return None
    except Exception:
        return None

def attach_discord_id(key_id: str, discord_id: str) -> bool:
    url = f"{AUTHGUARD_API_URL}/key-manager/premium-key/{key_id}"
    payload = {
        "discordId": discord_id
    }
    
    try:
        response = requests.patch(
            url,
            headers=get_auth_headers(),
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("success"):
                return True
            return False
        return False
    except Exception:
        return False

def add_note_to_premium_key(key_id: str, note_content: str) -> bool:
    url = f"{AUTHGUARD_API_URL}/key-manager/premium-key/{key_id}"
    payload = {
        "note": note_content
    }
    try:
        response = requests.patch(url, headers=get_auth_headers(), json=payload)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("success") and response_data.get("statusCode") == 200:
                return True
            return False
        return False
    except Exception:
        return False

def download_default_keys() -> bool:
    url = f"{AUTHGUARD_API_URL}/key-manager/default-key"
    
    try:
        response = requests.get(url, headers=get_auth_headers(), timeout=10)
        response.raise_for_status()

        data = response.json()
        default_keys_list = data.get("data", {}).get("defaultKeys")

        if not isinstance(default_keys_list, list):
            return False
        
        output_content = ""
        separator = "-" * 33 + "\n"
        
        for key_data in default_keys_list:
            key_value = key_data.get("key", "N/A")
            key_id = key_data.get("id", "N/A")
            
            block = separator
            block += f"Key : {key_value}\n"
            block += f"ID : {key_id}\n"
            block += separator
            output_content += block

        with open("default_keys_dump.txt", "w", encoding="utf-8") as f:
            f.write(output_content)
        
        return True

    except:
        return False

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
        name="/attachdiscordid",
        value="Attaches a Discord User ID to a Premium Key ID.\n**Usage**: `/attachdiscordid <key_id> <discord_id>`\n**Example**: `/attachdiscordid 126b... 104472...`",
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
        value="Generates and uploads a JSON file with details for specified keys.\n**Usage**: `/getkeysjson <key_ids>`\n**Example**: `/getkeysjson 126b2503... 2a3b4c5d...`",
        inline=False
    )
    embed.add_field(
        name="/getdefaultkeyid",
        value="Retrieves the Key ID for a given key name.\n**Usage**: `/getdefaultkeyid <key_name>`\n**Example**: `/getdefaultkeyid Cravex::Hub_1234567890`",
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
        name="/downloaddefaultkeys",
        value="Downloads all default keys to a text file.\n**Usage**: `/downloaddefaultkeys`\n**Example**: `/downloaddefaultkeys`",
        inline=False
    )
    embed.add_field(
        name="/addnotetopremiumkey",
        value="Adds a note to a premium key.\n**Usage**: `/addnotetopremiumkey <key_id> <note>`\n**Example**: `/addnotetopremiumkey 126b2503... Customer purchased 1-year plan`",
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

        try:
            created_ts = int(datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp())
        except ValueError:
            created_ts = int(created_at / 1000) if isinstance(created_at, (int, float)) else int(time.time())

        embed.add_field(name="Created At", value=f"<t:{created_ts}:F>", inline=True)
        
        expires_ts = None
        if expires_at:
            if isinstance(expires_at, str):
                try:
                    expires_ts = int(datetime.fromisoformat(expires_at.replace('Z', '+00:00')).timestamp())
                except ValueError:
                    expires_ts = None
            elif isinstance(expires_at, (int, float)):
                expires_ts = int(expires_at)
                if len(str(expires_ts)) > 10:
                    expires_ts = int(expires_ts / 1000)

        if expires_ts:
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
        
        try:
            created_ts = int(datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp())
        except ValueError:
            created_ts = int(created_at / 1000) if isinstance(created_at, (int, float)) else int(time.time())

        embed.add_field(name="Created At", value=f"<t:{created_ts}:F>", inline=True)
        
        expires_ts = None
        if expires_at:
            if isinstance(expires_at, str):
                try:
                    expires_ts = int(datetime.fromisoformat(expires_at.replace('Z', '+00:00')).timestamp())
                except ValueError:
                    expires_ts = None
            elif isinstance(expires_at, (int, float)):
                expires_ts = int(expires_at)
                if len(str(expires_ts)) > 10:
                    expires_ts = int(expires_ts / 1000)

        if expires_ts:
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

@bot.tree.command(name="attachdiscordid", description="Attaches a Discord User ID to a Premium Key ID")
@commands.has_permissions(administrator=True)
async def attachdiscordid(interaction: discord.Interaction, key_id: str, discord_id: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    
    if not discord_id.isdigit():
        embed = discord.Embed(title="❌ Invalid Discord ID", description="The Discord ID must be a numeric value.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    key_info = get_premium_key_details(key_id)
    if not key_info:
        embed = discord.Embed(title="❌ Invalid Key ID", description=f"Could not verify key ID `{key_id.strip()}`. Ensure it is a valid Premium Key.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    success = attach_discord_id(key_id.strip(), discord_id.strip())
    
    if success:
        embed = discord.Embed(title="🔗 Discord ID Attached Successfully!", description="The Discord ID has been linked to the Premium Key.", color=0x00ff00, timestamp=datetime.utcnow())
        embed.add_field(name="Key ID", value=f"`{key_id.strip()}`", inline=False)
        embed.add_field(name="Discord ID", value=f"`{discord_id.strip()}`", inline=True)
        embed.add_field(name="Status", value="✅ Attachment complete", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Failed to Attach Discord ID", 
                              description=f"Could not attach Discord ID to key `{key_id.strip()}`. "
                                          f"Ensure the Key ID is correct and is a **Premium Key**.", 
                              color=0xff0000, timestamp=datetime.utcnow())
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

@bot.tree.command(name="getdefaultkeyid", description="Retrieves the Key ID for a given key name")
@commands.has_permissions(administrator=True)
async def getdefaultkeyid(interaction: discord.Interaction, key_name: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    key_info = get_key_data_by_name(key_name.strip())
    if key_info and key_info.get("id"):
        embed = discord.Embed(title="✅ Key ID Found!", description="The Key ID for the provided key name.", color=0x00ff00, timestamp=datetime.utcnow())
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

@bot.tree.command(name="downloaddefaultkeys", description="Downloads all default keys to a text file")
@commands.has_permissions(administrator=True)
async def downloaddefaultkeys(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    success = download_default_keys()
    if success:
        file = discord.File("default_keys_dump.txt", filename=f"default_keys_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt")
        embed = discord.Embed(title="✅ Default Keys Downloaded!", description="All default keys have been downloaded to a text file.", color=0x00ff00, timestamp=datetime.utcnow())
        embed.add_field(name="Status", value="✅ File generated", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Failed to Download Keys", description="Could not retrieve default keys. Please try again later.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="addnotetopremiumkey", description="Adds a note to a premium key")
@commands.has_permissions(administrator=True)
async def addnotetopremiumkey(interaction: discord.Interaction, key_id: str, note: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    
    key_info = get_premium_key_details(key_id)
    if not key_info:
        embed = discord.Embed(title="❌ Invalid Key ID", description=f"Could not verify key ID `{key_id.strip()}`. Ensure it is a valid Premium Key.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    success = add_note_to_premium_key(key_id.strip(), note.strip())
    
    if success:
        embed = discord.Embed(title="✅ Note Added Successfully!", description="The note has been added to the Premium Key.", color=0x00ff00, timestamp=datetime.utcnow())
        embed.add_field(name="Key ID", value=f"`{key_id.strip()}`", inline=False)
        embed.add_field(name="Note", value=f"`{note.strip()}`", inline=True)
        embed.add_field(name="Status", value="✅ Note added", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Failed to Add Note", description=f"Could not add note to key `{key_id.strip()}`. Ensure the Key ID is correct and is a **Premium Key**.", color=0xff0000, timestamp=datetime.utcnow())
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    max_retries = 5
    retry_delay = 5
    for attempt in range(max_retries):
        try:
            print("Attempting to sync application commands...")
            synced = await bot.tree.sync()
            print(f"Successfully synced {len(synced)} command(s).")
            break
        except Exception as e:
            print(f"Sync attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                raise e

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
