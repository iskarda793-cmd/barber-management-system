-- Barber Management System: database schema (PostgreSQL)
-- Safe to run many times. The app also runs this file on startup.

CREATE TABLE IF NOT EXISTS barbers (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    phone       VARCHAR(30),
    specialty   VARCHAR(100),
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS services (
    id                SERIAL PRIMARY KEY,
    name              VARCHAR(100) NOT NULL,
    duration_minutes  INTEGER NOT NULL CHECK (duration_minutes > 0),
    price             NUMERIC(8, 2) NOT NULL CHECK (price >= 0),
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appointments (
    id                SERIAL PRIMARY KEY,
    customer_name     VARCHAR(100) NOT NULL,
    customer_phone    VARCHAR(30),
    barber_id         INTEGER NOT NULL REFERENCES barbers(id),
    service_id        INTEGER NOT NULL REFERENCES services(id),
    appointment_time  TIMESTAMP NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'scheduled'
                      CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    notes             TEXT,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_appointments_time ON appointments (appointment_time);
