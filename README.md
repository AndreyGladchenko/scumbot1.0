# 🛒 SCUM Discord Bot Shop System

A full-stack, self-hosted shop system for SCUM game servers. Players buy items via Discord using buttons or slash commands. Admins manage everything via a web portal. Includes full **delivery automation** and **taxi support**.

---

## ✨ Features

- 🛒 Buy items via Discord (slash commands + buttons)
- 🚖 **Taxi booking system** – players can order taxis in-game via Discord
- 🤖 **Delivery bot automation** – spawns purchased items & taxis in-game (Windows PC)
- 🔐 Admin-only web interface
- 💾 PostgreSQL database
- 📦 JSON import/export of shop items
- ♻️ Auto-refresh shop, bank & taxis on bot startup
- 🚀 Fully Dockerized (easy to deploy)

---

## 🚀 Setup Instructions

> 🐳 You only need **Docker** and **Git** installed

### 1. Clone the repository

```bash
git clone https://github.com/NARobz/scumbot1.0.git
cd scumbot1.0
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` and fill in your secrets and channel IDs (see guide below).

### 3. Build and start everything

```bash
docker compose up -d --build
```

### 4. Done!

- Bot will appear online in your server
- Visit admin panel: http://localhost:5000
- All containers are running in the background

---

## ⚙️ Environment Variables (`.env`)

> Use `.env.example` as your template.

#####################################
# ⚙️  Discord Bot Configuration
#####################################

DISCORD_TOKEN=your_discord_bot_token_here     # 🔐 Your bot token from the Discord developer portal
DISCORD_GUILD_ID=your_guild_id_here           # 🏠 ID of the Discord server where the bot operates
ADMIN_ROLE_NAME=Admin                         # 👑 Role name with admin permissions (case-sensitive)

#####################################
# 🛠️  Channel Configuration (Discord)
#####################################

LOG_CHANNEL_ID=                                # 📜 Channel ID where admin command logs are posted (e.g. bot-shop-admin)
SHOP_LOG_CHANNEL_ID=                           # 🛒 Channel ID where shop items are posted (e.g. bot-shop)
PURCHASE_LOG_CHANNEL_ID=                       # 📦 Channel ID where purchases are logged (e.g. bot-shop-delivery)
BANK_CHANNEL_ID=                                # 🏦 Channel ID for bank actions
TAXI_CHANNEL_ID=                                # 🚖 Channel ID where taxi order buttons will be posted
BOT_STATUS_CHANNEL_ID=                          # 📡 Bot status updates channel

DISCORD_WEBHOOK_URL=                            # 🌐 Optional webhook URL if used for posting shop items (leave blank if using bot instead)

#####################################
# 🐘 PostgreSQL Database Configuration
#####################################

POSTGRES_HOST=db                               # Hostname of the PostgreSQL container (usually "db" in Docker)
POSTGRES_PORT=5432                             # Port PostgreSQL listens on (default: 5432)
POSTGRES_DB=scumshop                           # Database name
POSTGRES_USER=scumuser                         # Database user
POSTGRES_PASSWORD=your_postgres_password       # Database password
DATABASE_URL=postgresql://scumuser:password@db:5432/scumshop   # Optional full connection string (overrides above if set)

#####################################
# 🔐 Flask & Internal API
#####################################

FLASK_SECRET_KEY=your_flask_secret_key_here    # 🔐 Secret key for Flask session security
BOT_API_URL=http://discord-bot:3000/api/post_item       # 🔁 Internal API for posting shop items
BOT_API_URL_REPOST_TAXIS=http://discord-bot:3000/api/repost_taxis  # 🔁 Internal API for refreshing taxi posts

#####################################
# 📄 Other Bot Settings
#####################################

COMMAND_RELAY_FILE=/app/outgoing_commands.txt  # 📝 File where spawn commands are queued (if not sent to Discord)
AUTO_REFRESH_ON_STARTUP=true                   # ♻️ If true, clears & repopulates shop/bank/taxi channels on bot startup

#####################################
# 💻 Delivery Bot (Windows PC)
#####################################

# Connection to main DB for reading orders & taxis
DATABASE_URL=postgresql://scumuser:password@HOST_IP:5432/scumshop

# Steam & SCUM game config
STEAM_PATH=C:\Program Files (x86)\Steam\steam.exe
SCUM_APP_ID=513710                              # Steam app ID for SCUM
GAME_CLIENT_PATH=                               # Optional direct path to SCUM.exe

# Drone settings for delivery bot
STAGING_COORDS=X=0 Y=0 Z=0                      # Safe staging coordinates for drone to return to
SCREEN_WIDTH=1280                               # Width to resize SCUM window to
SCREEN_HEIGHT=720                               # Height to resize SCUM window to

