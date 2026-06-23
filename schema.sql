-- Aviation Maintenance Analyzer — schema
-- Target platform: UH-60 series (Black Hawk) fleet maintenance records
-- Engine: SQLite 3
--
-- Design note: all data produced by this schema is SYNTHETIC. The tables are
-- modeled on how a unit tracks airframe time, time/life-limited components, and
-- scheduled inspections so the app can report both fault HISTORY and UPCOMING
-- maintenance (remaining hours / remaining days).

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS discrepancies;
DROP TABLE IF EXISTS inspections;
DROP TABLE IF EXISTS aircraft_components;
DROP TABLE IF EXISTS components;
DROP TABLE IF EXISTS aircraft;

-- One row per airframe in the fleet.
CREATE TABLE aircraft (
    aircraft_id        INTEGER PRIMARY KEY,
    tail_number        TEXT    NOT NULL UNIQUE,   -- Army serial, e.g. 92-26471
    model              TEXT    NOT NULL,          -- UH-60A / UH-60L / UH-60M / HH-60M
    unit               TEXT    NOT NULL,          -- assigned unit
    airframe_hours     REAL    NOT NULL,          -- total accumulated airframe hours
    avg_monthly_hours  REAL    NOT NULL,          -- utilization rate, used to project due dates
    status             TEXT    NOT NULL           -- FMC / PMC / NMC readiness
);

-- Catalog of trackable component TYPES (the parts/systems we log against).
CREATE TABLE components (
    component_id   INTEGER PRIMARY KEY,
    component_name TEXT NOT NULL UNIQUE,
    category       TEXT NOT NULL                  -- Drivetrain / Rotor System / Powerplant / ...
);

-- A specific component installed on a specific aircraft, with time/life tracking.
-- Drives "remaining hours" to retirement / time-between-overhaul.
CREATE TABLE aircraft_components (
    id                INTEGER PRIMARY KEY,
    aircraft_id       INTEGER NOT NULL,
    component_id      INTEGER NOT NULL,
    serial_number     TEXT    NOT NULL,
    hours_since_new   REAL    NOT NULL,
    life_limit_hours  REAL    NOT NULL,           -- TBO / retirement life
    install_date      TEXT    NOT NULL,
    FOREIGN KEY (aircraft_id)  REFERENCES aircraft(aircraft_id),
    FOREIGN KEY (component_id) REFERENCES components(component_id)
);

-- Scheduled inspections per aircraft. An inspection may be driven by flight
-- hours, by calendar days, or both. Drives "remaining hours / remaining days".
CREATE TABLE inspections (
    id              INTEGER PRIMARY KEY,
    aircraft_id     INTEGER NOT NULL,
    inspection_type TEXT    NOT NULL,
    interval_hours  REAL,                          -- NULL if purely calendar based
    hours_at_last   REAL,                          -- airframe hours at last completion
    interval_days   INTEGER,                       -- NULL if purely hours based
    date_last       TEXT,                          -- date of last completion (ISO)
    FOREIGN KEY (aircraft_id) REFERENCES aircraft(aircraft_id)
);

-- Fault / discrepancy history (the maintenance log).
CREATE TABLE discrepancies (
    record_id         INTEGER PRIMARY KEY,
    aircraft_id       INTEGER NOT NULL,
    component_id      INTEGER NOT NULL,
    date              TEXT    NOT NULL,
    discrepancy_text  TEXT    NOT NULL,
    corrective_action TEXT    NOT NULL,
    downtime_hours    REAL    NOT NULL,
    status            TEXT    NOT NULL,            -- Open / Closed
    FOREIGN KEY (aircraft_id)  REFERENCES aircraft(aircraft_id),
    FOREIGN KEY (component_id) REFERENCES components(component_id)
);

-- Indexes for the analytics/search queries the app runs most.
CREATE INDEX idx_disc_aircraft  ON discrepancies(aircraft_id);
CREATE INDEX idx_disc_component ON discrepancies(component_id);
CREATE INDEX idx_disc_text      ON discrepancies(discrepancy_text);
CREATE INDEX idx_ac_aircraft    ON aircraft_components(aircraft_id);
CREATE INDEX idx_insp_aircraft  ON inspections(aircraft_id);
