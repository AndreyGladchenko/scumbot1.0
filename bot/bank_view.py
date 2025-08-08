# bank_view.py
from discord.ui import View, Button, Modal, TextInput
from discord import ButtonStyle, Interaction
import db

class BankView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(BalanceButton(bot))
        self.add_item(TransferButton(bot))
        self.add_item(PurchaseHistoryButton(bot))

class BalanceButton(Button):
    def __init__(self, bot):
        super().__init__(label="💰 Check Balance", style=ButtonStyle.green, custom_id="check_balance")
        self.bot = bot

    async def callback(self, interaction: Interaction):
        balance = db.get_balance_by_discord_id(interaction.user.id)
        await interaction.response.send_message(f"🪙 Your balance: **{int(balance)} coins**", ephemeral=True)

class TransferModal(Modal, title="Transfer Coins"):
    def __init__(self, bot, sender_id):
        super().__init__()
        self.bot = bot
        self.sender_id = sender_id

        self.add_item(TextInput(label="Recipient Discord ID", placeholder="e.g. 123456789012345678"))
        self.add_item(TextInput(label="Amount to transfer", placeholder="e.g. 50"))

    async def on_submit(self, interaction: Interaction):
        try:
            recipient_id = int(self.children[0].value.strip())
            amount = int(self.children[1].value.strip())
            sender_balance = db.get_balance_by_discord_id(self.sender_id)

            if recipient_id == self.sender_id:
                await interaction.response.send_message("❌ You cannot send coins to yourself.", ephemeral=True)
                return

            if amount <= 0 or sender_balance < amount:
                await interaction.response.send_message("❌ Invalid amount or insufficient balance.", ephemeral=True)
                return

            db.update_balance_by_discord_id(self.sender_id, -amount)
            db.update_balance_by_discord_id(recipient_id, amount)

            await interaction.response.send_message(
                f"✅ Transferred **{amount} coins** to <@{recipient_id}>.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

class TransferButton(Button):
    def __init__(self, bot):
        super().__init__(label="💸 Transfer Coins", style=ButtonStyle.blurple, custom_id="transfer_coin")
        self.bot = bot

    async def callback(self, interaction: Interaction):
        await interaction.response.send_modal(TransferModal(self.bot, interaction.user.id))

class PurchaseHistoryButton(Button):
    def __init__(self, bot):
        super().__init__(label="📜 Purchase History", style=ButtonStyle.secondary, custom_id="purchase_history")
        self.bot = bot

    async def callback(self, interaction: Interaction):
        orders = db.get_order_history_by_discord_id(interaction.user.id)
        if not orders:
            await interaction.response.send_message("📭 No purchases found.", ephemeral=True)
            return

        history = "\n".join(
            f"{o['item_name']} x{o['quantity']} — {o['created_at'].strftime('%Y-%m-%d')}"
            for o in orders
        )
        await interaction.response.send_message(f"🧾 **Your Purchase History**:\n```\n{history}\n```", ephemeral=True)
