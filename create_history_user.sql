-- =============================================================================
-- AI-Enhanced Database Query Assistant - Phase 5
-- Dedicated Query History MySQL User Setup Script
--
-- IMPORTANT:
-- 1. Replace 'CHANGE_ME_HISTORY_PASSWORD' with a strong password of your choice.
-- 2. Execute this script manually using a MySQL admin/root account.
-- 3. Update your .env file with DB_HISTORY_USER and DB_HISTORY_PASSWORD.
-- =============================================================================

CREATE USER IF NOT EXISTS 'query_history_user'@'localhost'
    IDENTIFIED BY 'sujan12345@';

-- Grant only the minimum required permissions on college_db.query_history
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'query_history_user'@'localhost';
GRANT SELECT, INSERT, UPDATE ON college_db.query_history TO 'query_history_user'@'localhost';

FLUSH PRIVILEGES;
