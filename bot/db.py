#databse logic for scumbot db.py
#this file contains all the database logic for the bot, including player management, shop items,
#and orders. It uses psycopg2 to connect to a PostgreSQL database.

import psycopg2
import psycopg2.extras
import os
import json
from psycopg2.extras import RealDictCursor

DB_URL = os.getenv("DATABASE_URL")

def get_connection():
    print("Connecting to:", DB_URL)

    return psycopg2.connect(DB_URL)

def init():
    with get_connection() as conn:
        with conn.cursor() as cur:
            # ─── Players table ───────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    discord_id BIGINT UNIQUE NOT NULL,
                    scum_username TEXT,
                    balance INTEGER DEFAULT 0
                );
            """)
            cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS discord_username TEXT;")

            # ─── Shop Items table ────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS shop_items (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT,
                    price NUMERIC NOT NULL,
                    image_url TEXT
                );
            """)
            cur.execute("ALTER TABLE shop_items ADD COLUMN IF NOT EXISTS description TEXT;")
            cur.execute("ALTER TABLE shop_items ADD COLUMN IF NOT EXISTS content TEXT;")
            cur.execute("ALTER TABLE shop_items ADD COLUMN IF NOT EXISTS message_id TEXT;")
            cur.execute("ALTER TABLE shop_items ADD COLUMN IF NOT EXISTS channel_id TEXT;")

            # ─── Orders table ────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    item_id INTEGER NOT NULL REFERENCES shop_items(id) ON DELETE CASCADE,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    total_price NUMERIC NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                );
            """)
            cur.execute("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'
            """)

            # ─── Audit Logs table ────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    admin_id BIGINT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # ─── Settings table ──────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)

            # ─── Taxis table ─────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS taxis (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    price NUMERIC(10,2) NOT NULL,
                    coordinates JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # ─── Taxi Orders table ───────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS taxi_orders (
                    id SERIAL PRIMARY KEY,
                    player_id INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    taxi_id INT NOT NULL REFERENCES taxis(id) ON DELETE CASCADE,
                    chosen_coordinate TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );
            """)

            # ─── Helpful indexes ─────────────────────────────
            cur.execute("CREATE INDEX IF NOT EXISTS idx_taxi_orders_player_id ON taxi_orders(player_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_taxi_orders_taxi_id ON taxi_orders(taxi_id);")

        conn.commit()
    print("✅ Database schema checked/updated (players, shop, orders, taxis)")



        
def get_all_players():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT discord_id, scum_username, balance, discord_username FROM players")
            return [
                {
                    "discord_id": row[0],
                    "scum_username": row[1],
                    "balance": row[2],
                    "discord_username": row[3]
                }
                for row in cur.fetchall()
            ]


def get_or_create_player(discord_id, scum_username, discord_username=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM players WHERE discord_id = %s", (discord_id,))
            result = cur.fetchone()
            if result:
                # Optional: Update discord_username if it changed
                if discord_username:
                    cur.execute("UPDATE players SET discord_username = %s WHERE discord_id = %s", (discord_username, discord_id))
                    conn.commit()
                return result[0]
            else:
                cur.execute(
                    "INSERT INTO players (discord_id, scum_username, discord_username) VALUES (%s, %s, %s) RETURNING id",
                    (discord_id, scum_username, discord_username)
                )
                conn.commit()
                return cur.fetchone()[0]


def get_player_by_discord_id(discord_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT discord_id, scum_username, balance, discord_username FROM players WHERE discord_id = %s", (discord_id,))
            row = cur.fetchone()
            if row:
                return {
                    "discord_id": row[0],
                    "scum_username": row[1],
                    "balance": row[2],
                    "discord_username": row[3]
                }
            return None

        
def remove_player(discord_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM players WHERE discord_id = %s", (discord_id,))

def delete_orders_by_discord_id(discord_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Get internal player_id from discord_id
            cur.execute("SELECT id FROM players WHERE discord_id = %s", (discord_id,))
            result = cur.fetchone()
            if result:
                player_id = result[0]
                cur.execute("DELETE FROM orders WHERE player_id = %s", (player_id,))
                conn.commit()


def get_balance(player_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM players WHERE id = %s", (player_id,))
            return cur.fetchone()[0]

def update_balance(player_id, amount):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE players SET balance = balance + %s WHERE id = %s", (amount, player_id))
            conn.commit()

def update_player(discord_id, scum_username, balance):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE players
                SET scum_username = %s, balance = %s
                WHERE discord_id = %s
            """, (scum_username, balance, discord_id))
            conn.commit()

