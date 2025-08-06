-- Table for linking Discord users to SCUM usernames
CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT UNIQUE NOT NULL,
    scum_username TEXT NOT NULL
);

-- Table for storing player balances
CREATE TABLE IF NOT EXISTS bank_accounts (
    id SERIAL PRIMARY KEY,
    player_id INT NOT NULL REFERENCES players(id),
    balance INT NOT NULL DEFAULT 0
);

-- Shop item catalog (optional, you can also hardcode this)
CREATE TABLE IF NOT EXISTS shop_items (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    price INT NOT NULL,
    category TEXT NOT NULL
);

-- 🛒 Table for storing player orders
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES shop_items(id) ON DELETE CASCADE,
    quantity INTEGER DEFAULT 1,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);