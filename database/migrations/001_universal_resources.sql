-- Cultiva Universal Import System migration.
-- Safe to run against an existing database; existing application tables/data are untouched.
CREATE TABLE IF NOT EXISTS resources (
    id INT NOT NULL AUTO_INCREMENT,
    stored_name VARCHAR(100) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    extension VARCHAR(20) NOT NULL DEFAULT '',
    category VARCHAR(40) NOT NULL DEFAULT 'Other',
    mime_type VARCHAR(150) NULL,
    size_bytes BIGINT NOT NULL DEFAULT 0,
    sha256 CHAR(64) NOT NULL,
    description VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_resources_stored (stored_name),
    UNIQUE KEY uq_resources_sha256 (sha256),
    KEY idx_resources_category (category),
    KEY idx_resources_name (original_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS resource_links (
    id INT NOT NULL AUTO_INCREMENT,
    resource_id INT NOT NULL,
    module_key VARCHAR(40) NOT NULL,
    record_id INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_resource_module_record (resource_id, module_key, record_id),
    KEY idx_resource_links_record (module_key, record_id),
    CONSTRAINT fk_resource_links_resource FOREIGN KEY (resource_id) REFERENCES resources (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
