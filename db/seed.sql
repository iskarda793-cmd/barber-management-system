-- Barber Management System: sample data
-- Run AFTER schema.sql. Each block only inserts if the table is empty.

INSERT INTO barbers (name, phone, specialty)
SELECT * FROM (VALUES
    ('Mehmet Yılmaz',   '+48 600 100 200', 'Classic cuts & hot towel shave'),
    ('Piotr Nowak',     '+48 600 300 400', 'Fades & modern styles'),
    ('Arda Işık',       '+48 600 500 600', 'Beard design')
) AS v(name, phone, specialty)
WHERE NOT EXISTS (SELECT 1 FROM barbers);

INSERT INTO services (name, duration_minutes, price)
SELECT * FROM (VALUES
    ('Haircut',             30, 60.00),
    ('Beard trim',          20, 40.00),
    ('Haircut + Beard',     50, 90.00),
    ('Hot towel shave',     30, 50.00),
    ('Kids haircut',        25, 45.00)
) AS v(name, duration_minutes, price)
WHERE NOT EXISTS (SELECT 1 FROM services);

INSERT INTO appointments (customer_name, customer_phone, barber_id, service_id, appointment_time, status, notes)
SELECT v.customer, v.phone, b.id, s.id, v.at, v.status, v.notes
FROM (VALUES
    ('Jan Kowalski',     '+48 501 111 222', 'Mehmet Yılmaz', 'Haircut',          CURRENT_DATE - 1 + TIME '15:00', 'completed', NULL),
    ('Anna Wiśniewska',  '+48 502 333 444', 'Piotr Nowak',   'Kids haircut',     CURRENT_DATE - 1 + TIME '16:30', 'completed', 'For her son'),
    ('Tomasz Zieliński', '+48 503 555 666', 'Arda Işık',     'Haircut + Beard',  CURRENT_DATE + 1 + TIME '10:00', 'scheduled', NULL),
    ('Kemal Demir',      '+48 504 777 888', 'Mehmet Yılmaz', 'Hot towel shave',  CURRENT_DATE + 1 + TIME '12:30', 'scheduled', 'First visit'),
    ('Marek Lewandowski','+48 505 999 000', 'Piotr Nowak',   'Beard trim',       CURRENT_DATE + 2 + TIME '09:30', 'scheduled', NULL),
    ('Ewa Kamińska',     '+48 506 123 456', 'Arda Işık',     'Haircut',          CURRENT_DATE + 3 + TIME '17:00', 'cancelled', 'Customer called to cancel')
) AS v(customer, phone, barber, service, at, status, notes)
JOIN barbers  b ON b.name = v.barber
JOIN services s ON s.name = v.service
WHERE NOT EXISTS (SELECT 1 FROM appointments);

-- Verify
SELECT a.id, a.customer_name, b.name AS barber, s.name AS service, a.appointment_time, a.status
FROM appointments a
JOIN barbers b  ON b.id = a.barber_id
JOIN services s ON s.id = a.service_id
ORDER BY a.appointment_time;
