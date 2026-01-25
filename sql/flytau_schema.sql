/* SQLite Schema */
PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS `AIRCREW_ASSIGNMENT`;
DROP TABLE IF EXISTS `TICKET_ORDER`;
DROP TABLE IF EXISTS `TICKET`;
DROP TABLE IF EXISTS `FLIGHT`;
DROP TABLE IF EXISTS `SEAT`;
DROP TABLE IF EXISTS `CLASS`;
DROP TABLE IF EXISTS `AIRPLANE`;
DROP TABLE IF EXISTS `PHONE_NUMBER_MEMBER`;
DROP TABLE IF EXISTS `PHONE_NUMBER_GUEST`;
DROP TABLE IF EXISTS `ORDER`;
DROP TABLE IF EXISTS `MEMBER`;
DROP TABLE IF EXISTS `GUEST`;
DROP TABLE IF EXISTS `FLIGHT_ROUTE`;
DROP TABLE IF EXISTS `AIRCREW`;
DROP TABLE IF EXISTS `MANAGER`;

PRAGMA foreign_keys = ON;

CREATE TABLE `MANAGER` (
  `ID` TEXT NOT NULL,
  `City` TEXT NOT NULL,
  `Street` TEXT NOT NULL,
  `House_Number` TEXT NOT NULL,
  `Start_date_of_employment` TEXT NOT NULL,
  `First_name` TEXT NOT NULL,
  `Last_name` TEXT NOT NULL,
  `Phone_number` TEXT NOT NULL,
  `Password` TEXT NOT NULL,
  PRIMARY KEY (`ID`)
);

CREATE TABLE `AIRCREW` (
  `ID` INTEGER NOT NULL,
  `City` TEXT NOT NULL,
  `Street` TEXT NOT NULL,
  `House_Number` TEXT NOT NULL,
  `Start_date_of_employment` TEXT NOT NULL,
  `First_name` TEXT NOT NULL,
  `Last_name` TEXT NOT NULL,
  `Phone_number` TEXT NOT NULL,
  `Type` TEXT NOT NULL CHECK(`Type` IN ('Pilot','Flight attendant')),
  `Training` INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (`ID`)
);

CREATE TABLE `FLIGHT_ROUTE` (
  `Origin_airport` TEXT NOT NULL,
  `Arrival_airport` TEXT NOT NULL,
  `Flight_duration` INTEGER NOT NULL,
  PRIMARY KEY (`Origin_airport`, `Arrival_airport`),
  CHECK (`Flight_duration` > 0)
);

CREATE TABLE `GUEST` (
  `Email` TEXT NOT NULL,
  `First_name_in_English` TEXT NOT NULL,
  `Last_name_in_English` TEXT NOT NULL,
  PRIMARY KEY (`Email`)
);

CREATE TABLE `MEMBER` (
  `Email` TEXT NOT NULL,
  `First_name_in_English` TEXT NOT NULL,
  `Last_name_in_English` TEXT NOT NULL,
  `Passport_number` TEXT NOT NULL,
  `Date_of_birth` TEXT NOT NULL,
  `Register_date` TEXT NOT NULL,
  `Password` TEXT NOT NULL,
  PRIMARY KEY (`Email`)
);

CREATE TABLE `ORDER` (
  `ID` INTEGER NOT NULL,
  `Status` TEXT NOT NULL CHECK(`Status` IN ('Active','Completed','Customer Cancellation','System Cancellation')),
  `Total_price` REAL NOT NULL,
  `Date_of_purchase` TEXT NOT NULL,
  `Cancellation_fee` REAL NOT NULL DEFAULT 0,
  `GUEST_Email` TEXT NULL, 
  `MEMBER_Email` TEXT NULL, 
  FOREIGN KEY (`GUEST_Email`) REFERENCES `GUEST`(`Email`) ON UPDATE CASCADE,
  FOREIGN KEY (`MEMBER_Email`) REFERENCES `MEMBER`(`Email`) ON UPDATE CASCADE,
  PRIMARY KEY (`ID`)
);

CREATE TABLE `PHONE_NUMBER_GUEST` (
  `Email` TEXT NOT NULL,
  `Phone_number` TEXT NOT NULL,
  PRIMARY KEY (`Email`, `Phone_number`),
  FOREIGN KEY (`Email`) REFERENCES `GUEST`(`Email`) ON UPDATE CASCADE
);

CREATE TABLE `PHONE_NUMBER_MEMBER` (
  `Email` TEXT NOT NULL,
  `Phone_number` TEXT NOT NULL,
  PRIMARY KEY (`Email`, `Phone_number`),
  FOREIGN KEY (`Email`) REFERENCES `MEMBER`(`Email`) ON UPDATE CASCADE
);

CREATE TABLE `AIRPLANE` (
  `ID` INTEGER NOT NULL,
  `Date_of_purchase` TEXT NOT NULL,
  `Manufacturer` TEXT NOT NULL CHECK(`Manufacturer` IN ('Boeing','Airbus','Dassault')),
  `Size` TEXT NOT NULL CHECK(`Size` IN ('Big','Small')),
  PRIMARY KEY (`ID`)
);

CREATE TABLE `CLASS` (
  `Type` TEXT NOT NULL CHECK(`Type` IN ('First','Regular')),
  `Airplane_ID` INTEGER NOT NULL,
  `Number_of_rows` INTEGER NOT NULL,
  `Number_of_columns` INTEGER NOT NULL,
  PRIMARY KEY (`Airplane_ID`, `Type`),
  FOREIGN KEY (`Airplane_ID`) REFERENCES `AIRPLANE`(`ID`) ON UPDATE CASCADE,
  CHECK (`Number_of_rows` > 0 AND `Number_of_columns` > 0)
);

