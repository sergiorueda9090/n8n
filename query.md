1. Clientes con 0 a 3 días de mora
SELECT
    c.nombre_completo AS nombre,
    c.telefono,
    s.saldo_total AS monto,
    s.fecha_vencimiento
FROM clientes c
INNER JOIN saldo s
    ON s.id_cliente = c.id
WHERE CURRENT_DATE - s.fecha_vencimiento BETWEEN 0 AND 3;   


2. Clientes con 4 a 7 días de mora
SELECT
    c.nombre_completo AS nombre,
    c.telefono,
    s.saldo_total AS monto,
    s.fecha_vencimiento
FROM clientes c
INNER JOIN saldo s
    ON s.id_cliente = c.id
WHERE CURRENT_DATE - s.fecha_vencimiento BETWEEN 4 AND 7;

3. Clientes con 8 a 15 días de mora
SELECT
    c.nombre_completo AS nombre,
    c.telefono,
    s.saldo_total AS monto,
    s.fecha_vencimiento
FROM clientes c
INNER JOIN saldo s
    ON s.id_cliente = c.id
WHERE CURRENT_DATE - s.fecha_vencimiento BETWEEN 8 AND 15;


4. Clientes con más de 31 días de mora
SELECT
    c.nombre_completo AS nombre,
    c.telefono,
    s.saldo_total AS monto,
    s.fecha_vencimiento
FROM clientes c
INNER JOIN saldo s
    ON s.id_cliente = c.id
WHERE CURRENT_DATE - s.fecha_vencimiento > 31;