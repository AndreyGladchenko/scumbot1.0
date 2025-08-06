# 🛒 SCUM Discord Bot Shop System

A full-stack, self-hosted shop system for SCUM game servers. Players buy items via Discord using buttons or slash commands. Admins manage everything via a web portal.

---

## ✨ Features

- 🛒 Buy items via Discord (slash commands + buttons)
- 🔐 Admin-only web interface
- 💾 PostgreSQL database
- 📦 JSON import/export of shop items
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

```env
# Discord bot token (keep secret!)
DISCORD_TOKEN=

# PostgreSQL settings
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=

# Optional: full database URL (used by Flask)
DATABASE_URL=

# Discord guild (server) ID
DISCORD_GUILD_ID=

# Channel IDs (from your Discord server)
LOG_CHANNEL_ID=                 # Admin log channel (e.g. bot-shop-admin)
SHOP_LOG_CHANNEL_ID=           # Where shop items with buttons are posted
PURCHASE_LOG_CHANNEL_ID=       # Where purchases are logged

# Webhook (optional - used for posting embeds via webhook, not bot)
DISCORD_WEBHOOK_URL=

# Where spawn commands are stored (future automation)
COMMAND_RELAY_FILE=/app/outgoing_commands.txt

# Admin-only role name for slash command protection
ADMIN_ROLE_NAME=Admin

# Flask API
FLASK_SECRET_KEY=randomstring
BOT_API_URL=http://discord-bot:3000
```

---

## 🧾 Slash Commands

Use inside your Discord server:

- `/register <scum_username>` – Link your Discord to your SCUM name  
- `/buy <item_name> [quantity]` – Buy an item  
- `/send_shop_items` – Admin only: Post all shop items with buttons

---

## 🛍 Buy Buttons

When shop items are posted, a "🛒 Buy" button appears.

- Clicking it:
  - Checks user balance
  - Deducts cost
  - Logs order
  - Sends spawn commands to delivery channel

---

## 🛠 Admin Panel

Open your browser to: [http://localhost:5000](http://localhost:5000)

From there you can:

- ✅ Add/edit/delete shop items  
- 👤 Manage players  
- 📜 View order history  
- 📥 Import/export JSON  
- 📬 Trigger posting items to Discord

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
