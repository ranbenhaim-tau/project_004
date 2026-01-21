USE FLYTAU;

-- Query 1 - Average Occupancy of Completed Flights: -------

SELECT 
    AVG(CAST(occupied_count AS REAL) / total_seats) * 100 AS average_occupancy_percentage
FROM (
    SELECT 
        f.ID,
        (SELECT COUNT(*) FROM SEAT s WHERE s.Airplane_ID = f.Airplane_ID) AS total_seats,
        (SELECT COUNT(*)
             FROM TICKET_ORDER to1
             JOIN `ORDER` o1 ON o1.ID = to1.Order_ID
            WHERE to1.Flight_ID = f.ID
              AND o1.Status = 'Completed') AS occupied_count
    FROM 
        FLIGHT AS f
    WHERE 
        f.Status = 'Completed'
) AS flight_data;


-- Query 2 - Revenue by Aircraft Size, Manufacturer and Class: -------

SELECT 
    a.Size, 
    a.Manufacturer, 
    t.CLASS_Type, 
    SUM(t.Price) AS Total_Income
FROM
    TICKET_ORDER AS to1
JOIN
    TICKET AS t
      ON t.Airplane_ID = to1.Airplane_ID
     AND t.Flight_ID = to1.Flight_ID
     AND t.SEAT_Row_num = to1.SEAT_Row_num
     AND t.SEAT_Column_number = to1.SEAT_Column_number
     AND t.CLASS_Type = to1.CLASS_Type
JOIN
    AIRPLANE AS a ON t.Airplane_ID = a.ID
JOIN
    `ORDER` AS o ON to1.Order_ID = o.ID
WHERE o.Status IN ('Active','Completed')
GROUP BY 
    a.Size, 
    a.Manufacturer, 
    t.CLASS_Type
ORDER BY 
    a.Size, 
    a.Manufacturer, 
    t.CLASS_Type;

-- Query 3 - Accumulated Flight Hours of Employees by Flight Type (Long / Short) -------

WITH qualified_types AS (
    SELECT
        ID AS Aircrew_ID,
        'Short' AS Flight_Type
    FROM AIRCREW
    UNION ALL
    SELECT
        ID AS Aircrew_ID,
        'Long' AS Flight_Type
    FROM AIRCREW
    WHERE Training = TRUE
)
SELECT
    ac.ID,
    ac.First_name,
    ac.Last_name,
    qt.Flight_Type AS Flight_Type,
    COALESCE(ROUND(SUM(fr.Flight_duration) / 60.0, 2), 0) AS Total_Flight_Hours
FROM qualified_types AS qt
JOIN AIRCREW AS ac
    ON ac.ID = qt.Aircrew_ID
LEFT JOIN AIRCREW_ASSIGNMENT AS aa
    ON aa.Aircrew_ID = ac.ID
LEFT JOIN FLIGHT AS f
    ON f.ID = aa.Flight_ID
   AND f.Status = 'Completed'
   AND f.Type = qt.Flight_Type
LEFT JOIN FLIGHT_ROUTE AS fr
    ON f.Origin_airport = fr.Origin_airport
   AND f.Arrival_airport = fr.Arrival_airport
GROUP BY
    ac.ID, ac.First_name, ac.Last_name, qt.Flight_Type
ORDER BY
    ac.Last_name, ac.First_name, qt.Flight_Type;

-- Query 4 - Purchase Cancellation Rate by Month: ---
SELECT 
    strftime('%Y/%m', Date_of_purchase) AS Month,
    ROUND(
        (SUM(CASE WHEN Status IN ('Customer Cancellation') THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) * 100, 2
    ) AS Cancellation_Rate
FROM  
    `ORDER`
GROUP BY 
    strftime('%Y/%m', Date_of_purchase)
ORDER BY 
    Month;

-- Query 5 - Monthly Activity Summary for Each Aircraft in the Fleet ---

WITH MonthlyStats AS (
    SELECT 
        f.Airplane_ID,
        strftime('%Y-%m', f.Date_of_departure) AS Month,
        SUM(CASE WHEN f.Status = 'Completed' THEN 1 ELSE 0 END) AS Flights_Executed,
        SUM(CASE WHEN f.Status = 'Canceled' THEN 1 ELSE 0 END) AS Flights_Canceled,
        COUNT(DISTINCT CASE 
            WHEN f.Status = 'Completed' THEN DATE(f.Date_of_departure)
        END) AS Active_Days
    FROM 
        FLIGHT f
    GROUP BY 
        f.Airplane_ID, strftime('%Y-%m', f.Date_of_departure)
),
RouteRanking AS (
    SELECT 
        f.Airplane_ID,
        strftime('%Y-%m', f.Date_of_departure) AS Month,
        f.Origin_airport || '-' || f.Arrival_airport AS Route,
        COUNT(*) AS Route_Count,
        ROW_NUMBER() OVER (
            PARTITION BY f.Airplane_ID, strftime('%Y-%m', f.Date_of_departure) 
            ORDER BY COUNT(*) DESC
        ) AS rn
    FROM 
        FLIGHT f
    WHERE 
        f.Status = 'Completed'
    GROUP BY 
        f.Airplane_ID, strftime('%Y-%m', f.Date_of_departure), Route
)
SELECT 
    ms.Airplane_ID,
    ms.Month,
    ms.Flights_Executed,
    ms.Flights_Canceled,
    ROUND((ms.Active_Days / 30.0) * 100, 2) AS Utilization_Percentage,
    rr.Route AS Dominant_Route
FROM 
    MonthlyStats AS ms
LEFT JOIN 
    RouteRanking AS rr ON ms.Airplane_ID = rr.Airplane_ID 
                    AND ms.Month = rr.Month 
                    AND rr.rn = 1
ORDER BY 
    ms.Month, ms.Airplane_ID;
