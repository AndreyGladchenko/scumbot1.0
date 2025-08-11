# main.py – SCUM Bot for Discord Shop System

import os
import time
import discord
import json
from discord import app_commands, Interaction, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import threading
import db
from bank_view import BankView



print("💡 main.py starting up...")


load_dotenv()

# ─── ENV CONFIG ──────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SHOP_LOG_CHANNEL_ID = int(os.getenv("SHOP_LOG_CHANNEL_ID"))
PURCHASE_LOG_CHANNEL_ID = int(os.getenv("PURCHASE_LOG_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))
COMMAND_RELAY_FILE = os.getenv("COMMAND_RELAY_FILE", "outgoing_commands.txt")
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Admin")
COOLDOWN_SECONDS = 60
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID"))
BANK_CHANNEL_ID = int(os.getenv("BANK_CHANNEL_ID"))
BOT_STATUS_CHANNEL_ID = int(os.getenv("BOT_STATUS_CHANNEL_ID"))
last_status_message_id = None  # store the message ID so we can edit it later

# ─── GLOBALS ─────────────────────────────────────────────────
cooldowns = {}

# ─── FORMAT PRICE ────────────────────────────────────────────
def format_price(price):
    return str(int(float(price)))

# ─── DISCORD VIEW FOR BUTTON ────────────────────────────────
class ShopItemView(View):
    def __init__(self, bot, item_name):
        super().__init__(timeout=None)
        self.add_item(BuyButton(bot, item_name))

class BuyButton(Button):
    def __init__(self, bot, item_name):
        super().__init__(label="🛒 Buy", style=ButtonStyle.green, custom_id=f"buy_item_by_name:{item_name}")
        self.bot = bot
        self.item_name = item_name

    async def callback(self, interaction: Interaction):
        cog = self.bot.get_cog("ScumBot")
        if cog:
            await cog.buy_from_button(interaction, self.item_name)

# ─── DISCORD COG ─────────────────────────────────────────────
class ScumBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(self.send_bank_buttons, guild=discord.Object(id=GUILD_ID)) # Register bank buttons command for the specific guild
        # Register slash commands manually with the bot's app command tree
        #self.bot.tree.add_command(self.send_bank_buttons)

    async def log_command(self, interaction, message):
        if LOG_CHANNEL_ID:
            channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if channel:
                await channel.send(f"📜 {interaction.user} used `{interaction.command.name}`: {message}")

    def queue_spawn_command(self, item_name, player_name, quantity):
        with open(COMMAND_RELAY_FILE, "a") as f:
            for _ in range(quantity):
                f.write(f"#spawnitem {item_name} {player_name}\n")

    def is_on_cooldown(self, user_id):
        now = time.time()
        return user_id in cooldowns and now - cooldowns[user_id] < COOLDOWN_SECONDS

    def set_cooldown(self, user_id):
        cooldowns[user_id] = time.time()

    async def is_admin(self, interaction):
        guild = interaction.guild
        if not guild:
            return False
        member = await guild.fetch_member(interaction.user.id)
        return any(role.name == ADMIN_ROLE_NAME for role in member.roles)

    async def buy_from_button(self, interaction: discord.Interaction, item_name: str):
        player_id = db.get_or_create_player(interaction.user.id, "", interaction.user.name)
        item = db.get_shop_item_by_name(item_name)

        if not item:
            await interaction.response.send_message("❌ Item not found.", ephemeral=True)
            return

        quantity = 1
        total_cost = item["price"] * quantity
        balance = db.get_balance(player_id)

        if balance < total_cost:
            await interaction.response.send_message(
                f"❌ You don’t have enough funds. Cost: {total_cost}, Balance: {balance}", ephemeral=True
            )
            return

        # Deduct and save order
        db.update_balance(player_id, -total_cost)
        order_id = db.save_order_to_db(player_id, item["id"], quantity)  # keep ID for future tracking

        # Get SCUM username
        player = db.get_player_by_discord_id(interaction.user.id)
        scum_username = player.get("scum_username", interaction.user.name)

        # ✅ Parse content into a list of spawn commands
        commands = item["content"]
        if isinstance(commands, str):
            try:
                commands = json.loads(commands)  # parse JSON string to list
            except json.JSONDecodeError:
                commands = [commands]  # fallback to single string
        elif not isinstance(commands, list):
            commands = [str(commands)]

        # 🛠 Build the commands (easy to change format later)
        #spawn_commands = "\n".join([f"#spawnitem {cmd.split()[-1]} {scum_username}" for cmd in commands])
        spawn_commands = "\n".join([f"#teleportto {scum_username} #spawnitem {cmd.split()[-1]}" for cmd in commands])

        # Post delivery log
        delivery_channel = self.bot.get_channel(1398829991466242179)  # bot-shop-delivery
        if delivery_channel:
            delivery_msg = (
                f"📦 **New Delivery**\n"
                f"🧍 Player: **{scum_username}**\n"
                f"📦 Item: **{item['name']}**\n"
                f"💰 Price: {format_price(item['price'])}\n"
                f"🔢 Quantity: {quantity}\n"
                f"🕒 Time: {discord.utils.format_dt(discord.utils.utcnow(), style='f')}\n"
                f"```{spawn_commands}```"
            )
            await delivery_channel.send(delivery_msg)

        await interaction.response.send_message(
            f"✅ You purchased {item['name']} for {total_cost}. Delivery in progress...", ephemeral=True
        )

    async def send_spawn_command_to_discord(self, commands, scum_username: str):
        """
        Robustly accept commands as:
        - a Python list of strings
        - a JSON string (e.g. '["#spawnitem Weapon_A 1"]')
        - a single string (e.g. "#spawnitem Weapon_A 1")
        and send properly formatted spawn lines to the PURCHASE_LOG_CHANNEL_ID.
        """
        channel = self.bot.get_channel(PURCHASE_LOG_CHANNEL_ID)
        if not channel:
            print("❌ Could not find delivery channel.")
            return

        # --- Normalize commands into a list of strings ---
        commands_list = []

        # If it's JSON text, try to parse it
        if isinstance(commands, str):
            try:
                parsed = json.loads(commands)
                # parsed might be a list, a dict, or a single string
                if isinstance(parsed, list):
                    commands_list = [str(x) for x in parsed]
                elif isinstance(parsed, dict):
                    # handle common patterns: maybe {"Contents": [...] } or {"content": [...]}
                    if "Contents" in parsed and isinstance(parsed["Contents"], list):
                        commands_list = [str(x) for x in parsed["Contents"]]
                    elif "content" in parsed and isinstance(parsed["content"], list):
                        commands_list = [str(x) for x in parsed["content"]]
                    else:
                        commands_list = [json.dumps(parsed)]
                else:
                    commands_list = [str(parsed)]
            except json.JSONDecodeError:
                # plain string (not JSON)
                commands_list = [commands]
        elif isinstance(commands, (list, tuple, set)):
            commands_list = [str(x) for x in commands]
        else:
            # fallback: turn whatever it is into a single string
            commands_list = [str(commands)]

        # --- Parse each command string and build proper spawn lines ---
        messages = []
        for cmd in commands_list:
            cmd = cmd.strip()
            if not cmd:
                continue

            tokens = cmd.split()
            # If the command already starts with '#spawnitem' (or 'spawnitem')
            if len(tokens) >= 2 and tokens[0].lstrip('#').lower() == "spawnitem":
                item_token = tokens[1]
                # preserve quantity if present (last token numeric)
                qty_suffix = ""
                if len(tokens) >= 3 and tokens[-1].isdigit():
                    qty_suffix = f" {tokens[-1]}"
                spawn_line = f"#spawnitem {item_token}{qty_suffix} {scum_username}"
                messages.append(spawn_line)
            else:
                # Fallback: try to take the first token as the item name
                # (this handles if the DB stored just "Weapon_A" or similar)
                first = tokens[0] if tokens else cmd
                messages.append(f"#spawnitem {first} {scum_username}")

        # --- Send as a single code block with one command per line ---
        if messages:
            text_block = "\n".join(messages)
            await channel.send(f"📦 New Delivery:\n```{text_block}```")
 

    async def post_shop_item(self, item):
        channel = self.bot.get_channel(SHOP_LOG_CHANNEL_ID)
        if not channel:
            print("❌ Could not find shop channel.")
            return

        embed = discord.Embed(
            title=item["name"],
            description=item.get("description", "No description."),
            color=discord.Color.green()
        )
        embed.add_field(name="Price", value=format_price(item["price"]), inline=True)
        embed.add_field(name="Category", value=item["category"], inline=True)

        if item.get("image_url"):
            embed.set_image(url=item["image_url"])
        if item.get("content"):
            embed.add_field(name="Spawn Commands", value="\n".join(item["content"]), inline=False)

        view = ShopItemView(self.bot, item["name"])
        message = await channel.send(embed=embed, view=view)
        db.update_shop_item_message_info(item["id"], str(message.id), str(channel.id))

    @app_commands.command(name="register", description="Register your SCUM username")
    async def register(self, interaction: Interaction, scum_username: str):
        db.get_or_create_player(interaction.user.id, scum_username, interaction.user.name)
        await interaction.response.send_message(f"✅ Registered as `{scum_username}`.", ephemeral=True)
        await self.log_command(interaction, f"registered as {scum_username}")

    @app_commands.command(name="buy", description="Buy an item from the shop")
    @app_commands.describe(item_name="The exact name of the item")
    async def buy(self, interaction: discord.Interaction, item_name: str, quantity: int = 1):
        if quantity < 1:
            await interaction.response.send_message("❌ Quantity must be at least 1.", ephemeral=True)
            return
        if not await self.is_admin(interaction) and self.is_on_cooldown(interaction.user.id):
            await interaction.response.send_message("⏳ Please wait before using this command again.", ephemeral=True)
            return

        player_id = db.get_or_create_player(interaction.user.id, "", interaction.user.name)
        item = db.get_shop_item_by_name(item_name)

        if not item:
            await interaction.response.send_message("❌ Item not found.", ephemeral=True)
            return

        total = item["price"] * quantity
        if db.get_balance(player_id) < total:
            await interaction.response.send_message(f"❌ Not enough funds. Total cost is {format_price(total)}.", ephemeral=True)
            return

        db.update_balance(player_id, -total)
        db.save_order_to_db(player_id, item["id"], quantity)
        self.set_cooldown(interaction.user.id)

        await interaction.response.send_message(
            f"✅ Purchased {quantity}x {item['name']} for {format_price(total)}.",
            ephemeral=True
        )

        delivery_channel = self.bot.get_channel(PURCHASE_LOG_CHANNEL_ID)
        if delivery_channel:
            await delivery_channel.send(
                f"📦 {interaction.user.display_name} bought {quantity}x {item['name']} for {format_price(total)}"
            )

    @app_commands.command(name="send_shop_items", description="Post all shop items to the shop channel (admin only)")
    async def send_shop_items(self, interaction: Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        items = db.get_shop_items()
        for item in items:
            await self.post_shop_item(item)

        await interaction.response.send_message("✅ Posted all items.", ephemeral=True)

    @app_commands.command(name="send_bank_buttons", description="Post bank UI with balance, transfer, and history")
    async def send_bank_buttons(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        print("🧪 Creating BankView...")
        channel = self.bot.get_channel(BANK_CHANNEL_ID)
        if channel:
            await channel.send("🏦 **Bank Actions:**", view=BankView(self.bot))
            await interaction.response.send_message("✅ Posted bank buttons.", ephemeral=True)
        print("✅ Sent bank message")


# ─── FLASK APP (Internal API for Admin Portal) ──────────────
flask_app = Flask(__name__)

@flask_app.route('/api/post_item', methods=['POST'])
def api_post_item():
    data = request.json
    if not data:
        return jsonify({"error": "No JSON provided"}), 400

    print("📨 Received /api/post_item:", data)
    bot.loop.create_task(bot.get_cog("ScumBot").post_shop_item(data))
    return jsonify({"status": "posted"}), 200

def run_flask():
    print("🌐 Starting internal Flask API on port 3000")
    flask_app.run(host='0.0.0.0', port=3000)

# ─── BOT SETUP ───────────────────────────────────────────────
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
print(f"💡 Bot object created: {bot}")

@bot.event
async def on_ready():
    print("🔧 on_ready started")
    db.init()
    print("✅ DB initialized")

    await bot.add_cog(ScumBot(bot))
    print("✅ Cog added")

    try:
        guild = discord.Object(id=GUILD_ID)
        await bot.tree.sync(guild=guild)
        print("✅ Commands synced")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

    # BOT STATUS MESSAGE
    try:
        status_channel = await bot.fetch_channel(BOT_STATUS_CHANNEL_ID)
        status_text = f"✅ **Bot is online** — Ready at {discord.utils.format_dt(discord.utils.utcnow(), style='F')}"
        last_bot_message = None
        async for msg in status_channel.history(limit=10):
            if msg.author.id == bot.user.id:
                last_bot_message = msg
                break
        if last_bot_message:
            await last_bot_message.edit(content=status_text)
            print(f"✅ Updated existing status message: {last_bot_message.id}")
        else:
            sent_msg = await status_channel.send(status_text)
            print(f"✅ Created new status message: {sent_msg.id}")
    except Exception as e:
        print(f"❌ Failed to send bot status: {e}")

    # AUTO REFRESH SHOP & BANK
    auto_refresh = os.getenv("AUTO_REFRESH_ON_STARTUP", "false").lower() == "true"
    if auto_refresh:
        print("♻️ Auto-refresh enabled — clearing and repopulating channels")
        scum_cog = bot.get_cog("ScumBot")

        async def purge_without_pins(channel):
            def check(msg):
                return not msg.pinned
            await channel.purge(limit=None, check=check)

        shop_channel = bot.get_channel(SHOP_LOG_CHANNEL_ID)
        if shop_channel:
            await purge_without_pins(shop_channel)
            items = db.get_shop_items()
            for item in items:
                await scum_cog.post_shop_item(item)
            print("✅ Shop items refreshed")

        bank_channel = bot.get_channel(BANK_CHANNEL_ID)
        if bank_channel:
            await purge_without_pins(bank_channel)
            await bank_channel.send("🏦 **Bank Actions:**", view=BankView(bot))
            print("✅ Bank buttons refreshed")

    # Start Flask in background
    threading.Thread(target=run_flask, daemon=True).start()

    print("✅ Bot is ready.")

# ─── RUN BOT ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("💡 main.py starting up...")
    bot.run(DISCORD_TOKEN)




