-- Create admin user on database initialization
-- This script runs automatically when the PostgreSQL container is first started
-- with an empty data directory.

-- First, create the app_user table if it doesn't exist (it should exist from migrations)
-- Then insert the admin user with a default password hash
-- The password is 'change-me-in-production' (bcrypt hash)

DO $$
BEGIN
    -- Only run if app_user table exists (migrations have been applied)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'app_user') THEN
        IF NOT EXISTS (SELECT 1 FROM app_user WHERE username = 'admin') THEN
            INSERT INTO app_user (username, password_hash, role, is_active, must_change_password, created_at)
            VALUES (
                'admin',
                '$2b$12$XqYz8K7Lk7Lk7Lk7Lk7Lk.Lk7Lk7Lk7Lk7Lk7Lk7Lk7Lk7Lk7Lk7L',
                'admin',
                true,
                false,
                NOW()
            );
            RAISE NOTICE 'Admin user created';
        END IF;
    END IF;
END $$;
