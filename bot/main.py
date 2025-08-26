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
TAXI_CHANNEL_ID = int(os.getenv("TAXI_CHANNEL_ID", 0))  # taxi posting channel (e.g., 1408626703206580246)

# ─── GLOBALS ─────────────────────────────────────────────────
cooldowns = {}

# ─── FORMAT PRICE ────────────────────────────────────────────
def format_price(price):
    return str(int(float(price)))

# ─── PROCESS ITEM CONTENT ────────────────────────────────────
def process_item_content(content, player_name):
    """
    Parses the 'content' field from the DB and returns a list of SCUM commands.
    Supports:
    - JSON list: '["#teleportto {player}", "#spawnitem Weapon_A 1"]'
    - Plain multi-line text
    - Single string
    Replaces {player} with the SCUM username.
    """
    commands = []

    if not content:
        return commands

    # Try JSON first
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                commands = parsed
            else:
                commands = [str(parsed)]
        except json.JSONDecodeError:
            # Not JSON → treat as plain text lines
            commands = [line.strip() for line in content.splitlines() if line.strip()]
    elif isinstance(content, list):
        commands = content
    else:
        commands = [str(content)]

    # Replace placeholder with actual player name
    return [cmd.replace("{player}", player_name) for cmd in commands]

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
        self.bot.tree.add_command(self.send_taxis, guild=discord.Object(id=GUILD_ID)) # Register taxi command for the specific guild

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

        # ✅ Use unified content processor
        commands = process_item_content(item["content"], scum_username)

        # 🛠 Build the spawn command block for display/logging
        spawn_commands = "\n".join(commands)

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
        Uses process_item_content() to normalize commands and sends them to the delivery channel.
        """
        channel = self.bot.get_channel(PURCHASE_LOG_CHANNEL_ID)
        if not channel:
            print("❌ Could not find delivery channel.")
            return

        commands_list = process_item_content(commands, scum_username)

        if commands_list:
            text_block = "\n".join(commands_list)
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
            embed.add_field(name="Spawn Commands", value="\n".join(process_item_content(item["content"], "{player}")), inline=False)

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

        # ─── TAXI: post a single taxi to the taxi channel ───────
    async def post_taxi(self, taxi):
        if not TAXI_CHANNEL_ID:
            print("❌ TAXI_CHANNEL_ID not set")
            return
        channel = self.bot.get_channel(TAXI_CHANNEL_ID)
        if not channel:
            print("❌ Taxi channel not found")
            return

        price_display = format_price(taxi["price"])
        # coordinates is JSONB in DB; we just show a count to avoid clutter
        coords = taxi.get("coordinates")
        try:
            if isinstance(coords, str):
                coords = json.loads(coords)
        except Exception:
            pass
        coord_count = len(coords) if isinstance(coords, list) else 0

        embed = discord.Embed(
            title=f"🚖 {taxi['name']}",
            description=f"Price: **{price_display}** credits\nSpawn spots: **{coord_count}**",
            color=discord.Color.blurple()
        )
        view = TaxiView(self.bot, taxi["id"], taxi["name"], int(float(taxi["price"])))
        await channel.send(embed=embed, view=view)

    # ─── TAXI: admin command to (re)post all taxis ──────────
    @app_commands.command(name="send_taxis", description="Post all taxis to the taxi channel (admin only)")
    async def send_taxis(self, interaction: Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        if not TAXI_CHANNEL_ID:
            await interaction.response.send_message("❌ TAXI_CHANNEL_ID not set in .env", ephemeral=True)
            return

        # Fetch all taxis
        with db.get_connection() as conn:
            taxis = db.get_all_taxis(conn)

        if not taxis:
            await interaction.response.send_message("ℹ️ No taxis found to post.", ephemeral=True)
            return

        posted = 0
        for taxi in taxis:
            await self.post_taxi(taxi)
            posted += 1

        await interaction.response.send_message(f"✅ Posted {posted} taxi(s).", ephemeral=True)


    # ─── TAXI: button handler (deduct & create taxi order) ──
    async def order_taxi_from_button(self, interaction: discord.Interaction, taxi_id: int, taxi_name: str, price: int):
        # Ensure player exists
        player_id = db.get_or_create_player(interaction.user.id, "", interaction.user.name)

        # Check taxi still exists & get latest price (server-of-record)
        with db.get_connection() as conn:
            taxi = db.get_taxi_by_id(conn, taxi_id)
        if not taxi:
            await interaction.response.send_message("❌ Taxi no longer available.", ephemeral=True)
            return

        real_price = int(float(taxi["price"]))
        balance = db.get_balance(player_id)
        if balance < real_price:
            await interaction.response.send_message(
                f"❌ Not enough funds. Cost: {format_price(real_price)}, Balance: {format_price(balance)}",
                ephemeral=True
            )
            return

        # Deduct credits first (keeps pattern with your shop flow)
        db.update_balance(player_id, -real_price)

        # Create taxi order in DB
        with db.get_connection() as conn:
            db.create_taxi_order(conn, player_id, taxi_id)
            conn.commit()

        # Log to your delivery/admin channel (reuse PURCHASE_LOG_CHANNEL_ID if you like)
        delivery_channel = self.bot.get_channel(PURCHASE_LOG_CHANNEL_ID)
        if delivery_channel:
            await delivery_channel.send(
                f"🚕 **Taxi Ordered** — {interaction.user.display_name} → **{taxi['name']}** "
                f"for {format_price(real_price)} credits"
            )

        await interaction.response.send_message(
            f"✅ Taxi **{taxi_name}** ordered for {format_price(real_price)} credits! You’ll be teleported shortly.",
            ephemeral=True
        )

# ─── TAXI ORDER VIEW ────────────────────────────────────────
class TaxiView(View):
    def __init__(self, bot, taxi_id, taxi_name, price):
        super().__init__(timeout=None)
        self.add_item(OrderTaxiButton(bot, taxi_id, taxi_name, price))

class OrderTaxiButton(Button):
    def __init__(self, bot, taxi_id, taxi_name, price):
        super().__init__(
            label=f"🚖 Order {taxi_name}",
            style=ButtonStyle.blurple,
            custom_id=f"order_taxi:{taxi_id}"
        )
        self.bot = bot
        self.taxi_id = taxi_id
        self.taxi_name = taxi_name
        self.price = int(float(price))

    async def callback(self, interaction: Interaction):
        cog = self.bot.get_cog("ScumBot")
        if cog:
            await cog.order_taxi_from_button(interaction, self.taxi_id, self.taxi_name, self.price)


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

@flask_app.route("/api/repost_taxis", methods=["POST"])
def api_repost_taxis():
    scum_cog = bot.get_cog("ScumBot")
    if not scum_cog:
        return jsonify({"error": "ScumBot not ready"}), 500

    async def do_repost():
        channel_id = int(os.getenv("TAXI_CHANNEL_ID", "1408626703206580246"))
        channel = bot.get_channel(channel_id)
        if not channel:
            print("❌ Taxi channel not found.")
            return

        # Purge existing (non-pinned) messages in taxi channel
        def check(msg): return not msg.pinned
        await channel.purge(limit=None, check=check)

        # Get taxis from DB
        with db.get_connection() as conn:
            taxis = db.get_all_taxis(conn)

        # Post each taxi (reuse same logic from your /send_taxis command)
        for taxi in taxis:
            await scum_cog.post_taxi_item(channel, taxi)

        print("✅ Reposted taxis to Discord.")

    bot.loop.create_task(do_repost())
    return jsonify({"status": "reposted"}), 200


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
        # inside: if auto_refresh: ...
        taxi_channel = bot.get_channel(TAXI_CHANNEL_ID)
        if taxi_channel and TAXI_CHANNEL_ID:
            await purge_without_pins(taxi_channel)
            scum_cog = bot.get_cog("ScumBot")
            with db.get_connection() as conn:
                taxis = db.get_all_taxis(conn)
            for taxi in taxis:
                await scum_cog.post_taxi(taxi)
            print("✅ Taxis refreshed")

    # Start Flask in background
    threading.Thread(target=run_flask, daemon=True).start()

    print("✅ Bot is ready.")

# ─── RUN BOT ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("💡 main.py starting up...")
    bot.run(DISCORD_TOKEN)