CREATE TABLE `SEAT` (
  `Class_Type` TEXT NOT NULL CHECK(`Class_Type` IN ('First','Regular')),
  `Airplane_ID` INTEGER NOT NULL,
  `Row_num` INTEGER NOT NULL,
  `Column_number` TEXT NOT NULL,
  PRIMARY KEY (`Airplane_ID`, `Class_Type`, `Row_num`, `Column_number`),
  FOREIGN KEY (`Airplane_ID`, `Class_Type`) REFERENCES `CLASS`(`Airplane_ID`, `Type`) ON UPDATE CASCADE,
  CHECK (`Column_number` BETWEEN 'A' AND 'Z'),
  CHECK (`Row_num` > 0)
);

CREATE TABLE `FLIGHT` (
  `ID` TEXT NOT NULL,
  `Date_of_departure` TEXT NOT NULL,
  `Time_of_departure` TEXT NOT NULL,
  `Status` TEXT NOT NULL DEFAULT 'Active' CHECK(`Status` IN ('Active','Full','Completed','Canceled')),
  `Arrival_date` TEXT NOT NULL,
  `Arrival_time` TEXT NOT NULL,
  `Type` TEXT NOT NULL CHECK(`Type` IN ('Long','Short')),
  `Airplane_ID` INTEGER NOT NULL,
  `Origin_airport` TEXT NOT NULL,
  `Arrival_airport` TEXT NOT NULL,
  PRIMARY KEY (`ID`),
  FOREIGN KEY (`Airplane_ID`) REFERENCES `AIRPLANE`(`ID`) ON UPDATE CASCADE,
  FOREIGN KEY (`Origin_airport`,`Arrival_airport`) REFERENCES `FLIGHT_ROUTE`(`Origin_airport`,`Arrival_airport`) ON UPDATE CASCADE
);

CREATE TABLE `TICKET` (
  `Airplane_ID` INTEGER NOT NULL,
  `Flight_ID` TEXT NOT NULL,
  `SEAT_Row_num` INTEGER NOT NULL,
  `SEAT_Column_number` TEXT NOT NULL,
  `CLASS_Type` TEXT NOT NULL CHECK(`CLASS_Type` IN ('First','Regular')),
  `Price` REAL NOT NULL,
  `Availability` INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (`Airplane_ID`,`Flight_ID`,`SEAT_Row_num`,`SEAT_Column_number`,`CLASS_Type`),
  FOREIGN KEY (`Airplane_ID`, `CLASS_Type`, `SEAT_Row_num`, `SEAT_Column_number`)
    REFERENCES `SEAT`(`Airplane_ID`, `Class_Type`, `Row_num`, `Column_number`)
    ON UPDATE CASCADE,
  FOREIGN KEY (`Flight_ID`) REFERENCES `FLIGHT`(`ID`)
    ON UPDATE CASCADE
);

CREATE TABLE `TICKET_ORDER` (
  `Airplane_ID` INTEGER NOT NULL,
  `Flight_ID` TEXT NOT NULL,
  `SEAT_Row_num` INTEGER NOT NULL,
  `SEAT_Column_number` TEXT NOT NULL,
  `CLASS_Type` TEXT NOT NULL CHECK(`CLASS_Type` IN ('First','Regular')),
  `Order_ID` INTEGER NOT NULL,
  PRIMARY KEY (`Airplane_ID`,`Flight_ID`,`SEAT_Row_num`,`SEAT_Column_number`,`CLASS_Type`,`Order_ID`),
  FOREIGN KEY (`Airplane_ID`,`Flight_ID`,`SEAT_Row_num`,`SEAT_Column_number`,`CLASS_Type`)
    REFERENCES `TICKET`(`Airplane_ID`,`Flight_ID`,`SEAT_Row_num`,`SEAT_Column_number`,`CLASS_Type`)
    ON UPDATE CASCADE,
  FOREIGN KEY (`Order_ID`)
    REFERENCES `ORDER`(`ID`)
    ON UPDATE CASCADE
);

CREATE TABLE `AIRCREW_ASSIGNMENT` (
  `Aircrew_ID` INTEGER NOT NULL,
  `Flight_ID` TEXT NOT NULL,
  PRIMARY KEY (`Aircrew_ID`, `Flight_ID`),
  FOREIGN KEY (`Aircrew_ID`) REFERENCES `AIRCREW`(`ID`) ON UPDATE CASCADE,
  FOREIGN KEY (`Flight_ID`) REFERENCES `FLIGHT`(`ID`) ON UPDATE CASCADE
);

/* Performance Indices */
CREATE INDEX IF NOT EXISTS idx_ticket_flight_id ON TICKET(Flight_ID);
CREATE INDEX IF NOT EXISTS idx_flight_date ON FLIGHT(Date_of_departure);
CREATE INDEX IF NOT EXISTS idx_flight_origin ON FLIGHT(Origin_airport);
CREATE INDEX IF NOT EXISTS idx_flight_dest ON FLIGHT(Arrival_airport);
CREATE INDEX IF NOT EXISTS idx_flight_status ON FLIGHT(Status);
CREATE INDEX IF NOT EXISTS idx_flight_airplane_dep ON FLIGHT(Airplane_ID, Date_of_departure, Time_of_departure);
CREATE INDEX IF NOT EXISTS idx_flight_airplane_arr ON FLIGHT(Airplane_ID, Arrival_date, Arrival_time);
CREATE INDEX IF NOT EXISTS idx_aircrew_assignment_aircrew ON AIRCREW_ASSIGNMENT(Aircrew_ID);
CREATE INDEX IF NOT EXISTS idx_aircrew_assignment_flight ON AIRCREW_ASSIGNMENT(Flight_ID);
