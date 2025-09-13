import discord
from discord.ext import commands
import requests
import json
from datetime import datetime, timedelta
import asyncio
import re

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

AUTHGUARD_API_URL = "https://api.authguard.org"
API_TOKEN = "YOUR_API_TOKEN_HERE"
SERVICE_ID = YOUR_ID_HERE  # From provided URLs
CRAVEX_PROMO_LINK = "Developed by Cravex Team: https://discord.gg/NPzzhqTMvq"

def get_auth_headers():
    return {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://authguard.org",
        "Referer": "https://authguard.org/"
    }

def parse_duration(duration_str):
    """
    Parses duration string (e.g., '24d', '1h', '20m') into seconds.
    
    Args:
    - duration_str (str): Duration string (e.g., '24d', '1h', '20m').
    
    Returns:
    - int: Duration in seconds, or None if invalid.
    """
    match = re.match(r'^(\d+)([dhm])$', duration_str.lower().strip())
    if not match:
        return None
    
    value, unit = int(match.group(1)), match.group(2)
    if value <= 0:
        return None
    
    if unit == 'd':
        return value * 86400  # Days to seconds
    elif unit == 'h':
        return value * 3600   # Hours to seconds
    elif unit == 'm':
        return value * 60     # Minutes to seconds
    return None

def get_key_details(key_id):
    """
    Fetches details for a specific key using the Key Manager API.
    
    Args:
    - key_id (str): The Key ID to fetch.
    
    Returns:
    - dict: Key data if successful, None otherwise.
    """
    try:
        # Try service-specific endpoint first
        url = f"{AUTHGUARD_API_URL}/key-manager/service/{SERVICE_ID}/key/{key_id}"
        response = requests.get(url, headers=get_auth_headers())
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("data", {})
        
        # Fallback to default-key endpoint
        print("Service-specific endpoint failed, trying default...")
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key/{key_id}"
        response = requests.get(url, headers=get_auth_headers())
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("data", {})
        
        print(f"Error fetching key details: {response.status_code} - {response.text}")
        return None

    except Exception as e:
        print(f"Error interacting with AuthGuard API: {str(e)}")
        return None

