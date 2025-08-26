###############################################################################
### SCUM Delivery Bot #########################################################
### Automates deliveries using admin drone mode ###############################
###############################################################################

import os
import time
import json
import subprocess
import psutil
import psycopg2
import psycopg2.extras
import pyautogui
import pyperclip
import random
from dotenv import load_dotenv

# Optional: disable pyautogui fail-safe (corner of screen abort)
# pyautogui.FAILSAFE = False

# Load environment variables from .env
load_dotenv()

# 🔐 Database
DATABASE_URL = os.getenv("DATABASE_URL")

# 🎮 Game paths & settings
STEAM_PATH = os.getenv("STEAM_PATH")  # e.g. C:\\Steam\\steam.exe
SCUM_APP_ID = int(os.getenv("SCUM_APP_ID", "513710"))  # default 513710 if missing
GAME_CLIENT_PATH = os.getenv("GAME_CLIENT_PATH")  # optional if you need direct exe

# 📍 Staging teleport coordinates
STAGING_COORDS = os.getenv("STAGING_COORDS")  # e.g. "X=2922.660 Y=-58764.000 Z=21160.820"

# Screen size (used if needed for clicks)
SCREEN_WIDTH = int(os.getenv("SCREEN_WIDTH", "1280"))
SCREEN_HEIGHT = int(os.getenv("SCREEN_HEIGHT", "720"))

###############################################################################
# Database functions
###############################################################################

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def fetch_pending_orders():
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT o.id, p.scum_username, si.content
                FROM orders o
                JOIN players p ON o.player_id = p.id
                JOIN shop_items si ON o.item_id = si.id
                WHERE o.status IS NULL OR o.status = 'pending'
                ORDER BY o.timestamp ASC
                LIMIT 5
            """)
            return cur.fetchall()

def mark_order_delivered(order_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orders SET status = 'delivered' WHERE id = %s", (order_id,))
            conn.commit()

def fetch_pending_taxi_orders():
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT o.id,
                       p.scum_username AS player_name,
                       o.chosen_coordinate,
                       t.coordinates
                FROM taxi_orders o
                JOIN players p ON o.player_id = p.id
                JOIN taxis   t ON o.taxi_id = t.id
                WHERE o.status = 'pending'
                ORDER BY o.created_at ASC
                LIMIT 5
            """)
            return cur.fetchall()

def mark_taxi_delivered(order_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE taxi_orders SET status = 'delivered', completed_at = CURRENT_TIMESTAMP WHERE id = %s",
                (order_id,)
            )
            conn.commit()


###############################################################################
# Game automation helpers
###############################################################################

def launch_scum_if_needed():
    for proc in psutil.process_iter(attrs=['name']):
        if proc.info['name'] and "SCUM.exe" in proc.info['name']:
            print("🎮 SCUM is already running.")
            return

    print("🚀 Launching SCUM...")
    pyautogui.moveTo(400, 400)  # move mouse away from (0,0)
    subprocess.Popen([STEAM_PATH, "-applaunch", str(SCUM_APP_ID)])
    print("⏳ Waiting for SCUM to reach menu...")
    time.sleep(60)  # give plenty of time for SCUM to load fully

import pygetwindow as gw

def focus_and_position_scum():
    """Bring SCUM window to front and move it to top-left corner."""
    time.sleep(5)  # give Windows time to register window
    try:
        scum_windows = [w for w in gw.getWindowsWithTitle("SCUM") if w]
        if scum_windows:
            win = scum_windows[0]
            win.activate()
            time.sleep(1)
            win.moveTo(0, 0)   # 🔥 top-left of screen
            win.resizeTo(SCREEN_WIDTH, SCREEN_HEIGHT)  # match .env values
            print("🪟 SCUM window focused and repositioned (top-left).")
        else:
            print("⚠️ Could not find SCUM window.")
    except Exception as e:
        print(f"⚠️ Window management failed: {e}")


def skip_intro():
    """Skip SCUM intro cutscene."""
    print("⏭ Waiting for intro / cutscene...")
    time.sleep(30)  # wait for cutscene to actually appear

    print("⏭ Attempting to skip intro...")
    pyautogui.FAILSAFE = False  # disable during risky keypress
    pyautogui.press("space")
    pyautogui.FAILSAFE = True   # immediately back on

    time.sleep(5)


def enter_drone_mode():
    """Enter drone mode and click Continue."""
    print("🛸 Entering Drone Mode...")
    pyautogui.FAILSAFE = False
    pyautogui.hotkey("ctrl", "d")   # risky, disable failsafe
    #time.sleep(10)
    pyautogui.click(100, 430)       # Continue button
    pyautogui.FAILSAFE = True       # back on again

    print("⏳ Loading into world...")
    time.sleep(60)

def ensure_invisibility():
    """Press 3 to ensure invisibility."""
    print("👻 Ensuring drone invisibility...")
    pyautogui.press("3")
    time.sleep(5)

###############################################################################
# Command helper (clipboard method, fixes UK keyboard issues)
###############################################################################

def send_command(command: str):
    """
    Sends a SCUM admin command reliably by pasting from clipboard.
    Ensures the leading '#' is always present.
    """
    # Always prepend '#'
    full_command = f"#{command.lstrip('#')}"
    pyperclip.copy(full_command)

    # Paste and send
    pyautogui.hotkey("ctrl", "v")
    pyautogui.press("enter")
    time.sleep(3)

