CREATE TABLE IF NOT EXISTS users (
    id CHAR(36) PRIMARY KEY,
    auth0_user_id VARCHAR(191) NOT NULL UNIQUE,
    candidate_code VARCHAR(32) NOT NULL UNIQUE,
    full_name VARCHAR(191) NOT NULL,
    email VARCHAR(191) NOT NULL,
    avatar_url VARCHAR(512) NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    last_login_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_users_email (email),
    INDEX idx_users_candidate_code (candidate_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS modules (
    id CHAR(36) PRIMARY KEY,
    slug VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(191) NOT NULL,
    description TEXT NULL,
    question_count INT NOT NULL DEFAULT 5,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_modules_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluation_configs (
    id CHAR(36) PRIMARY KEY,
    module_id CHAR(36) NOT NULL,
    version INT NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    prompt_template MEDIUMTEXT NOT NULL,
    scoring_weights JSON NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_evaluation_configs_module_version (module_id, version),
    INDEX idx_evaluation_configs_active (module_id, is_active),
    CONSTRAINT fk_evaluation_configs_module
        FOREIGN KEY (module_id) REFERENCES modules (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS questions (
    id CHAR(36) PRIMARY KEY,
    module_id CHAR(36) NOT NULL,
    question_code VARCHAR(100) NOT NULL,
    title VARCHAR(191) NOT NULL,
    scenario_transcript MEDIUMTEXT NOT NULL,
    audio_storage_key VARCHAR(512) NOT NULL,
    audio_duration_seconds DECIMAL(8,2) NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_questions_module_code (module_id, question_code),
    INDEX idx_questions_module_active (module_id, is_active),
    CONSTRAINT fk_questions_module
        FOREIGN KEY (module_id) REFERENCES modules (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS standard_responses (
    id CHAR(36) PRIMARY KEY,
    question_id CHAR(36) NOT NULL,
    response_order INT NOT NULL,
    response_text MEDIUMTEXT NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_standard_responses_question_order (question_id, response_order),
    INDEX idx_standard_responses_question (question_id),
    CONSTRAINT fk_standard_responses_question
        FOREIGN KEY (question_id) REFERENCES questions (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS candidate_sessions (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    module_id CHAR(36) NOT NULL,
    status ENUM('not_started', 'in_progress', 'submitted', 'processing', 'completed', 'failed') NOT NULL DEFAULT 'not_started',
    login_at DATETIME(6) NOT NULL,
    started_at DATETIME(6) NULL,
    submitted_at DATETIME(6) NULL,
    completed_at DATETIME(6) NULL,
    ai_score DECIMAL(5,2) NULL,
    error_message VARCHAR(500) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_sessions_user_created (user_id, created_at),
    INDEX idx_sessions_module_status (module_id, status),
    CONSTRAINT fk_sessions_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_sessions_module
        FOREIGN KEY (module_id) REFERENCES modules (id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS session_questions (
    id CHAR(36) PRIMARY KEY,
    session_id CHAR(36) NOT NULL,
    question_id CHAR(36) NOT NULL,
    display_order INT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_session_questions_session_order (session_id, display_order),
    UNIQUE KEY uq_session_questions_session_question (session_id, question_id),
    CONSTRAINT fk_session_questions_session
        FOREIGN KEY (session_id) REFERENCES candidate_sessions (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_session_questions_question
        FOREIGN KEY (question_id) REFERENCES questions (id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS candidate_answers (
    id CHAR(36) PRIMARY KEY,
    session_id CHAR(36) NOT NULL,
    question_id CHAR(36) NOT NULL,
    status ENUM('pending', 'recorded', 'submitted', 'transcribed', 'evaluated', 'failed') NOT NULL DEFAULT 'pending',
    audio_storage_key VARCHAR(512) NULL,
    audio_duration_seconds DECIMAL(8,2) NULL,
    submitted_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_candidate_answers_session_question (session_id, question_id),
    INDEX idx_candidate_answers_status (status),
    CONSTRAINT fk_candidate_answers_session
        FOREIGN KEY (session_id) REFERENCES candidate_sessions (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_candidate_answers_question
        FOREIGN KEY (question_id) REFERENCES questions (id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS transcripts (
    id CHAR(36) PRIMARY KEY,
    answer_id CHAR(36) NOT NULL,
    transcript_text MEDIUMTEXT NOT NULL,
    detected_language VARCHAR(32) NULL,
    model_name VARCHAR(100) NOT NULL,
    processing_seconds DECIMAL(10,3) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_transcripts_answer (answer_id),
    CONSTRAINT fk_transcripts_answer
        FOREIGN KEY (answer_id) REFERENCES candidate_answers (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ai_evaluations (
    id CHAR(36) PRIMARY KEY,
    answer_id CHAR(36) NOT NULL,
    evaluation_config_id CHAR(36) NOT NULL,
    total_score DECIMAL(5,2) NOT NULL,
    courtesy_score DECIMAL(5,2) NOT NULL,
    respect_score DECIMAL(5,2) NOT NULL,
    empathy_score DECIMAL(5,2) NOT NULL,
    sympathy_score DECIMAL(5,2) NOT NULL,
    tone_score DECIMAL(5,2) NOT NULL,
    communication_clarity_score DECIMAL(5,2) NOT NULL,
    engagement_score DECIMAL(5,2) NOT NULL,
    problem_handling_approach_score DECIMAL(5,2) NOT NULL,
    strengths JSON NOT NULL,
    improvement_areas JSON NOT NULL,
    final_summary TEXT NOT NULL,
    confidence_score DECIMAL(5,2) NULL,
    raw_response JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_ai_evaluations_answer (answer_id),
    CONSTRAINT fk_ai_evaluations_answer
        FOREIGN KEY (answer_id) REFERENCES candidate_answers (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_ai_evaluations_config
        FOREIGN KEY (evaluation_config_id) REFERENCES evaluation_configs (id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS admin_evaluations (
    id CHAR(36) PRIMARY KEY,
    session_id CHAR(36) NOT NULL,
    admin_email VARCHAR(191) NOT NULL,
    admin_score DECIMAL(5,2) NOT NULL,
    feedback TEXT NULL,
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_admin_evaluations_session_created (session_id, updated_at),
    CONSTRAINT fk_admin_evaluations_session
        FOREIGN KEY (session_id) REFERENCES candidate_sessions (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
    id CHAR(36) PRIMARY KEY,
    actor_type VARCHAR(50) NOT NULL,
    actor_id VARCHAR(191) NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(191) NOT NULL,
    metadata JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_audit_logs_entity (entity_type, entity_id),
    INDEX idx_audit_logs_actor (actor_type, actor_id),
    INDEX idx_audit_logs_action (action, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
