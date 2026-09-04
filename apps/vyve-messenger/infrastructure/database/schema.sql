-- VYVE Messenger — Database Schema
-- Version: 1.0.0
-- Database: PostgreSQL 16+ (or SQLite 3.45+ with adaptations)
-- All sensitive content is end-to-end encrypted; server stores ciphertext only.

-- =====================================================================
-- USERS & IDENTITY
-- =====================================================================

CREATE TABLE users (
    user_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username          VARCHAR(32) UNIQUE NOT NULL,
    display_name      VARCHAR(64),
    bio               TEXT,
    avatar_url        TEXT,
    email             VARCHAR(255),  -- optional, for recovery only
    email_verified    BOOLEAN DEFAULT FALSE,
    
    -- Public keys (server cannot read messages)
    identity_signing_key    BYTEA NOT NULL,  -- Ed25519, 32 bytes
    identity_encryption_key BYTEA NOT NULL,  -- X25519, 32 bytes
    key_id            UUID NOT NULL DEFAULT gen_random_uuid(),
    keys_generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Account metadata
    tier              VARCHAR(20) DEFAULT 'free' CHECK (tier IN
                       ('free', 'creator', 'pro', 'developer', 'business', 'enterprise')),
    is_vendor         BOOLEAN DEFAULT FALSE,
    is_admin          BOOLEAN DEFAULT FALSE,  -- CJ-level only
    
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ,  -- soft delete for 30-day grace period
    scheduled_hard_delete_at TIMESTAMPTZ,  -- 30 days after deleted_at
    
    CONSTRAINT username_lowercase CHECK (username = LOWER(username)),
    CONSTRAINT username_format CHECK (username ~ '^[a-z0-9_]{3,32}$')
);

CREATE INDEX idx_users_username ON users(username) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_tier ON users(tier) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_deleted ON users(deleted_at) WHERE deleted_at IS NOT NULL;

-- =====================================================================
-- DEVICES
-- =====================================================================

CREATE TABLE devices (
    device_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    device_name            VARCHAR(64) NOT NULL,
    device_type            VARCHAR(16) NOT NULL CHECK (device_type IN
                            ('android', 'ios', 'web', 'desktop', 'watch', 'tv')),
    device_model           VARCHAR(64),  -- optional, for display
    
    -- Device public keys
    signing_key            BYTEA NOT NULL,  -- Ed25519
    encryption_key         BYTEA NOT NULL,  -- X25519
    
    -- Attestation
    attestation_token      TEXT,  -- hardware attestation (SafetyNet/Play Integrity)
    attestation_verified   BOOLEAN DEFAULT FALSE,
    
    -- Lifecycle
    registered_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at           TIMESTAMPTZ,
    revoked_at             TIMESTAMPTZ,  -- if revoked, can no longer receive messages
    revocation_reason      TEXT,
    
    -- Trust
    trusted                BOOLEAN DEFAULT TRUE,  -- user has verified this device
    
    UNIQUE (user_id, signing_key)
);

CREATE INDEX idx_devices_user ON devices(user_id) WHERE revoked_at IS NULL;
CREATE INDEX idx_devices_last_seen ON devices(last_seen_at) WHERE revoked_at IS NULL;

-- =====================================================================
-- OAUTH TOKENS
-- =====================================================================

CREATE TABLE oauth_tokens (
    token_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    device_id         UUID REFERENCES devices(device_id) ON DELETE CASCADE,
    
    access_token_hash BYTEA NOT NULL UNIQUE,  -- SHA-256 of access token
    refresh_token_hash BYTEA NOT NULL UNIQUE,  -- SHA-256 of refresh token
    id_token_hash     BYTEA,  -- optional OIDC ID token
    
    scopes            TEXT[] NOT NULL DEFAULT '{}',
    
    issued_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    access_expires_at TIMESTAMPTZ NOT NULL,
    refresh_expires_at TIMESTAMPTZ NOT NULL,
    
    -- Rotation tracking
    rotated_from      UUID REFERENCES oauth_tokens(token_id),  -- parent token
    rotated_at        TIMESTAMPTZ,
    
    revoked_at        TIMESTAMPTZ,
    revocation_reason TEXT,
    
    CONSTRAINT access_expires_valid CHECK (access_expires_at > issued_at),
    CONSTRAINT refresh_expires_valid CHECK (refresh_expires_at > access_expires_at)
);

