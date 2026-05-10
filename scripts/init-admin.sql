-- Create admin user on first database initialization
-- This runs only once when the database is created

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM app_user WHERE username = 'admin') THEN
        INSERT INTO app_user (username, password_hash, role, is_active, must_change_password, created_at)
        VALUES (
            'admin',
            '$2b$12$LJ3m4ys3Lk7Lk7Lk7Lk7L.Lk7Lk7Lk7Lk7Lk7Lk7Lk7Lk7Lk7Lk7L',
            'admin',
            true,
            false,
            NOW()
        );
    END IF;
END $$;
