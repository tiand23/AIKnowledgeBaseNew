-- ============================================
-- 会话归档相关表结构
-- ============================================

-- 1. 会话归档表
CREATE TABLE IF NOT EXISTS `conversation_archive` (
    `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `conversation_id` VARCHAR(36) NOT NULL UNIQUE COMMENT '会话ID（UUID）',
    `user_id` BIGINT NOT NULL COMMENT '用户ID',
    `archived_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '归档时间',
    INDEX `idx_conversation_id` (`conversation_id`),
    INDEX `idx_user_archived` (`user_id`, `archived_at`),
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话归档表';

-- 2. 会话消息表
CREATE TABLE IF NOT EXISTS `conversation_messages` (
    `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `conversation_id` VARCHAR(36) NOT NULL COMMENT '会话ID',
    `role` VARCHAR(20) NOT NULL COMMENT '角色: user 或 assistant',
    `content` LONGTEXT NOT NULL COMMENT '消息内容',
    `timestamp` DATETIME NOT NULL COMMENT '消息时间戳',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX `idx_conversation_timestamp` (`conversation_id`, `timestamp`),
    FOREIGN KEY (`conversation_id`) REFERENCES `conversation_archive` (`conversation_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话消息表';

