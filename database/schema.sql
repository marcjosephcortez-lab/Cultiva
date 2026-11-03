-- ============================================================
--  Garden / Farm Planner - database schema
-- ============================================================
--  This file only creates TABLES. The database itself is created
--  by setup_db.py (so the name can come from your .env file).
--
--  Foreign key rules used on purpose:
--    RESTRICT  plantings -> plots, crops   (cannot delete a plot or crop
--                                           that still has plantings)
--    SET NULL  optional links               (delete the plot, keep the task)
--    CASCADE   shifts, attendance, attachments (child rows go with parent)
--
--  NOTE for students: this file must not contain a semicolon inside a
--  comment or text, because setup_db.py splits the file on semicolons.
-- ============================================================

-- ---------- settings: small key/value store (e.g. mode = garden or farm)
CREATE TABLE IF NOT EXISTS settings (
    setting_key   VARCHAR(50)  NOT NULL,
    setting_value VARCHAR(255) NOT NULL,
    PRIMARY KEY (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------- workers: Farm = workers, Garden = helpers
CREATE TABLE IF NOT EXISTS workers (
    id          INT           NOT NULL AUTO_INCREMENT,
    name        VARCHAR(100)  NOT NULL,
    role        VARCHAR(100)  NULL,
    phone       VARCHAR(30)   NULL,
    daily_rate  DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    active      TINYINT(1)    NOT NULL DEFAULT 1,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------- plots: Farm = plots, Garden = beds
CREATE TABLE IF NOT EXISTS plots (
    id          INT           NOT NULL AUTO_INCREMENT,
    name        VARCHAR(100)  NOT NULL,
    area        VARCHAR(50)   NULL,
    notes       TEXT          NULL,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_plots_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------- crops: Farm = crops, Garden = plants
CREATE TABLE IF NOT EXISTS crops (
    id               INT          NOT NULL AUTO_INCREMENT,
    name             VARCHAR(100) NOT NULL,
    color            CHAR(7)      NOT NULL DEFAULT '#4C9F50',
    days_to_harvest  INT          NOT NULL DEFAULT 90,
    notes            TEXT         NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_crops_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------- plantings: one crop planted in one plot on a date
CREATE TABLE IF NOT EXISTS plantings (
    id                INT          NOT NULL AUTO_INCREMENT,
    plot_id           INT          NOT NULL,
    crop_id           INT          NOT NULL,
    plant_date        DATE         NOT NULL,
    expected_harvest  DATE         NOT NULL,
    status            ENUM('growing','harvested','failed') NOT NULL DEFAULT 'growing',
    notes             TEXT         NULL,
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_plantings_plot FOREIGN KEY (plot_id) REFERENCES plots (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_plantings_crop FOREIGN KEY (crop_id) REFERENCES crops (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------- tasks: things to do. Links to plot, planting and worker are optional
CREATE TABLE IF NOT EXISTS tasks (
    id           INT          NOT NULL AUTO_INCREMENT,
    title        VARCHAR(200) NOT NULL,
    due_date     DATE         NOT NULL,
    priority     ENUM('low','medium','high') NOT NULL DEFAULT 'medium',
    done         TINYINT(1)   NOT NULL DEFAULT 0,
    notes        TEXT         NULL,
    plot_id      INT          NULL,
    planting_id  INT          NULL,
    worker_id    INT          NULL,
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_tasks_plot FOREIGN KEY (plot_id) REFERENCES plots (id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_tasks_planting FOREIGN KEY (planting_id) REFERENCES plantings (id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_tasks_worker FOREIGN KEY (worker_id) REFERENCES workers (id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------- shifts: weekly repeating blocks for the Timetable
--  weekday: 0 = Monday ... 6 = Sunday
--  Farm = a worker's shift. Garden = a care routine (worker_id may be empty).
CREATE TABLE IF NOT EXISTS shifts (
    id          INT          NOT NULL AUTO_INCREMENT,
    worker_id   INT          NULL,
    title       VARCHAR(150) NOT NULL,
    weekday     TINYINT      NOT NULL,
    start_time  TIME         NOT NULL,
    end_time    TIME         NOT NULL,
    plot_id     INT          NULL,
    notes       TEXT         NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_shifts_worker FOREIGN KEY (worker_id) REFERENCES workers (id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_shifts_plot FOREIGN KEY (plot_id) REFERENCES plots (id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------- attendance: one row per worker per day (Farm mode)
CREATE TABLE IF NOT EXISTS attendance (
    id          INT          NOT NULL AUTO_INCREMENT,
    worker_id   INT          NOT NULL,
    att_date    DATE         NOT NULL,
    status      ENUM('present','late','half_day','absent','leave','not_marked')
                NOT NULL DEFAULT 'not_marked',
    time_in     TIME         NULL,
    time_out    TIME         NULL,
    remarks     VARCHAR(255) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_attendance_worker_date (worker_id, att_date),
    CONSTRAINT fk_attendance_worker FOREIGN KEY (worker_id) REFERENCES workers (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------- journal_entries: dated diary entries
CREATE TABLE IF NOT EXISTS journal_entries (
    id             INT          NOT NULL AUTO_INCREMENT,
    entry_date     DATE         NOT NULL,
    title          VARCHAR(200) NOT NULL,
    body           TEXT         NULL,
    mood_weather   VARCHAR(50)  NULL,
    plot_id        INT          NULL,
    crop_id        INT          NULL,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_journal_date (entry_date),
    CONSTRAINT fk_journal_plot FOREIGN KEY (plot_id) REFERENCES plots (id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_journal_crop FOREIGN KEY (crop_id) REFERENCES crops (id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------- notes: titled notes with optional links
CREATE TABLE IF NOT EXISTS notes (
    id          INT          NOT NULL AUTO_INCREMENT,
    title       VARCHAR(200) NOT NULL,
    body        TEXT         NULL,
    plot_id     INT          NULL,
    crop_id     INT          NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_notes_plot FOREIGN KEY (plot_id) REFERENCES plots (id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_notes_crop FOREIGN KEY (crop_id) REFERENCES crops (id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------- attachments: files that belong to a note OR a journal entry
--  Exactly one of note_id / journal_id must be set. The matching CHECK
--  constraint is added by setup_db.py (see the comment there), and the
--  app also validates this rule before saving.
CREATE TABLE IF NOT EXISTS attachments (
    id             INT          NOT NULL AUTO_INCREMENT,
    note_id        INT          NULL,
    journal_id     INT          NULL,
    stored_name    VARCHAR(100) NOT NULL,
    original_name  VARCHAR(255) NOT NULL,
    mime_type      VARCHAR(100) NULL,
    size_bytes     BIGINT       NOT NULL DEFAULT 0,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_attachments_stored (stored_name),
    CONSTRAINT fk_attachments_note FOREIGN KEY (note_id) REFERENCES notes (id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_attachments_journal FOREIGN KEY (journal_id) REFERENCES journal_entries (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------- resources: centralized, deduplicated imported files
CREATE TABLE IF NOT EXISTS resources (
    id             INT NOT NULL AUTO_INCREMENT,
    stored_name    VARCHAR(100) NOT NULL,
    original_name  VARCHAR(255) NOT NULL,
    extension      VARCHAR(20) NOT NULL DEFAULT '',
    category       VARCHAR(40) NOT NULL DEFAULT 'Other',
    mime_type      VARCHAR(150) NULL,
    size_bytes     BIGINT NOT NULL DEFAULT 0,
    sha256         CHAR(64) NOT NULL,
    description    VARCHAR(500) NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_resources_stored (stored_name),
    UNIQUE KEY uq_resources_sha256 (sha256),
    KEY idx_resources_category (category),
    KEY idx_resources_name (original_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------- resource_links: reuse one Library resource from multiple modules
CREATE TABLE IF NOT EXISTS resource_links (
    id             INT NOT NULL AUTO_INCREMENT,
    resource_id    INT NOT NULL,
    module_key     VARCHAR(40) NOT NULL,
    record_id      INT NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_resource_module_record (resource_id, module_key, record_id),
    KEY idx_resource_links_record (module_key, record_id),
    CONSTRAINT fk_resource_links_resource FOREIGN KEY (resource_id) REFERENCES resources (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