# bank view helper functions
def get_balance_by_discord_id(discord_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM players WHERE discord_id = %s", (discord_id,))
            result = cur.fetchone()
            return result[0] if result else 0

def update_balance_by_discord_id(discord_id, amount):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE players SET balance = balance + %s WHERE discord_id = %s", (amount, discord_id,))

def get_order_history_by_discord_id(discord_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT i.name, o.quantity, o.timestamp
                FROM orders o
                JOIN players p ON o.player_id = p.id
                JOIN shop_items i ON o.item_id = i.id
                WHERE p.discord_id = %s
                ORDER BY o.timestamp DESC
                LIMIT 10
            """, (discord_id,))
            return [
                {"item_name": row[0], "quantity": row[1], "created_at": row[2]}
                for row in cur.fetchall()
            ]



import json

def get_shop_items():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, category, price, image_url, description, content
                FROM shop_items
                ORDER BY name ASC
            """)
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "category": row[2],
                    "price": row[3],
                    "image_url": row[4],
                    "description": row[5],
                    # Parse JSON string into Python list
                    "content": json.loads(row[6]) if isinstance(row[6], str) else row[6],
                }
                for row in cur.fetchall()
            ]


def get_shop_item_by_id(item_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, category, price, image_url, description, content
                FROM shop_items
                WHERE id = %s
            """, (item_id,))
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "category": row[2],
                    "price": row[3],
                    "image_url": row[4],
                    "description": row[5],
                    "content": row[6],
                }
            return None

def get_shop_item_by_name(name):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM shop_items WHERE name = %s", (name,))
            return cur.fetchone()


def add_shop_item(name, category, price, image_url, description, content):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO shop_items (name, category, price, image_url, description, content)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, category, price, image_url, description, json.dumps(content)))
            conn.commit()


def update_shop_item(item_id, name, category, price, image_url, description, content):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE shop_items
                SET name = %s, category = %s, price = %s,
                    image_url = %s, description = %s, content = %s
                WHERE id = %s
            """, (name, category, price, image_url, description, json.dumps(content), item_id))
            conn.commit()