---

## 🧾 Slash Commands

Use inside your Discord server:

/register <scum_username> – Link your Discord to your SCUM name

/buy <item_name> [quantity] – Buy an item

/send_shop_items – Admin only: Post all shop items with buttons

/send_taxis – Admin only: Post all taxis with order buttons
---

## 🛍 Buy & Taxi Buttons

Buy buttons appear for each shop item posted

Taxi buttons appear for each taxi route posted

Clicking:

      Checks user balance

      Deducts cost

      Logs order

      Sends to delivery bot for in-game execution
---

## 🛠 Admin Panel

Open your browser to: http://localhost:5000

Manage:

✅ Add/edit/delete shop items

🚖 Add/edit/delete taxis (with coordinates)

👤 Manage players

📜 View order history

📥 Import/export JSON

📬 Trigger posting shop items & taxis to Discord

🤖 Delivery Bot (Windows)

Runs on a separate PC with SCUM installed

Uses Steam to launch SCUM and automates admin drone mode

Picks up pending orders (items & taxis) and fulfills them automatically

Requires .env configuration with:

          DATABASE_URL pointing to your main DB

          STEAM_PATH, SCUM_APP_ID, and STAGING_COORDS
---

## 🐘 PostgreSQL

Postgres stores all players, items, balances, and orders.

To access it:

```bash
docker compose exec db psql -U scumuser -d scumshop
```

---

## 🐛 Troubleshooting

- See logs:  
  ```bash
  docker compose logs -f
  ```

- Restart everything:
  ```bash
  docker compose down
  docker compose up -d --build
  ```

- Check your `.env` is filled correctly

---

## 📁 File Structure

```
scumbot1.0/
├── bot/
│   ├── main.py                 # Discord bot + internal Flask API
│   ├── db.py                   # Database functions
│   ├── schema.sql              # DB schema
│   └── outgoing_commands.txt   # Command relay file
│
├── web/
│   ├── app.py                  # Flask admin portal
│   ├── templates/              # HTML pages
│   ├── static/styles.css
│
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

## 🔒 Security

- Keep `.env` out of version control
- Use `.gitignore` to exclude secrets:

```gitignore
.env
*.pyc
__pycache__/
postgres-data/
```

---

## 📜 License

MIT  
Made with ☕ by [@NARobz](https://github.com/NARobz/scumbot1.0)

---

## 📦 To Do

- Admin login system  
- Webhooks for command relay  
- Balance top-ups via discord 
- Item usage tracking  
- Permission roles for staff


## New Features (Aug 2025)

📜 New Features (Aug 2025)

Bank UI Register Button – Register SCUM username via Discord modal

Purchase History Button – View last 10 purchases in Discord

Taxi Management – Add/edit/delete taxis via admin panel

Taxi Buttons in Discord – Players can order taxis directly

Delivery Bot Integration – Fulfills both item and taxi orders automatically

Bot Status Updates – Updates a single status message instead of spamming

Auto-Refresh Channels – Shop, bank, and taxi channels cleaned & repopulated on startup

- **Register Button in Bank UI**  
  Players can now link their SCUM in-game name with their Discord account directly from the bank channel using a button.  
  A modal will appear to enter the SCUM name, which uses the existing `/register` logic in the admin web portal.

- **Purchase History Button**  
  Players can now view their last 10 purchases directly in Discord via the bank UI.  
  Each entry shows the item name, quantity, and purchase date.  
  The `orders` table now stores a `created_at` timestamp for all new orders.

### Database Update
  Ensure the `orders` table has a `created_at` column:
  ```sql
  ALTER TABLE orders
  ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

  🚀 Recent Updates
  Bot Status Updates
  The bot now posts its online/offline status to the channel specified by BOT_STATUS_CHANNEL_ID in your .env file.

  Instead of posting a new message each time, it edits the last bot status message to avoid clutter.

  Auto-Refresh Shop & Bank on Startup
  If AUTO_REFRESH_ON_STARTUP=true in .env, the bot will automatically:

  Purge non-pinned messages from bot-shop and bot-bank channels.

  Repost all shop items from the database.

  Re-add the bank action buttons.

  This ensures the shop and bank channels are always clean and up to date after restarts.

  Improved Delivery Logs
  Purchases now log to the delivery channel (BOT_SHOP_DELIVERY_CHANNEL_ID) with clean, copy-paste-ready spawn commands.

  Future-proofed for possible teleport + spawn bot automation.

  .env Variables for New Features
    BOT_STATUS_CHANNEL_ID=123456789012345678
    AUTO_REFRESH_ON_STARTUP=true