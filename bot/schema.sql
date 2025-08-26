-- schema.sql — SCUM Bot Shop System (updated for JSON/plain text content support)

-- Players table
CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT UNIQUE NOT NULL,
    scum_username TEXT NOT NULL,
    discord_username TEXT NOT NULL,
    balance NUMERIC(10, 2) DEFAULT 0 NOT NULL
);

-- Shop items table
CREATE TABLE IF NOT EXISTS shop_items (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'Misc',
    price NUMERIC(10, 2) NOT NULL,
    content TEXT DEFAULT '', -- Can hold plain text OR JSON
    image_url TEXT DEFAULT NULL,
    message_id TEXT DEFAULT NULL,
    channel_id TEXT DEFAULT NULL
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    player_id INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    item_id INT NOT NULL REFERENCES shop_items(id) ON DELETE CASCADE,
    quantity INT NOT NULL DEFAULT 1,
    total_price NUMERIC(10, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending'   -- ✅ new column
);

-- Auto calculate total_price when inserting orders (if not supplied)
CREATE OR REPLACE FUNCTION set_total_price()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.total_price = 0 OR NEW.total_price IS NULL THEN
        SELECT price * NEW.quantity INTO NEW.total_price
        FROM shop_items
        WHERE id = NEW.item_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_total_price ON orders;
CREATE TRIGGER trg_set_total_price
BEFORE INSERT ON orders
FOR EACH ROW
EXECUTE FUNCTION set_total_price();

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_players_discord_id ON players(discord_id);
CREATE INDEX IF NOT EXISTS idx_shop_items_name ON shop_items(name);
CREATE INDEX IF NOT EXISTS idx_orders_player_id ON orders(player_id);
CREATE INDEX IF NOT EXISTS idx_orders_item_id ON orders(item_id);