def delete_shop_item(item_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shop_items WHERE id = %s", (item_id,))
            conn.commit()

def set_item_price(name, price):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE shop_items SET price = %s WHERE LOWER(name) = LOWER(%s)", (price, name))
            conn.commit()

def remove_shop_item(name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shop_items WHERE LOWER(name) = LOWER(%s)", (name,))
            conn.commit()

def delete_orders_by_item_id(item_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM orders WHERE item_id = %s", (item_id,))
            conn.commit()

def edit_shop_item(old_name, new_name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE shop_items SET name = %s WHERE LOWER(name) = LOWER(%s)", (new_name, old_name))
            conn.commit()

def import_shop_items(items):
    with get_connection() as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute("""
                    INSERT INTO shop_items (name, price, category, image_url)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE 
                    SET price = EXCLUDED.price,
                        category = EXCLUDED.category,
                        image_url = EXCLUDED.image_url
                """, (item["name"], item["price"], item.get("category", "Misc"), item.get("image_url")))
            conn.commit()

def export_shop_items():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, price, category, image_url FROM shop_items ORDER BY name ASC")
            return [
                {
                    "name": row[0],
                    "price": row[1],
                    "category": row[2],
                    "image_url": row[3]
                } for row in cur.fetchall()
            ]

        
def get_orders_by_player(discord_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT o.id, si.name, si.category, si.price, o.quantity, o.timestamp, p.discord_username, o.status
                FROM orders o
                JOIN players p ON o.player_id = p.id
                JOIN shop_items si ON o.item_id = si.id
                WHERE p.discord_id = %s
                ORDER BY o.timestamp DESC
            """, (discord_id,))
            return [
                {
                    "order_id": row[0],
                    "item_name": row[1],
                    "category": row[2],
                    "price": row[3],
                    "quantity": row[4],
                    "timestamp": row[5],
                    "discord_username": row[6],
                    "status": row[7],   # ✅ new field
                }
                for row in cur.fetchall()
            ]
        
def save_order_to_db(player_id, item_id, quantity):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Get price from the shop_items table
            cur.execute("SELECT price FROM shop_items WHERE id = %s", (item_id,))
            result = cur.fetchone()
            if not result:
                raise ValueError("Item not found")
            price = result[0]

            # Calculate total
            total_price = price * quantity

            cur.execute("""
                INSERT INTO orders (player_id, item_id, quantity, total_price, status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (player_id, item_id, quantity, total_price, "pending"))
            order_id = cur.fetchone()[0]

        conn.commit()
        return order_id

def update_order_status(order_id, new_status):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id))
            conn.commit()


# Save message/channel ID to a shop item
def update_shop_item_message_info(item_id, message_id, channel_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE shop_items
                SET message_id = %s, channel_id = %s
                WHERE id = %s
            """, (message_id, channel_id, item_id))
            conn.commit()

# Get full shop item with message/channel ID
def get_shop_item_with_message(item_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, category, price, image_url, description, content, message_id, channel_id
                FROM shop_items
                WHERE id = %s
            """, (item_id,))
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "category": row[2],
                    "price": row[3],
                    "image_url": row[4],
                    "description": row[5],
                    "content": row[6],
                    "message_id": row[7],
                    "channel_id": row[8]
                }
            return None
# ===============================
# Taxi System Database Functions
# ===============================
import json
from psycopg2.extras import RealDictCursor

def get_all_taxis(conn):
    """Fetch all taxis."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM taxis ORDER BY id;")
        return cur.fetchall()

def get_taxi_by_id(conn, taxi_id):
    """Fetch a taxi by ID."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM taxis WHERE id=%s;", (taxi_id,))
        return cur.fetchone()

def create_taxi(conn, name, price, coordinates):
    """
    Create a new taxi.
    coordinates must be a list of coordinate strings.
    """
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO taxis (name, price, coordinates) VALUES (%s, %s, %s) RETURNING id;",
            (name, price, json.dumps(coordinates))
        )
        return cur.fetchone()[0]

def update_taxi(conn, taxi_id, name, price, coordinates):
    """Update a taxi's name, price and coordinates (list of strings)."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE taxis
               SET name = %s,
                   price = %s,
                   coordinates = %s
             WHERE id = %s
        """, (name, price, json.dumps(coordinates), taxi_id))

def delete_taxi(conn, taxi_id):
    """Delete a taxi."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM taxis WHERE id=%s;", (taxi_id,))

def create_taxi_order(conn, player_id, taxi_id, chosen_coordinate=None):
    """Create a taxi order for a player."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO taxi_orders (player_id, taxi_id, chosen_coordinate) VALUES (%s, %s, %s) RETURNING id;",
            (player_id, taxi_id, chosen_coordinate)
        )
        return cur.fetchone()[0]

def fetch_pending_taxi_orders(conn):
    """Fetch all pending taxi orders with taxi details."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT o.*, 
                   t.name AS taxi_name, 
                   t.price AS taxi_price,
                   t.coordinates,
                   p.scum_username AS player_name,
                   p.discord_id AS player_discord_id
            FROM taxi_orders o
            JOIN taxis t ON o.taxi_id = t.id
            JOIN players p ON o.player_id = p.id
            WHERE o.status = 'pending'
            ORDER BY o.created_at ASC;
        """)
        return cur.fetchall()

def mark_taxi_order_status(conn, order_id, status):
    """Update taxi order status (completed/failed)."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE taxi_orders SET status=%s, completed_at=NOW() WHERE id=%s;",
            (status, order_id)
        )