# coordinate parsing/format helpers

def _normalize_coordinates(coords_json):
    """
    coords_json is taxis.coordinates (JSONB). Accepts:
      - list of strings: ["X=1 Y=2 Z=3", ...]
      - list of [x,y,z]
      - list of {"X":1,"Y":2,"Z":3}
    Returns a list of strings formatted 'X=... Y=... Z=...'.
    """
    if isinstance(coords_json, str):
        try:
            coords_json = json.loads(coords_json)
        except Exception:
            coords_json = [coords_json]

    norm = []
    for c in coords_json or []:
        if isinstance(c, str):
            # assume already in SCUM format
            norm.append(c.strip())
        elif isinstance(c, (list, tuple)) and len(c) == 3:
            x, y, z = c
            norm.append(f"X={x} Y={y} Z={z}")
        elif isinstance(c, dict):
            x = c.get("X") or c.get("x")
            y = c.get("Y") or c.get("y")
            z = c.get("Z") or c.get("z")
            if x is not None and y is not None and z is not None:
                norm.append(f"X={x} Y={y} Z={z}")
    return norm

def _format_single_coord(chosen):
    """Accepts TEXT from taxi_orders.chosen_coordinate or a parsed value; returns 'X=.. Y=.. Z=..'."""
    if not chosen:
        return None
    if isinstance(chosen, str):
        # Already 'X=.. Y=.. Z=..' or 'x y z'
        s = chosen.strip()
        if "=" in s:
            return s
        parts = [p for p in s.replace(",", " ").split() if p]
        if len(parts) == 3:
            return f"X={parts[0]} Y={parts[1]} Z={parts[2]}"
        return s
    if isinstance(chosen, (list, tuple)) and len(chosen) == 3:
        return f"X={chosen[0]} Y={chosen[1]} Z={chosen[2]}"
    if isinstance(chosen, dict):
        x = chosen.get("X") or chosen.get("x")
        y = chosen.get("Y") or chosen.get("y")
        z = chosen.get("Z") or chosen.get("z")
        if x is not None and y is not None and z is not None:
            return f"X={x} Y={y} Z={z}"
    return None


###############################################################################
# Delivery logic
###############################################################################

def teleport_to_staging():
    """Teleport drone back to staging area."""
    print(f"📍 Returning to staging area {STAGING_COORDS}...")
    send_command(f"teleport {STAGING_COORDS}")
    time.sleep(5)

def generate_spawn_commands(content):
    """Parse shop_items.content as JSON list or plain string."""
    commands = []
    try:
        parsed = json.loads(content) if content else []
        if isinstance(parsed, list):
            commands.extend(parsed)
        elif isinstance(parsed, str):
            commands.append(parsed)
    except (json.JSONDecodeError, TypeError):
        if content:
            commands.append(content)
    return commands

def deliver_order(order):
    """Teleport to player and issue spawn commands."""
    username = order["scum_username"]
    content = order["content"]
    commands = generate_spawn_commands(content)

    print(f"📦 Delivering order {order['id']} to {username}...")

    # teleport to player
    send_command(f"teleportto {username}")
    time.sleep(5)

    # spawn items
    for cmd in commands:
        send_command(cmd)

    # mark as delivered
    mark_order_delivered(order["id"])
    print(f"✅ Order {order['id']} delivered.")

def deliver_taxi_order(order):
    """
    order: { id, player_name, chosen_coordinate, coordinates }
    Steps:
      - pick a random coordinate (unless chosen_coordinate set)
      - teleport there
      - teleporttome player
      - mark delivered
    """
    username = order["player_name"]
    coords_all = _normalize_coordinates(order.get("coordinates"))
    if not coords_all:
        print(f"❌ Taxi order {order['id']} has no coordinates configured.")
        # Mark failed instead of delivered
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE taxi_orders SET status='failed', error='No coordinates' WHERE id=%s", (order["id"],))
                conn.commit()
        return

    chosen = _format_single_coord(order.get("chosen_coordinate")) or random.choice(coords_all)

    print(f"🚕 Taxi order {order['id']} → {username} to {chosen}")

    # 1) Drone to destination coord
    send_command(f"teleport {chosen}")
    time.sleep(3)

    # 2) Pull the player to taxi
    send_command(f"teleporttome {username}")
    time.sleep(5)

    # 3) Mark delivered
    mark_taxi_delivered(order["id"])
    print(f"✅ Taxi order {order['id']} delivered.")


###############################################################################
# Main Loop
###############################################################################

def main_loop():
    launch_scum_if_needed()
    focus_and_position_scum()
    skip_intro()
    enter_drone_mode()
    ensure_invisibility()
    teleport_to_staging()

    # Open chat once at the start of session
    pyautogui.press("t")
    time.sleep(3)

    print("🚀 Delivery bot is active and checking for orders...")

    while True:
        orders = fetch_pending_orders()
        taxi_orders = fetch_pending_taxi_orders()

        if orders or taxi_orders:
            # Shop item deliveries first
            for order in orders:
                deliver_order(order)

            # Then taxi rides
            for torder in taxi_orders:
                deliver_taxi_order(torder)

            # Return to staging after work
            teleport_to_staging()
        else:
            print("⏳ No pending orders. Waiting...")

        time.sleep(10)

if __name__ == "__main__":
    main_loop()
