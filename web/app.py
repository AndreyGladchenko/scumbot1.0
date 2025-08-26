# flask app main file for admin portal: app.py

import sys
import os
import json
import io
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../bot')))

from flask import Flask, render_template, redirect, request, url_for, send_file, flash
from psycopg2 import errors
from bot import db
from decimal import Decimal

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")
db.init()


# ─────────────────────────────────────────────────────────────
# 🔄 Function to POST a new item to Discord bot
# ─────────────────────────────────────────────────────────────

def send_item_to_discord(item):
    bot_api_url = os.getenv("BOT_API_URL", "http://discord-bot:3000/api/post_item")

    try:
        print(f"📤 DEBUG: Sending to bot at {bot_api_url}")
        
        # Fix Decimal serialization
        item_serializable = item.copy()
        if isinstance(item_serializable.get("price"), Decimal):
            item_serializable["price"] = int(item_serializable["price"])

        print(f"📦 Payload: {json.dumps(item_serializable, indent=2)}")
        
        # ✅ Send the fixed version only
        response = requests.post(bot_api_url, json=item_serializable, timeout=5)

        print(f"✅ Response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Exception posting to bot: {e}")



# ─────────────────────────────────────────────────────────────
# 🏠 Home page
# ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ─────────────────────────────────────────────────────────────
# 🛒 Shop Items
# ─────────────────────────────────────────────────────────────

@app.route('/items')
def items():
    shop_items = db.get_shop_items()
    return render_template('items.html', items=shop_items)


@app.route('/items/create', methods=['GET', 'POST'])
def create_item():
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        try:
            price = int(float(request.form['price']))  # round and remove decimals
        except ValueError:
            flash("❌ Invalid price format", "error")
            return redirect(request.url)

        image_url = request.form.get('image_url', '')
        description = request.form.get('description', '')
        content_raw = request.form.get('content', '')
        content = [line.strip() for line in content_raw.strip().splitlines() if line.strip()]

        try:
            db.add_shop_item(name, category, price, image_url, description, content)
        except Exception as e:
            flash(f"❌ Failed to add item to DB: {e}", "error")
            return redirect(request.url)

        # ✅ Fetch full item (including ID)
        new_item = db.get_shop_item_by_name(name)
        if not new_item:
            flash("❌ Failed to retrieve item after insert", "error")
            return redirect(url_for('items'))

        # ✅ Send to Discord
        try:
            new_item["content"] = content
            print(f"📣 About to send item to Discord: {new_item['name']}")
            send_item_to_discord(new_item)
            flash("✅ Item added and posted to Discord!", "success")
        except Exception as e:
            flash(f"⚠️ Item added to DB, but failed to post to Discord: {e}", "warning")

        return redirect(url_for('items'))

    return render_template('create_item.html')


