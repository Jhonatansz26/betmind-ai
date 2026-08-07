-- Migración 013: Soporte Multi-Tenancy y Autenticación Progresiva en saved_tickets
ALTER TABLE users
ADD COLUMN IF NOT EXISTS auth_uid UUID;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_auth_uid
ON users (auth_uid)
WHERE auth_uid IS NOT NULL;

ALTER TABLE saved_tickets
ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_saved_tickets_user_id
ON saved_tickets (user_id)
WHERE user_id IS NOT NULL;

ALTER TABLE saved_tickets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS saved_tickets_public_read ON saved_tickets;
DROP POLICY IF EXISTS saved_tickets_read_policy ON saved_tickets;
CREATE POLICY saved_tickets_read_policy ON saved_tickets
    FOR SELECT USING (
        user_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = saved_tickets.user_id
              AND users.auth_uid = auth.uid()
        )
    );

DROP POLICY IF EXISTS saved_tickets_insert_policy ON saved_tickets;
CREATE POLICY saved_tickets_insert_policy ON saved_tickets
    FOR INSERT WITH CHECK (
        user_id IS NULL
        OR EXISTS (
            SELECT 1 FROM users
            WHERE users.id = saved_tickets.user_id
              AND users.auth_uid = auth.uid()
        )
    );

DROP POLICY IF EXISTS saved_tickets_update_policy ON saved_tickets;
CREATE POLICY saved_tickets_update_policy ON saved_tickets
    FOR UPDATE USING (
        (
            user_id IS NOT NULL
            AND EXISTS (
                SELECT 1 FROM users
                WHERE users.id = saved_tickets.user_id
                  AND users.auth_uid = auth.uid()
            )
        )
        OR (user_id IS NULL AND auth.uid() IS NOT NULL)
    )
    WITH CHECK (
        user_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = saved_tickets.user_id
              AND users.auth_uid = auth.uid()
        )
    );
