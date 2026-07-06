from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `aerich` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `version` VARCHAR(255) NOT NULL,
    `app` VARCHAR(100) NOT NULL,
    `content` JSON NOT NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `hashed_password` VARCHAR(128),
    `name` VARCHAR(50) NOT NULL,
    `role_type` VARCHAR(20) NOT NULL DEFAULT 'PATIENT',
    `gender` VARCHAR(10),
    `birth_date` VARCHAR(20),
    `phone_number` VARCHAR(11),
    `sns_provider` VARCHAR(20) NOT NULL DEFAULT 'LOCAL',
    `sns_id` VARCHAR(255),
    `refresh_token` VARCHAR(500),
    `use_voice_mode` BOOL NOT NULL DEFAULT 0,
    `use_large_font` BOOL NOT NULL DEFAULT 0,
    `wake_time` TIME(6),
    `breakfast_time` TIME(6),
    `lunch_time` TIME(6),
    `dinner_time` TIME(6),
    `bed_time` TIME(6),
    `is_active` BOOL NOT NULL DEFAULT 1,
    `is_admin` BOOL NOT NULL DEFAULT 0,
    `last_login` DATETIME(6),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY `idx_users_email_133a6f` (`email`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `medications` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `standard_code` VARCHAR(50),
    `medication_name` VARCHAR(150) NOT NULL,
    `form_type` VARCHAR(30),
    `dosage_guideline` LONGTEXT,
    `side_effects` LONGTEXT,
    `precautions` LONGTEXT,
    `storage_method` LONGTEXT,
    `shape` VARCHAR(30),
    `color` VARCHAR(30),
    `letters` VARCHAR(50)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `medical_records` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `document_type` VARCHAR(20),
    `hospital_name` VARCHAR(100),
    `pharmacy_name` VARCHAR(100),
    `department_name` VARCHAR(50),
    `diagnosis_name` VARCHAR(150),
    `diagnosis_code` VARCHAR(20),
    `visit_date` DATE,
    `image_s3_url` VARCHAR(500),
    `ocr_raw_json` JSON,
    `receipt_amount` INT,
    `uploaded_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_medical__users_aa3196ba` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `medication_schedules` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `card_alias` VARCHAR(100),
    `frequency_type` VARCHAR(10) NOT NULL DEFAULT 'DAILY',
    `target_day_of_week` VARCHAR(10),
    `alarm_time` TIME(6) NOT NULL,
    `is_active` BOOL NOT NULL DEFAULT 1,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `medication_id` INT NOT NULL,
    `record_id` INT,
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_medicati_medicati_b5bbf7c8` FOREIGN KEY (`medication_id`) REFERENCES `medications` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_medicati_medical__536969f5` FOREIGN KEY (`record_id`) REFERENCES `medical_records` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_medicati_users_34f74703` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `ocr_tasks` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `task_id` VARCHAR(50) NOT NULL UNIQUE,
    `status` VARCHAR(20) NOT NULL DEFAULT 'PROCESSING',
    `image_s3_url` VARCHAR(500),
    `ocr_raw_json` JSON,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `record_id` INT,
    CONSTRAINT `fk_ocr_task_medical__7af6c806` FOREIGN KEY (`record_id`) REFERENCES `medical_records` (`id`) ON DELETE SET NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `record_medication_mapping` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `dosage_per_take` VARCHAR(30),
    `takes_per_day` INT,
    `duration_days` INT,
    `instruction` VARCHAR(255),
    `device_type` VARCHAR(30),
    `total_clicks_or_doses` INT,
    `total_prescribed_quantity` INT,
    `remaining_quantity` INT,
    `medication_id` INT NOT NULL,
    `record_id` INT NOT NULL,
    CONSTRAINT `fk_record_m_medicati_d5fafb1e` FOREIGN KEY (`medication_id`) REFERENCES `medications` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_record_m_medical__10e3634c` FOREIGN KEY (`record_id`) REFERENCES `medical_records` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `intake_logs` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `planned_date` DATE NOT NULL,
    `actual_take_time` DATETIME(6),
    `status` VARCHAR(20) NOT NULL DEFAULT 'MISSED',
    `verification_media_url` VARCHAR(500),
    `schedule_id` INT NOT NULL,
    CONSTRAINT `fk_intake_l_medicati_83909a91` FOREIGN KEY (`schedule_id`) REFERENCES `medication_schedules` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `support_groups` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `group_name` VARCHAR(100) NOT NULL,
    `invite_code` VARCHAR(50) NOT NULL UNIQUE,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `group_members` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `leaderboard_score` INT NOT NULL DEFAULT 0,
    `joined_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `group_id` INT NOT NULL,
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_group_me_support__25665270` FOREIGN KEY (`group_id`) REFERENCES `support_groups` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_group_me_users_ac3b0077` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `health_metrics` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `weight` DOUBLE,
    `height` DOUBLE,
    `blood_pressure_systolic` INT,
    `blood_pressure_diastolic` INT,
    `blood_glucose` INT,
    `source` VARCHAR(10) NOT NULL DEFAULT 'MANUAL',
    `recorded_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_health_m_users_769d851c` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `symptom_logs` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `symptom_notes` LONGTEXT NOT NULL,
    `severity_level` INT NOT NULL DEFAULT 1,
    `recorded_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_symptom__users_3995e4e1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `food_intake_logs` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `meal_time_type` VARCHAR(20),
    `food_name` VARCHAR(200) NOT NULL,
    `image_url` VARCHAR(500),
    `key_nutrients` VARCHAR(200),
    `calories` DOUBLE,
    `sugar_content` DOUBLE,
    `recorded_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_food_int_users_14b4c673` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `emergency_cards` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `blood_type` VARCHAR(5),
    `food_allergies` LONGTEXT,
    `medication_allergies` LONGTEXT,
    `past_history` LONGTEXT,
    `present_history` LONGTEXT,
    `family_history` LONGTEXT,
    `emergency_contacts` LONGTEXT,
    `user_id` INT NOT NULL UNIQUE,
    CONSTRAINT `fk_emergenc_users_72a898e0` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `drug_food_interactions` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `substance_name` VARCHAR(100) NOT NULL,
    `risk_level` VARCHAR(20) NOT NULL DEFAULT 'INFO',
    `guidance_text` LONGTEXT,
    `medication_id` INT NOT NULL,
    CONSTRAINT `fk_drug_foo_medicati_c144baf7` FOREIGN KEY (`medication_id`) REFERENCES `medications` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `chat_sessions` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `session_title` VARCHAR(150),
    `session_intent_mode` VARCHAR(30),
    `has_injected_context` BOOL NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_chat_ses_users_520002c0` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `chat_messages` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `sender_type` VARCHAR(15) NOT NULL,
    `message_text` LONGTEXT NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `session_id` INT NOT NULL,
    CONSTRAINT `fk_chat_mes_chat_ses_0d4a2737` FOREIGN KEY (`session_id`) REFERENCES `chat_sessions` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `hospital_appointments` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `hospital_name` VARCHAR(100) NOT NULL,
    `doctor_name` VARCHAR(50),
    `doctor_contact` VARCHAR(30),
    `appointment_at` DATETIME(6) NOT NULL,
    `memo` LONGTEXT,
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_hospital_users_c3a5c862` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `pwa_subscriptions` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `endpoint_url` VARCHAR(500) NOT NULL UNIQUE,
    `p256dh_key` VARCHAR(255) NOT NULL,
    `auth_key` VARCHAR(255) NOT NULL,
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_pwa_subs_users_5dc7fecc` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
