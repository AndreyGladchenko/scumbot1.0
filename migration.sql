-- === MIGRATION SCRIPT: Bring existing SCUM Bot DB up-to-date ===

-- 1. Players table updates
ALTER TABLE players
    ALTER COLUMN scum_username SET DEFAULT '',
    ALTER COLUMN discord_username SET DEFAULT '',
    ALTER COLUMN balance SET DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='players' AND column_name='discord_username'
    ) THEN
        ALTER TABLE players ADD COLUMN discord_username TEXT DEFAULT '';
    END IF;
END$$;

-- 2. Shop items table updates
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='shop_items' AND column_name='description'
    ) THEN
        ALTER TABLE shop_items ADD COLUMN description TEXT DEFAULT '';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='shop_items' AND column_name='content'
    ) THEN
        ALTER TABLE shop_items ADD COLUMN content TEXT DEFAULT '';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='shop_items' AND column_name='image_url'
    ) THEN
        ALTER TABLE shop_items ADD COLUMN image_url TEXT DEFAULT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='shop_items' AND column_name='message_id'
    ) THEN
        ALTER TABLE shop_items ADD COLUMN message_id TEXT DEFAULT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='shop_items' AND column_name='channel_id'
    ) THEN
        ALTER TABLE shop_items ADD COLUMN channel_id TEXT DEFAULT NULL;
    END IF;
END$$;

-- 3. Orders table updates
ALTER TABLE orders
    ALTER COLUMN total_price SET DEFAULT 0;

-- Trigger to auto-calc total_price if NULL
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

-- 4. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_players_discord_id ON players(discord_id);
CREATE INDEX IF NOT EXISTS idx_shop_items_name ON shop_items(name);
CREATE INDEX IF NOT EXISTS idx_orders_player_id ON orders(player_id);
CREATE INDEX IF NOT EXISTS idx_orders_item_id ON orders(item_id);

-- ✅ Done
