-- ============================================
-- MySQL 数据库索引优化脚本
-- 汽车移动设备管理平台
-- 执行此脚本可显著提升查询性能
-- ============================================

-- ============================================
-- 1. 设备表 (devices) 索引优化
-- ============================================

-- 用于逾期设备查询优化（admin_mobile_dashboard）
CREATE INDEX idx_devices_status_expected 
ON devices(status, expected_return_date, is_deleted);

-- 用于设备类型筛选查询
CREATE INDEX idx_devices_type_status 
ON devices(device_type, status, is_deleted);

-- 用于借用人查询
CREATE INDEX idx_devices_borrower 
ON devices(borrower, status);

-- ============================================
-- 2. 用户表 (users) 索引优化
-- ============================================

-- 用于用户状态筛选（排行榜等查询）
CREATE INDEX idx_users_status 
ON users(is_frozen, is_deleted);

-- 用于用户名搜索
CREATE INDEX idx_users_name 
ON users(borrower_name);

-- ============================================
-- 3. 积分表 (user_points) 索引优化
-- ============================================

-- 用于积分排行榜排序（关键优化）
CREATE INDEX idx_user_points_total_earned 
ON user_points(total_earned DESC);

-- 用户ID关联查询
CREATE INDEX idx_user_points_user_id 
ON user_points(user_id);

-- ============================================
-- 4. 积分记录表 (points_records) 索引优化
-- ============================================

-- 用于每日积分统计查询
CREATE INDEX idx_points_records_daily 
ON points_records(user_id, transaction_type, create_time);

-- 用于用户积分记录查询
CREATE INDEX idx_points_records_user 
ON points_records(user_id, create_time DESC);

-- ============================================
-- 5. 记录表 (records) 索引优化
-- ============================================

-- 用于记录查询和统计
CREATE INDEX idx_records_borrower_time 
ON records(borrower, operation_time DESC);

-- 用于设备关联记录查询
CREATE INDEX idx_records_device 
ON records(device_id, operation_time DESC);

-- 用于操作类型统计
CREATE INDEX idx_records_operation_type 
ON records(operation_type, operation_time);

-- ============================================
-- 6. 预约表 (reservations) 索引优化
-- ============================================

-- 用于用户预约查询
CREATE INDEX idx_reservations_user 
ON reservations(user_id, status, create_time DESC);

-- 用于设备预约查询
CREATE INDEX idx_reservations_device 
ON reservations(device_id, status);

-- ============================================
-- 7. 悬赏表 (bounties) 索引优化
-- ============================================

-- 用于悬赏状态筛选
CREATE INDEX idx_bounties_status 
ON bounties(status, create_time DESC);

-- 用于发布者查询
CREATE INDEX idx_bounties_publisher 
ON bounties(publisher_id, status);

-- ============================================
-- 8. 点赞表 (user_likes) 索引优化
-- ============================================

-- 用于用户点赞查询
CREATE INDEX idx_user_likes_user 
ON user_likes(user_id, target_id);

-- 用于被点赞者查询
CREATE INDEX idx_user_likes_target 
ON user_likes(target_id);

-- ============================================
-- 索引优化说明
-- ============================================
-- 
-- 主要优化效果：
-- 1. 排行榜查询：从全表扫描 O(n) 优化到索引扫描 O(log n)
-- 2. 逾期设备查询：避免全表遍历，直接定位逾期记录
-- 3. 用户积分查询：加速每日积分统计
-- 4. 记录查询：加速借阅历史查询
--
-- 注意事项：
-- 1. 索引会增加写入操作的时间，建议在低峰期执行
-- 2. 如果表数据量很大，创建索引可能需要较长时间
-- 3. 建议定期使用 ANALYZE TABLE 更新统计信息
--
-- 执行方式：
-- mysql -u username -p database_name < mysql_indexes_optimization.sql
--
-- ============================================