def create_24h_key():
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key"
        payload = {
            "expiredAt": int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        }

        response = requests.post(
            url,
            headers=get_auth_headers(),
            json=payload
        )

        if response.status_code == 201:
            key_data = response.json()
            return key_data
        else:
            print(f"Error creating key: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"Error interacting with AuthGuard API: {str(e)}")
        return None

def create_premium_key(duration_seconds):
    """
    Creates a premium key with the specified expiration duration.
    
    Args:
    - duration_seconds (int): Duration in seconds until the key expires.
    
    Returns:
    - dict: Key data if successful, None otherwise.
    """
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/premium-key"
        expired_at = int((datetime.utcnow() + timedelta(seconds=duration_seconds)).timestamp())
        payload = {
            "expiredAt": expired_at
        }

        response = requests.post(
            url,
            headers=get_auth_headers(),
            json=payload
        )

        if response.status_code == 201:
            key_data = response.json()
            return key_data
        else:
            print(f"Error creating premium key: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"Error interacting with AuthGuard API: {str(e)}")
        return None

def change_key_hwid(key_id):
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key/{key_id}"
        payload = {
            "hwid": ""
        }

        response = requests.patch(
            url,
            headers=get_auth_headers(),
            json=payload
        )

        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("success"):
                return True
            else:
                print(f"Failed to update HWID: {response_data}")
                return False
        else:
            print(f"Error updating HWID: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Error interacting with AuthGuard API: {str(e)}")
        return False

def blacklist_key(key_id, duration_seconds=604800, reason="No reason provided"):
    """
    Blacklists a key by first fetching its associated HWID (if any) and then blacklisting the HWID.
    If no HWID is associated, attempts to disable the key by setting expiredAt early via PATCH.
    
    Args:
    - key_id (str): The Key ID to blacklist.
    - duration_seconds (int): Duration in seconds until blacklist expires (default: 7 days).
    - reason (str): Reason for blacklisting (default: "No reason provided").
    
    Returns:
    - bool: True if successful, False otherwise.
    """
    # Step 1: Fetch key details to get associated HWID
    key_data = get_key_details(key_id)
    if not key_data:
        print("Could not fetch key details. Cannot blacklist without HWID.")
        return False
    
    hwid = key_data.get("hwid")  # Assuming the field is "hwid" in key data
    if not hwid:
        print("No HWID associated with this key. Attempting to disable key directly...")
        # Fallback: Disable key by setting expiredAt to now + duration
        return disable_key(key_id, duration_seconds, reason)
    
    # Step 2: Blacklist the HWID
    try:
        url = f"{AUTHGUARD_API_URL}/key-manager/blacklist"
        expired_at = int((datetime.utcnow() + timedelta(seconds=duration_seconds)).timestamp())
        payload = {
            "hwid": hwid,
            "ip": None,
            "reason": reason,
            "expiredAt": expired_at
        }

        response = requests.post(
            url,
            headers=get_auth_headers(),
            json=payload
        )

        if response.status_code == 201:
            response_data = response.json()
            if response_data.get("success"):
                print(f"HWID '{hwid}' for key '{key_id}' blacklisted successfully! Blacklist ID: {response_data['data']['blacklist']['id']}")
                return True
            else:
                print(f"Failed to blacklist HWID: {response_data}")
                return False
        else:
            print(f"Error blacklisting HWID: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Error interacting with AuthGuard API: {str(e)}")
        return False

def disable_key(key_id, duration_seconds, reason):
    """
    Disables a key by setting its expiredAt to now + duration via PATCH.
    This is a fallback if no HWID is available for blacklisting.
    
    Args:
    - key_id (str): The Key ID to disable.
    - duration_seconds (int): Duration in seconds until expiration.
    - reason (str): Reason (not used in payload, but logged).
    
    Returns:
    - bool: True if successful, False otherwise.
    """
    try:
        print(f"Disabling key '{key_id}' directly (reason: {reason})")
        expired_at = int((datetime.utcnow() + timedelta(seconds=duration_seconds)).timestamp())
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key/{key_id}"
        payload = {
            "expiredAt": expired_at
            # Note: Reason might not be supported here; adjust if API allows it
        }

        response = requests.patch(
            url,
            headers=get_auth_headers(),
            json=payload
        )

        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("success"):
                print(f"Key '{key_id}' disabled successfully!")
                return True
            else:
                print(f"Failed to disable key: {response_data}")
                return False
        else:
            print(f"Error disabling key: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Error interacting with AuthGuard API: {str(e)}")
        return False

def get_blacklist_entry(hwid):
    """
    Queries the blacklist to find an entry for the given HWID.
    
    Args:
    - hwid (str): The HWID to check.
    
    Returns:
    - str: Blacklist ID if found, None otherwise.
    """
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
            print("No blacklist entry found for HWID.")
            return None
        
        print(f"Error querying blacklist: {response.status_code} - {response.text}")
        return None

    except Exception as e:
        print(f"Error interacting with AuthGuard API: {str(e)}")
        return None

def whitelist_key(key_id, reason="No reason provided"):
    """
    Whitelists a key by removing its HWID from the blacklist or restoring its expiration.
    
    Args:
    - key_id (str): The Key ID to whitelist.
    - reason (str): Reason for whitelisting (for logging, not sent in payload).
    
    Returns:
    - bool: True if successful, False otherwise.
    """
    try:
        # Step 1: Fetch key details to get HWID
        key_data = get_key_details(key_id)
        if not key_data:
            print("Could not fetch key details. Cannot whitelist.")
            return False
        
        hwid = key_data.get("hwid")
        if not hwid:
            print("No HWID associated with this key. Checking if key is disabled...")
            return restore_key_expiration(key_id, reason)
        
        # Step 2: Find blacklist entry for HWID
        blacklist_id = get_blacklist_entry(hwid)
        if not blacklist_id:
            print("No blacklist entry found for HWID. Checking if key is disabled...")
            return restore_key_expiration(key_id, reason)
        
        # Step 3: Delete blacklist entry
        url = f"{AUTHGUARD_API_URL}/key-manager/blacklist/{blacklist_id}"
        response = requests.delete(url, headers=get_auth_headers())
        
        if response.status_code in (200, 204):
            response_data = response.json() if response.text else {"success": True}
            if response_data.get("success", True):
                print(f"HWID '{hwid}' for key '{key_id}' removed from blacklist successfully!")
                return True
            else:
                print(f"Failed to remove blacklist entry: {response_data}")
                return False
        else:
            print(f"Error removing blacklist entry: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Error interacting with AuthGuard API: {str(e)}")
        return False

def restore_key_expiration(key_id, reason):
    """
    Restores a key by setting its expiredAt to a future date (1 year) if it was disabled.
    
    Args:
    - key_id (str): The Key ID to restore.
    - reason (str): Reason (for logging).
    
    Returns:
    - bool: True if successful, False otherwise.
    """
    try:
        print(f"Restoring key '{key_id}' expiration (reason: {reason})")
        expired_at = int((datetime.utcnow() + timedelta(days=365)).timestamp())  # 1 year
        url = f"{AUTHGUARD_API_URL}/key-manager/default-key/{key_id}"
        payload = {
            "expiredAt": expired_at
        }

        response = requests.patch(
            url,
            headers=get_auth_headers(),
            json=payload
        )

        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("success"):
                print(f"Key '{key_id}' expiration restored successfully!")
                return True
            else:
                print(f"Failed to restore key: {response_data}")
                return False
        else:
            print(f"Error restoring key: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Error interacting with AuthGuard API: {str(e)}")
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
        name="⚠️ Note",
        value="All commands require Administrator permissions. Duration formats: `Xd` (days), `Xh` (hours), `Xm` (minutes).",
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

    await interaction.response.defer()

    key_data = create_24h_key()
    
    if key_data:
        key_info = key_data['data']['defaultKey']
        key = key_info['key']
        key_id = key_info['id']
        created_at = key_info['createdAt']
        expires_at = key_info.get('expiredAt')
        
        embed = discord.Embed(
            title="🔑 24-Hour Key Created Successfully!",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
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
        
        embed.add_field(
            name="⚠️ Important", 
            value="Store this key securely; it cannot be retrieved again!", 
            inline=False
        )
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        
        await interaction.followup.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Failed to Create Key",
            description="Failed to create key. Please try again later.",
            color=0xff0000,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="createpremiumkey", description="Creates a premium key with custom expiration for administrators only")
@commands.has_permissions(administrator=True)
async def createpremiumkey(interaction: discord.Interaction, duration: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        embed = discord.Embed(
            title="❌ Invalid Duration",
            description="Invalid duration format. Please use format like `24d`, `1h`, or `20m`.",
            color=0xff0000,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed)
        return
    
    key_data = create_premium_key(duration_seconds)
    
    if key_data:
        # Assuming similar response structure to createkey; adjust if different
        key_info = key_data['data']['premiumKey']  # Assuming 'premiumKey' field; change if needed
        key = key_info['key']
        key_id = key_info['id']
        created_at = key_info['createdAt']
        expires_at = key_info.get('expiredAt')
        
        embed = discord.Embed(
            title="🔑 Premium Key Created Successfully!",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
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
            # Calculate display duration from seconds
            duration_display = f"{duration_seconds // 86400}d" if duration_seconds >= 86400 else \
                             f"{duration_seconds // 3600}h" if duration_seconds >= 3600 else \
                             f"{duration_seconds // 60}m"
            embed.add_field(name="Expires At", value=f"{duration_display} from creation", inline=True)
        
        embed.add_field(
            name="⚠️ Important", 
            value="Store this key securely; it cannot be retrieved again!", 
            inline=False
        )
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        
        await interaction.followup.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Failed to Create Premium Key",
            description="Failed to create premium key. Please try again later.",
            color=0xff0000,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="resethwid", description="Resets HWID for a key to empty for administrators only")
@commands.has_permissions(administrator=True)
async def resethwid(interaction: discord.Interaction, key_id: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    success = change_key_hwid(key_id.strip())
    
    if success:
        embed = discord.Embed(
            title="🔄 HWID Reset Successfully!",
            description=f"The HWID for key ID `{key_id.strip()}` has been reset to empty.",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Key ID", value=f"`{key_id.strip()}`", inline=False)
        embed.add_field(name="Status", value="✅ Reset complete", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Failed to Reset HWID",
            description=f"Could not reset HWID for key ID `{key_id.strip()}`. Check the key ID and try again.",
            color=0xff0000,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="blacklistkey", description="Blacklists a key for administrators only")
@commands.has_permissions(administrator=True)
async def blacklistkey(interaction: discord.Interaction, key_id: str, duration: str = "7d", reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        duration_seconds = 604800  # Default 7 days
        print("Invalid duration format. Using default of 7 days.")

    success = blacklist_key(key_id.strip(), duration_seconds, reason)
    
    if success:
        embed = discord.Embed(
            title="🚫 Key Blacklisted Successfully!",
            description=f"The key `{key_id.strip()}` has been blacklisted.",
            color=0xff0000,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Key ID", value=f"`{key_id.strip()}`", inline=False)
        embed.add_field(name="Duration", value=f"`{duration}`", inline=True)
        embed.add_field(name="Reason", value=f"`{reason}`", inline=True)
        embed.add_field(name="Status", value="✅ Blacklist complete", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Failed to Blacklist Key",
            description=f"Could not blacklist key `{key_id.strip()}`. Check the key ID and try again.",
            color=0xff0000,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="whitelistkey", description="Whitelists (unbans) a key for administrators only")
@commands.has_permissions(administrator=True)
async def whitelistkey(interaction: discord.Interaction, key_id: str, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    success = whitelist_key(key_id.strip(), reason)
    
    if success:
        embed = discord.Embed(
            title="✅ Key Whitelisted Successfully!",
            description=f"The key `{key_id.strip()}` has been whitelisted.",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Key ID", value=f"`{key_id.strip()}`", inline=False)
        embed.add_field(name="Reason", value=f"`{reason}`", inline=True)
        embed.add_field(name="Status", value="✅ Whitelist complete", inline=True)
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Failed to Whitelist Key",
            description=f"Could not whitelist key `{key_id.strip()}`. Check the key ID and try again.",
            color=0xff0000,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=CRAVEX_PROMO_LINK)
        await interaction.followup.send(embed=embed)

@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

if __name__ == "__main__":
    bot.run('BOT_TOKEN_HERE')