CREATE INDEX idx_oauth_access ON oauth_tokens(access_token_hash) WHERE revoked_at IS NULL;
CREATE INDEX idx_oauth_refresh ON oauth_tokens(refresh_token_hash) WHERE revoked_at IS NULL;
CREATE INDEX idx_oauth_user ON oauth_tokens(user_id, issued_at DESC) WHERE revoked_at IS NULL;
CREATE INDEX idx_oauth_expiring ON oauth_tokens(refresh_expires_at) WHERE revoked_at IS NULL;

-- =====================================================================
-- CONVERSATIONS
-- =====================================================================

CREATE TABLE conversations (
    conversation_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_type VARCHAR(16) NOT NULL CHECK (conversation_type IN
                       ('direct', 'group', 'channel', 'community')),
    name              VARCHAR(128),
    description       TEXT,
    avatar_url        TEXT,
    
    -- Group/channel metadata
    is_public         BOOLEAN DEFAULT FALSE,
    max_members       INTEGER,
    
    created_by        UUID NOT NULL REFERENCES users(user_id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    deleted_at        TIMESTAMPTZ
);

CREATE INDEX idx_conversations_last_activity ON conversations(last_activity_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_conversations_type ON conversations(conversation_type) WHERE deleted_at IS NULL;

CREATE TABLE conversation_participants (
    conversation_id  UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    joined_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at          TIMESTAMPTZ,  -- null = still a participant
    
    role             VARCHAR(20) DEFAULT 'member' CHECK (role IN
                      ('owner', 'admin', 'moderator', 'member')),
    
    -- Per-user encryption metadata
    encryption_key_id UUID,  -- which key version they're using
    
    -- Read state
    last_read_message_id UUID,
    unread_count     INTEGER DEFAULT 0,
    
    -- Notifications
    notifications_enabled BOOLEAN DEFAULT TRUE,
    muted_until      TIMESTAMPTZ,
    
    PRIMARY KEY (conversation_id, user_id)
);

CREATE INDEX idx_conv_part_user ON conversation_participants(user_id) WHERE left_at IS NULL;
CREATE INDEX idx_conv_part_unread ON conversation_participants(user_id, unread_count) WHERE left_at IS NULL;

-- =====================================================================
-- MESSAGES (server never sees plaintext)
-- =====================================================================

CREATE TABLE messages (
    message_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id   UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    sender_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Cryptographic envelope (server CANNOT read)
    ephemeral_pubkey  BYTEA NOT NULL,  -- 32 bytes
    nonce             BYTEA NOT NULL,  -- 24 bytes
    ciphertext        BYTEA NOT NULL,  -- variable, encrypted
    signature         BYTEA NOT NULL,  -- 64 bytes Ed25519
    
    -- Server metadata (privacy-minimized)
    sender_key_id     UUID NOT NULL,  -- which sender device
    recipient_key_ids UUID[] NOT NULL,  -- which recipient devices
    size_bucket       VARCHAR(8) NOT NULL CHECK (size_bucket IN
                       ('tiny', 'small', 'medium', 'large', 'xlarge')),
    
    -- Client features
    reply_to_message_id UUID REFERENCES messages(message_id) ON DELETE SET NULL,
    forward_policy    VARCHAR(16) DEFAULT 'allowed' CHECK (forward_policy IN
                       ('allowed', 'restricted', 'forbidden')),
    
    -- Lifecycle
    sent_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at      TIMESTAMPTZ,
    read_at           TIMESTAMPTZ,
    edited_at         TIMESTAMPTZ,
    deleted_at        TIMESTAMPTZ,  -- user deleted from their view
    expires_at        TIMESTAMPTZ,  -- for disappearing messages
    
    -- Delivery status per device
    delivery_status   JSONB NOT NULL DEFAULT '{}',  -- {device_id: status}
    
    -- Moderation
    flagged           BOOLEAN DEFAULT FALSE,
    flag_reason       TEXT,
    moderation_status VARCHAR(20) DEFAULT 'ok' CHECK (moderation_status IN
                       ('ok', 'reviewing', 'removed')),
    
    CONSTRAINT ciphertext_not_empty CHECK (octet_length(ciphertext) > 0)
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, sent_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_messages_sender ON messages(sender_id, sent_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_messages_flagged ON messages(flagged) WHERE flagged = TRUE;
CREATE INDEX idx_messages_expires ON messages(expires_at) WHERE expires_at IS NOT NULL;

-- Per-recipient delivery tracking
CREATE TABLE message_recipients (
    message_id    UUID NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
    user_id       UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    device_id     UUID REFERENCES devices(device_id) ON DELETE CASCADE,
    
    delivered_at  TIMESTAMPTZ,
    read_at       TIMESTAMPTZ,
    
    PRIMARY KEY (message_id, user_id, device_id)
);

CREATE INDEX idx_msg_recipients_user ON message_recipients(user_id, read_at);

-- =====================================================================
-- ATTACHMENTS (encrypted files)
-- =====================================================================

CREATE TABLE attachments (
    attachment_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploader_id       UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    conversation_id   UUID REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    message_id        UUID REFERENCES messages(message_id) ON DELETE CASCADE,
    
    filename          VARCHAR(255) NOT NULL,
    mime_type         VARCHAR(128),
    file_size         BIGINT NOT NULL,
    
    -- Encryption envelope
    wrapped_file_key  BYTEA NOT NULL,  -- encrypted with recipient's encryption key
    file_nonce        BYTEA NOT NULL,  -- 24 bytes
    file_hash         BYTEA NOT NULL,  -- BLAKE2b-512 of plaintext
    storage_key       TEXT NOT NULL,   -- S3 object key (ciphertext)
    
    -- Metadata
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at        TIMESTAMPTZ,
    download_count    INTEGER DEFAULT 0,
    
    deleted_at        TIMESTAMPTZ
);

CREATE INDEX idx_attachments_message ON attachments(message_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_attachments_uploader ON attachments(uploader_id) WHERE deleted_at IS NULL;

-- =====================================================================
-- SOCIAL GRAPH
-- =====================================================================

CREATE TABLE follows (
    follower_id  UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    followee_id  UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (follower_id, followee_id),
    CHECK (follower_id <> followee_id)
);

CREATE INDEX idx_follows_followee ON follows(followee_id);
CREATE INDEX idx_follows_follower ON follows(follower_id);

CREATE TABLE blocks (
    blocker_id   UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    blocked_id   UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    reason       TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (blocker_id, blocked_id),
    CHECK (blocker_id <> blocked_id)
);

-- =====================================================================
-- COMMUNITIES
-- =====================================================================

CREATE TABLE communities (
    community_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(64) UNIQUE NOT NULL,
    display_name  VARCHAR(128) NOT NULL,
    description   TEXT,
    rules         TEXT,
    
    is_public     BOOLEAN DEFAULT TRUE,
    requires_approval BOOLEAN DEFAULT FALSE,
    
    created_by    UUID NOT NULL REFERENCES users(user_id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    member_count  INTEGER DEFAULT 0,
    post_count    INTEGER DEFAULT 0,
    
    deleted_at    TIMESTAMPTZ
);

CREATE INDEX idx_communities_name ON communities(name) WHERE deleted_at IS NULL;
CREATE INDEX idx_communities_public ON communities(is_public, member_count DESC) WHERE deleted_at IS NULL;

CREATE TABLE community_members (
    community_id UUID NOT NULL REFERENCES communities(community_id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    role         VARCHAR(20) DEFAULT 'member' CHECK (role IN
                  ('owner', 'admin', 'moderator', 'member')),
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at      TIMESTAMPTZ,
    
    PRIMARY KEY (community_id, user_id)
);

CREATE INDEX idx_community_members_user ON community_members(user_id) WHERE left_at IS NULL;

-- =====================================================================
-- POSTS
-- =====================================================================

CREATE TABLE posts (
    post_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    author_id    UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    community_id UUID REFERENCES communities(community_id) ON DELETE SET NULL,
    
    content      TEXT NOT NULL,
    
    visibility   VARCHAR(16) NOT NULL DEFAULT 'public' CHECK (visibility IN
                  ('public', 'followers', 'community', 'private')),
    
    reply_to_post_id UUID REFERENCES posts(post_id) ON DELETE SET NULL,
    repost_of_post_id UUID REFERENCES posts(post_id) ON DELETE SET NULL,
    
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    edited_at    TIMESTAMPTZ,
    deleted_at   TIMESTAMPTZ,
    
    moderation_status VARCHAR(20) DEFAULT 'ok' CHECK (moderation_status IN
                       ('ok', 'reviewing', 'removed')),
    
    CONSTRAINT content_not_empty CHECK (length(content) > 0)
);

CREATE INDEX idx_posts_author ON posts(author_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_posts_community ON posts(community_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_posts_visibility ON posts(visibility, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_posts_reply_to ON posts(reply_to_post_id) WHERE reply_to_post_id IS NOT NULL;

CREATE TABLE post_reactions (
    post_id    UUID NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    reaction   VARCHAR(16) NOT NULL,  -- emoji or reaction type
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (post_id, user_id, reaction)
);

CREATE TABLE comments (
    comment_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id      UUID NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    author_id    UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    content      TEXT NOT NULL,
    
    parent_comment_id UUID REFERENCES comments(comment_id) ON DELETE CASCADE,
    
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    edited_at    TIMESTAMPTZ,
    deleted_at   TIMESTAMPTZ,
    
    CONSTRAINT content_not_empty CHECK (length(content) > 0)
);

CREATE INDEX idx_comments_post ON comments(post_id, created_at) WHERE deleted_at IS NULL;

-- =====================================================================
-- MARKETPLACE (🔐💲💎)
-- =====================================================================

CREATE TABLE vendors (
    vendor_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    
    vendor_name   VARCHAR(64) NOT NULL,
    display_name  VARCHAR(128),
    description   TEXT,
    logo_url      TEXT,
    banner_url    TEXT,
    
    verified      BOOLEAN DEFAULT FALSE,
    verification_status VARCHAR(20) DEFAULT 'pending' CHECK (verification_status IN
                     ('pending', 'verified', 'rejected', 'suspended')),
    
    categories    TEXT[] DEFAULT '{}',
    
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    suspended_at  TIMESTAMPTZ,
    
    -- Aggregated stats (materialized)
    rating_avg    DECIMAL(3,2),
    rating_count  INTEGER DEFAULT 0,
    product_count INTEGER DEFAULT 0
);

CREATE INDEX idx_vendors_verified ON vendors(verified) WHERE verified = TRUE;
CREATE INDEX idx_vendors_categories ON vendors USING gin(categories);

CREATE TABLE products (
    product_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id      UUID NOT NULL REFERENCES vendors(vendor_id) ON DELETE CASCADE,
    
    title          VARCHAR(128) NOT NULL,
    description    TEXT NOT NULL,
    
    product_type   VARCHAR(32) NOT NULL CHECK (product_type IN
                    ('digital_good', 'service', 'course', 'template',
                     'consulting', 'artwork', 'music', 'software')),
    
    price          DECIMAL(12,2) NOT NULL,
    currency       VARCHAR(3) DEFAULT 'USD',
    
    -- For digital goods
    file_size      BIGINT,
    file_format    VARCHAR(32),
    
    -- For services
    delivery_days  INTEGER,
    revisions      INTEGER DEFAULT 0,
    
    status         VARCHAR(16) DEFAULT 'active' CHECK (status IN
                    ('active', 'paused', 'sold_out', 'deleted')),
    
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at     TIMESTAMPTZ
);

CREATE INDEX idx_products_vendor ON products(vendor_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_products_status ON products(status, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_products_type ON products(product_type) WHERE deleted_at IS NULL;

CREATE TABLE orders (
    order_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id       UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    vendor_id      UUID NOT NULL REFERENCES vendors(vendor_id) ON DELETE CASCADE,
    product_id     UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    
    -- Payment (handled by external provider; VYVE stores only IDs)
    payment_provider    VARCHAR(32) NOT NULL,
    payment_intent_id   VARCHAR(128) NOT NULL,
    payment_status      VARCHAR(32) NOT NULL,
    
    amount         DECIMAL(12,2) NOT NULL,
    currency       VARCHAR(3) NOT NULL,
    platform_fee   DECIMAL(12,2) NOT NULL,
    
    -- Order lifecycle
    status         VARCHAR(32) NOT NULL DEFAULT 'requested' CHECK (status IN
                    ('requested', 'accepted', 'in_progress', 'delivered',
                     'completed', 'cancelled', 'disputed', 'refunded')),
    
    -- Delivery (for digital goods: file IDs; for services: chat thread)
    delivered_at   TIMESTAMPTZ,
    completed_at   TIMESTAMPTZ,
    cancelled_at   TIMESTAMPTZ,
    disputed_at    TIMESTAMPTZ,
    
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_buyer ON orders(buyer_id, created_at DESC);
CREATE INDEX idx_orders_vendor ON orders(vendor_id, created_at DESC);
CREATE INDEX idx_orders_status ON orders(status, created_at DESC);

CREATE TABLE reviews (
    review_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id    UUID NOT NULL UNIQUE REFERENCES orders(order_id) ON DELETE CASCADE,
    buyer_id    UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    vendor_id   UUID NOT NULL REFERENCES vendors(vendor_id) ON DELETE CASCADE,
    product_id  UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title       VARCHAR(128),
    content     TEXT,
    
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    edited_at   TIMESTAMPTZ,
    deleted_at  TIMESTAMPTZ  -- soft delete only
);

CREATE INDEX idx_reviews_vendor ON reviews(vendor_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_reviews_product ON reviews(product_id) WHERE deleted_at IS NULL;

-- =====================================================================
-- AUDIT & SECURITY
-- =====================================================================

CREATE TABLE audit_log (
    audit_id      BIGSERIAL PRIMARY KEY,
    actor_id      UUID REFERENCES users(user_id) ON DELETE SET NULL,
    action        VARCHAR(64) NOT NULL,
    target_type   VARCHAR(32),
    target_id     VARCHAR(64),
    details       JSONB,
    ip_address    INET,
    user_agent    TEXT,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_actor ON audit_log(actor_id, occurred_at DESC);
CREATE INDEX idx_audit_action ON audit_log(action, occurred_at DESC);
CREATE INDEX idx_audit_target ON audit_log(target_type, target_id);

-- Append-only enforced via trigger
CREATE OR REPLACE FUNCTION audit_log_no_update() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_immutable
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_no_update();

CREATE TABLE security_events (
    event_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID REFERENCES users(user_id) ON DELETE SET NULL,
    event_type    VARCHAR(64) NOT NULL,
    severity      VARCHAR(16) NOT NULL CHECK (severity IN
                    ('low', 'medium', 'high', 'critical')),
    details       JSONB,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at   TIMESTAMPTZ,
    resolved_by   UUID REFERENCES users(user_id)
);

CREATE INDEX idx_security_user ON security_events(user_id, occurred_at DESC);
CREATE INDEX idx_security_unresolved ON security_events(severity, occurred_at DESC) WHERE resolved_at IS NULL;

-- =====================================================================
-- FULL-TEXT SEARCH
-- =====================================================================

-- For searching posts, products, vendors (text-search is server-side)
CREATE INDEX idx_posts_content_fts ON posts USING gin(to_tsvector('english', content))
    WHERE deleted_at IS NULL;

CREATE INDEX idx_products_title_fts ON products USING gin(to_tsvector('english', title || ' ' || description))
    WHERE deleted_at IS NULL;

-- =====================================================================
-- CLEANUP: Auto-delete expired data
-- =====================================================================

-- Run daily via cron or pg_cron
-- DELETE FROM messages WHERE expires_at < NOW() AND expires_at IS NOT NULL;
-- DELETE FROM oauth_tokens WHERE refresh_expires_at < NOW();
-- UPDATE users SET scheduled_hard_delete_at = NOW() + INTERVAL '30 days' WHERE deleted_at IS NOT NULL AND scheduled_hard_delete_at IS NULL;

-- =====================================================================
-- END OF SCHEMA
-- =====================================================================
