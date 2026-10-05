-- Technical baseline for NEW isolated databases only. See README.md for provenance.
CREATE TABLE roles (
 id SERIAL PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 short_definition TEXT, mission TEXT, personalization_variables TEXT,
 typical_tasks TEXT, work_objects TEXT, planning_horizon TEXT, impact_scale TEXT, authority_allowed TEXT, authority_requires_approval TEXT, escalation_rules TEXT, role_limits TEXT, red_lines TEXT, success_metrics TEXT, risks TEXT, interaction_scope TEXT, communication_rules TEXT, typical_scenarios TEXT, information_sources TEXT, templates_tools TEXT, correct_personalization_examples TEXT, incorrect_personalization_examples TEXT, methodist_notes TEXT
);
CREATE TABLE users (
 id SERIAL PRIMARY KEY, full_name TEXT, email TEXT UNIQUE, role_id INTEGER REFERENCES roles(id),
 job_description TEXT, phone TEXT, created_at TIMESTAMP NOT NULL DEFAULT NOW(), active_profile_id BIGINT
);
CREATE TABLE user_role_profiles (
 id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 role_id INTEGER REFERENCES roles(id), detected_role TEXT,
 user_processes JSONB, user_tasks JSONB, user_stakeholders JSONB, user_risks JSONB, user_constraints JSONB,
 raw_position TEXT, raw_duties TEXT, normalized_duties TEXT, role_confidence DOUBLE PRECISION,
 role_rationale TEXT, user_domain TEXT, user_context_vars JSONB NOT NULL DEFAULT '{}',
 profile_version INTEGER NOT NULL DEFAULT 1, profile_updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(), UNIQUE(user_id,profile_version)
);
ALTER TABLE users ADD CONSTRAINT users_active_profile_fk FOREIGN KEY(active_profile_id) REFERENCES user_role_profiles(id);
CREATE TABLE skills (
 id SERIAL PRIMARY KEY, skill_code TEXT NOT NULL UNIQUE, skill_name TEXT NOT NULL,
 competency_code TEXT, competency_name TEXT, description TEXT
);
CREATE TABLE user_sessions (
 id SERIAL PRIMARY KEY, session_code TEXT NOT NULL UNIQUE, user_id INTEGER NOT NULL REFERENCES users(id),
 role_id INTEGER REFERENCES roles(id), assessment_code TEXT, status TEXT NOT NULL DEFAULT 'created',
 source TEXT, notes TEXT, created_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 started_at TIMESTAMP, completed_at TIMESTAMP, finished_at TIMESTAMP
);
CREATE TABLE session_cases (
 id SERIAL PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES user_sessions(id),
 user_id INTEGER NOT NULL REFERENCES users(id), role_id INTEGER REFERENCES roles(id),
 status TEXT NOT NULL DEFAULT 'selected', selection_reason TEXT, planned_duration_minutes INTEGER,
 created_at TIMESTAMP NOT NULL DEFAULT NOW(), started_at TIMESTAMP, completed_at TIMESTAMP,
 personalized_case_text TEXT, user_answer TEXT, result_status TEXT
);
CREATE TABLE user_case_assignments (
 id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 status TEXT NOT NULL DEFAULT 'assigned', assigned_at TIMESTAMP NOT NULL DEFAULT NOW(), completed_at TIMESTAMP
);
CREATE TABLE user_skill_coverage (
 id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), skill_id INTEGER NOT NULL REFERENCES skills(id),
 status TEXT NOT NULL DEFAULT 'planned', covered_at TIMESTAMP, created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TABLE session_skills (
 id SERIAL PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES user_sessions(id), skill_id INTEGER NOT NULL REFERENCES skills(id),
 status TEXT NOT NULL DEFAULT 'planned', assigned_case_count INTEGER NOT NULL DEFAULT 0,
 completed_case_count INTEGER NOT NULL DEFAULT 0, covered_at TIMESTAMP, UNIQUE(session_id,skill_id)
);
CREATE TABLE session_case_skills (
 id SERIAL PRIMARY KEY, session_case_id INTEGER NOT NULL REFERENCES session_cases(id), skill_id INTEGER NOT NULL REFERENCES skills(id),
 coverage_status TEXT NOT NULL DEFAULT 'planned', UNIQUE(session_case_id,skill_id)
);
CREATE TABLE session_skill_assessments (
 id SERIAL PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES user_sessions(id), user_id INTEGER NOT NULL REFERENCES users(id),
 skill_id INTEGER NOT NULL REFERENCES skills(id), assessed_level_code TEXT, UNIQUE(session_id,skill_id)
);
CREATE TABLE organizations (
 id BIGSERIAL PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE role_skills (
 role_id INTEGER NOT NULL REFERENCES roles(id), skill_id INTEGER NOT NULL REFERENCES skills(id),
 PRIMARY KEY(role_id,skill_id)
);
