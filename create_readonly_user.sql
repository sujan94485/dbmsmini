-- =============================================================================
-- AI-Enhanced Database Query Assistant - Phase 4
-- Read-Only MySQL User Setup Script
--
-- IMPORTANT:
-- 1. Replace 'CHANGE_ME_STRONG_PASSWORD' with a strong password of your choice.
-- 2. Execute this script manually using a MySQL admin/root account.
-- 3. Update your .env file with DB_READONLY_USER and DB_READONLY_PASSWORD.
-- =============================================================================

CREATE USER IF NOT EXISTS 'query_readonly'@'localhost'
    IDENTIFIED BY 'sujan1234@';

-- Grant read-only SELECT access strictly on college_db
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'query_readonly'@'localhost';
GRANT SELECT ON college_db.* TO 'query_readonly'@'localhost';

FLUSH PRIVILEGES;
