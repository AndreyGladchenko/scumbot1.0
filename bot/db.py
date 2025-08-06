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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    discord_id BIGINT UNIQUE NOT NULL,
                    scum_username TEXT,
                    balance INTEGER DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS shop_items (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT,
                    price NUMERIC NOT NULL,
                    image_url TEXT
                )
            """)

        conn.commit()
        
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
                SELECT o.id, si.name, si.category, si.price, o.quantity, o.timestamp, p.discord_username
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
                }
                for row in cur.fetchall()
            ]
        
def save_order_to_db(player_id, item_id, quantity):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO orders (player_id, item_id, quantity)
                VALUES (%s, %s, %s)
            """, (player_id, item_id, quantity))
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
