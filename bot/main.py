# main.py – SCUM Bot for Discord Shop System

import os
import time
import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import threading
import db
from bank_view import BankView

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

        # Deduct balance & log order
        db.update_balance(player_id, -total_cost)
        db.save_order_to_db(player_id, item["id"], quantity)

        # Get player's SCUM name for spawn delivery
        player = db.get_player_by_discord_id(interaction.user.id)
        scum_username = player.get("scum_username", interaction.user.name)  # fallback to Discord name

        await self.send_spawn_command_to_discord(item["content"], scum_username)

        await interaction.response.send_message(
            f"✅ You purchased {item['name']} for {total_cost}. Delivery in progress...", ephemeral=True
        )

    async def send_spawn_command_to_discord(self, commands: list, scum_username: str):
        channel = self.bot.get_channel(PURCHASE_LOG_CHANNEL_ID)
        if not channel:
            print("❌ Could not find delivery channel.")
            return

        messages = []
        for command in commands:
            parts = command.split()
            if len(parts) >= 2:
                spawn_line = f"#SpawnItem {parts[1]} {scum_username}"
                messages.append(spawn_line)

        if messages:
            await channel.send(f"📦 New Delivery:\n```{chr(10).join(messages)}```")

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


# ─── BOT SETUP ───────────────────────────────────────────────
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("🔧 on_ready started")
    db.init()
    print("✅ DB initialized")

    await bot.add_cog(ScumBot(bot))
    print("✅ Cog added")

    try:
        guild = discord.Object(id=GUILD_ID)
        #bot.tree.clear_commands(guild=guild)  # no await here
        print("🔄 Cleared guild commands")

        await bot.tree.sync(guild=guild)
        print("✅ Commands synced")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

    print("✅ Bot is ready.")


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

# ─── RUN ─────────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(DISCORD_TOKEN)