@app.route('/items/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    item = db.get_shop_item_by_id(item_id)
    if not item:
        return "Item not found", 404

    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        price = float(request.form['price'])
        description = request.form.get('description')
        content_raw = request.form.get('content')
        content = [line.strip() for line in content_raw.strip().split('\n') if line.strip()]
        image_url = request.form['image_url']

        db.update_shop_item(item_id, name, category, price, image_url, description, content)
        return redirect(url_for('items'))

    return render_template('edit_item.html', item=item)


@app.route('/items/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    try:
        db.delete_shop_item(item_id)
        return redirect(url_for('items'))
    except errors.ForeignKeyViolation:
        return redirect(url_for('confirm_delete_item', item_id=item_id))


@app.route('/items/delete_confirm/<int:item_id>')
def confirm_delete_item(item_id):
    item = db.get_shop_item_by_id(item_id)
    return render_template('confirm_delete_item.html', item=item)


@app.route('/items/delete_force/<int:item_id>', methods=['POST'])
def force_delete_item(item_id):
    db.delete_orders_by_item_id(item_id)
    db.delete_shop_item(item_id)
    return redirect(url_for('items'))


@app.route('/items/export')
def export_items():
    items = db.export_shop_items()
    buffer = io.BytesIO()
    buffer.write(json.dumps(items, indent=2).encode('utf-8'))
    buffer.seek(0)
    return send_file(buffer, mimetype='application/json', as_attachment=True, download_name='shop_items_backup.json')


@app.route('/items/import', methods=['GET', 'POST'])
def import_items():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part", "error")
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash("No selected file", "error")
            return redirect(request.url)
        data = json.load(file)
        db.import_shop_items(data)
        flash("✅ Items imported successfully", "success")
        return redirect(url_for('items'))

    return render_template('import_items.html')


# ─────────────────────────────────────────────────────────────
# 👤 Player Management
# ─────────────────────────────────────────────────────────────

@app.route('/players')
def players():
    all_players = db.get_all_players()
    return render_template('players.html', players=all_players)


@app.route('/players/create', methods=['GET', 'POST'])
def create_player():
    if request.method == 'POST':
        discord_id = request.form['discord_id']
        scum_username = request.form['scum_username']
        db.get_or_create_player(discord_id, scum_username)
        return redirect(url_for('players'))
    return render_template('create_player.html')


@app.route('/players/edit/<string:discord_id>', methods=['GET', 'POST'])
def edit_player(discord_id):
    all_players = db.get_all_players()
    player = next((p for p in all_players if str(p['discord_id']) == discord_id), None)

    if not player:
        return "Player not found", 404

    if request.method == 'POST':
        new_username = request.form['scum_username']
        new_balance = request.form['balance']

        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE players
                    SET scum_username = %s, balance = %s
                    WHERE discord_id = %s
                """, (new_username, new_balance, discord_id))
                conn.commit()

        return redirect(url_for('players'))

    return render_template('edit_player.html', player=player)


@app.route('/players/<string:discord_id>/orders')
def player_orders(discord_id):
    orders = db.get_orders_by_player(discord_id)
    discord_username = orders[0]["discord_username"] if orders else "Unknown"
    return render_template(
        'player_orders.html',
        orders=orders,
        discord_id=discord_id,
        discord_username=discord_username
    )


@app.route('/players/delete/<string:discord_id>', methods=['POST'])
def delete_player(discord_id):
    try:
        db.remove_player(discord_id)
        return redirect(url_for('players'))
    except errors.ForeignKeyViolation:
        return redirect(url_for('confirm_delete_player', discord_id=discord_id))


@app.route('/players/delete_confirm/<string:discord_id>')
def confirm_delete_player(discord_id):
    return render_template('confirm_delete.html', discord_id=discord_id)


@app.route('/players/delete_force/<string:discord_id>', methods=['POST'])
def force_delete_player(discord_id):
    db.delete_orders_by_discord_id(discord_id)
    db.remove_player(discord_id)
    return redirect(url_for('players'))

@app.route('/orders/<int:order_id>/status', methods=['POST'])
def update_order_status_route(order_id):
    new_status = request.form.get("status")
    if new_status:
        db.update_order_status(order_id, new_status)
        flash(f"Order {order_id} marked as {new_status}", "success")
    return redirect(request.referrer or url_for("players"))

# ─────────────────────────────────────────────────────────────
# 🚖 Taxis (Admin)
# ─────────────────────────────────────────────────────────────

from psycopg2.extras import RealDictCursor

@app.route('/taxis')
def taxis():
    with db.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM taxis ORDER BY id;")
            taxis = cur.fetchall()
    return render_template('taxis.html', taxis=taxis)

@app.route('/taxis/create', methods=['GET', 'POST'])
def taxis_create():
    if request.method == 'POST':
        name = request.form['name'].strip()
        price = int(float(request.form['price']))
        # one coord per line; accepts "X=.. Y=.. Z=.." or "x y z"
        raw = request.form.get('coordinates','').strip().splitlines()
        coords = []
        for line in raw:
            s = line.strip()
            if not s: 
                continue
            if "=" in s:
                coords.append(s)
            else:
                parts = [p for p in s.replace(",", " ").split() if p]
                if len(parts) != 3:
                    flash(f"Bad coord line: {s}", "error")
                    return redirect(request.url)
                coords.append(f"X={parts[0]} Y={parts[1]} Z={parts[2]}")

        with db.get_connection() as conn:
            taxi_id = db.create_taxi(conn, name, price, coords)
            conn.commit()

        flash(f"✅ Taxi '{name}' created (id {taxi_id})", "success")
        return redirect(url_for('taxis'))

    return render_template('taxis_create.html')

@app.route('/taxis/edit/<int:taxi_id>', methods=['GET', 'POST'])
def taxis_edit(taxi_id):
    # fetch current taxi
    with db.get_connection() as conn:
        taxi = db.get_taxi_by_id(conn, taxi_id)
    if not taxi:
        flash("❌ Taxi not found.", "error")
        return redirect(url_for('taxis'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        price = int(float(request.form['price']))
        raw = request.form.get('coordinates', '').strip().splitlines()

        coords = []
        for line in raw:
            s = line.strip()
            if not s:
                continue
            if "=" in s:
                coords.append(s)
            else:
                parts = [p for p in s.replace(",", " ").split() if p]
                if len(parts) != 3:
                    flash(f"❌ Bad coord line: {s}", "error")
                    return redirect(request.url)
                coords.append(f"X={parts[0]} Y={parts[1]} Z={parts[2]}")

        with db.get_connection() as conn:
            db.update_taxi(conn, taxi_id, name, price, coords)
            conn.commit()

        flash("✅ Taxi updated.", "success")
        return redirect(url_for('taxis'))

    # GET -> show form with existing values
    # ensure coordinates render as newline-separated strings
    coords_list = taxi.get("coordinates") or []
    if isinstance(coords_list, str):
        try:
            coords_list = json.loads(coords_list)
        except Exception:
            coords_list = [coords_list]
    coords_text = "\n".join(coords_list)

    return render_template('taxis_edit.html', taxi=taxi, coords_text=coords_text)

@app.route('/taxis/<int:taxi_id>/delete', methods=['POST'])
def taxis_delete(taxi_id):
    with db.get_connection() as conn:
        db.delete_taxi(conn, taxi_id)
        conn.commit()
    flash("Taxi deleted", "success")
    return redirect(url_for('taxis'))

def _print_routes_once():
    try:
        with app.app_context():
            print("🌐 Registered routes:")
            for r in app.url_map.iter_rules():
                methods = ",".join(sorted(r.methods - {"HEAD", "OPTIONS"}))
                print(f"  {r.rule:30s} -> {methods}")
    except Exception as e:
        print("Failed to print routes:", e)



# ─────────────────────────────────────────────────────────────
# ✅ Flask entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _print_routes_once()
    app.run(host="0.0.0.0", port=5000, debug=True)

