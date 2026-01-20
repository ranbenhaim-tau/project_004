SET SQL_SAFE_UPDATES = 0;

DROP SCHEMA IF EXISTS `FLYTAU`;

CREATE SCHEMA IF NOT EXISTS `FLYTAU`;

USE FLYTAU;

CREATE TABLE `MANAGER` (
  `ID` VARCHAR(100) NOT NULL,
  `City` VARCHAR(50) NOT NULL,
  `Street` VARCHAR(50) NOT NULL,
  `House_Number` VARCHAR(50) NOT NULL,
  `Start_date_of_employment` DATE NOT NULL,
  `First_name` VARCHAR(20) NOT NULL,
  `Last_name` VARCHAR(20) NOT NULL,
  `Phone_number` VARCHAR(20) NOT NULL,
  `Password` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`ID`));

CREATE TABLE `AIRCREW` (
  `ID` INT NOT NULL,
  `City` VARCHAR(50) NOT NULL,
  `Street` VARCHAR(50) NOT NULL,
  `House_Number` VARCHAR(50) NOT NULL,
  `Start_date_of_employment` DATE NOT NULL,
  `First_name` VARCHAR(50) NOT NULL,
  `Last_name` VARCHAR(20) NOT NULL,
  `Phone_number` VARCHAR(20) NOT NULL,
  `Type` ENUM('Pilot','Flight attendant') NOT NULL,
  `Training` BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (`ID`));

CREATE TABLE `FLIGHT_ROUTE` (
  `Origin_airport` VARCHAR(3) NOT NULL,
  `Arrival_airport` VARCHAR(3) NOT NULL,
  `Flight_duration` INT NOT NULL, -- minutes
  PRIMARY KEY (`Origin_airport`, `Arrival_airport`),
  CHECK (Flight_duration > 0));

CREATE TABLE `GUEST` (
  `Email` VARCHAR(30) NOT NULL,
  `First_name_in_English` VARCHAR(50) NOT NULL,
  `Last_name_in_English` VARCHAR(50) NOT NULL,
  PRIMARY KEY (`Email`));

CREATE TABLE `MEMBER` (
  `Email` VARCHAR(30) NOT NULL,
  `First_name_in_English` VARCHAR(50) NOT NULL,
  `Last_name_in_English` VARCHAR(50) NOT NULL,
  `Passport_number` VARCHAR(30) NOT NULL,
  `Date_of_birth` DATE NOT NULL,
  `Register_date` DATE NOT NULL,
  `Password` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`Email`));

CREATE TABLE `ORDER` (
  `ID` INT NOT NULL,
  `Status` ENUM('Active','Completed','Customer Cancellation','System Cancellation') NOT NULL,
  `Total_price` DECIMAL(10,2) NOT NULL,
  `Date_of_purchase` DATE NOT NULL,
  `Cancellation_fee` DECIMAL(10,2) NOT NULL DEFAULT 0,
  `GUEST_Email` VARCHAR(30) NULL, 
  `MEMBER_Email` VARCHAR(30) NULL, 
  FOREIGN KEY (`GUEST_Email`) REFERENCES `GUEST`(`Email`)
  ON UPDATE CASCADE,
  FOREIGN KEY (`MEMBER_Email`) REFERENCES `MEMBER`(`Email`)
  ON UPDATE CASCADE,
  PRIMARY KEY (`ID`));

CREATE TABLE `PHONE_NUMBER_GUEST` (
  `Email` VARCHAR(30) NOT NULL,
  `Phone_number` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`Email`, `Phone_number`),
  FOREIGN KEY (`Email`) REFERENCES `GUEST`(`Email`)
  ON UPDATE CASCADE);

CREATE TABLE `PHONE_NUMBER_MEMBER` (
  `Email` VARCHAR(30) NOT NULL,
  `Phone_number` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`Email`, `Phone_number`),
  FOREIGN KEY (`Email`) REFERENCES `MEMBER`(`Email`)
  ON UPDATE CASCADE);

CREATE TABLE `AIRPLANE` (
  `ID` INT NOT NULL,
  `Date_of_purchase` DATE NOT NULL,
  `Manufacturer` ENUM('Boeing','Airbus','Dassault') NOT NULL,
  `Size` ENUM('Big','Small') NOT NULL,
  PRIMARY KEY (`ID`));

CREATE TABLE `CLASS` (
  `Type` ENUM('First','Regular') NOT NULL,
  `Airplane_ID` INT NOT NULL,
  `Number_of_rows` INT NOT NULL,
  `Number_of_columns` INT NOT NULL,
  PRIMARY KEY (`Airplane_ID`, `Type`),
  FOREIGN KEY (`Airplane_ID`) REFERENCES `AIRPLANE`(`ID`)
  ON UPDATE CASCADE,
  CHECK (Number_of_rows > 0 AND Number_of_columns > 0));

CREATE TABLE `SEAT` (
  `Class_Type` ENUM('First','Regular') NOT NULL,
  `Airplane_ID` INT NOT NULL,
  `Row_num` INT NOT NULL,
  `Column_number` CHAR(1) NOT NULL,
  PRIMARY KEY (`Airplane_ID`, `Class_Type`, `Row_num`, `Column_number`),
  FOREIGN KEY (`Airplane_ID`, `Class_Type`) REFERENCES `CLASS`(`Airplane_ID`, `Type`)
  ON UPDATE CASCADE,
  CHECK (Column_number BETWEEN 'A' AND 'Z'),
  CHECK (Row_num > 0));

CREATE TABLE `FLIGHT` (
  `ID` VARCHAR(10) NOT NULL,
  `Date_of_departure` DATE NOT NULL,
  `Time_of_departure` TIME NOT NULL,
  `Status` ENUM('Active','Full','Completed','Canceled') NOT NULL DEFAULT 'Active',
  `Arrival_date` DATE NOT NULL,
  `Arrival_time` TIME NOT NULL,
  `Type` ENUM('Long','Short') NOT NULL,
  `Airplane_ID` INT NOT NULL,
  `Origin_airport` VARCHAR(3) NOT NULL,
  `Arrival_airport` VARCHAR(3) NOT NULL,
  PRIMARY KEY (`ID`),
  FOREIGN KEY (`Airplane_ID`) REFERENCES `AIRPLANE`(`ID`)
  ON UPDATE CASCADE,
  FOREIGN KEY (`Origin_airport`,`Arrival_airport`) REFERENCES `FLIGHT_ROUTE`(`Origin_airport`,`Arrival_airport`)
  ON UPDATE CASCADE);

CREATE TABLE `TICKET` (
  `Airplane_ID` INT NOT NULL,
  `Flight_ID` VARCHAR(10) NOT NULL,
  `SEAT_Row_num` INT NOT NULL,
  `SEAT_Column_number` CHAR(1) NOT NULL,
  `CLASS_Type` ENUM('First','Regular') NOT NULL,
  `Price` DECIMAL(10,2) NOT NULL,
  `Availability` BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (`Airplane_ID`,`Flight_ID`,`SEAT_Row_num`,`SEAT_Column_number`,`CLASS_Type`),
  FOREIGN KEY (`Airplane_ID`, `CLASS_Type`, `SEAT_Row_num`, `SEAT_Column_number`)
    REFERENCES `SEAT`(`Airplane_ID`, `Class_Type`, `Row_num`, `Column_number`)
    ON UPDATE CASCADE,
  FOREIGN KEY (`Flight_ID`) REFERENCES `FLIGHT`(`ID`)
    ON UPDATE CASCADE
);


CREATE TABLE `TICKET_ORDER` (
  `Airplane_ID` INT NOT NULL,
  `Flight_ID` VARCHAR(10) NOT NULL,
  `SEAT_Row_num` INT NOT NULL,
  `SEAT_Column_number` CHAR(1) NOT NULL,
  `CLASS_Type` ENUM('First','Regular') NOT NULL,
  `Order_ID` INT NOT NULL,
  PRIMARY KEY (`Airplane_ID`,`Flight_ID`,`SEAT_Row_num`,`SEAT_Column_number`,`CLASS_Type`,`Order_ID`),
  INDEX `idx_ticket_order_order` (`Order_ID`),
  CONSTRAINT `fk_ticket_order_ticket` FOREIGN KEY (`Airplane_ID`,`Flight_ID`,`SEAT_Row_num`,`SEAT_Column_number`,`CLASS_Type`)
    REFERENCES `TICKET`(`Airplane_ID`,`Flight_ID`,`SEAT_Row_num`,`SEAT_Column_number`,`CLASS_Type`)
    ON UPDATE CASCADE,
  CONSTRAINT `fk_ticket_order_order` FOREIGN KEY (`Order_ID`)
    REFERENCES `ORDER`(`ID`)
    ON UPDATE CASCADE
);



CREATE TABLE `AIRCREW_ASSIGNMENT` (
  `Aircrew_ID` INT NOT NULL,
  `Flight_ID` VARCHAR(10) NOT NULL,
  PRIMARY KEY (`Aircrew_ID`, `Flight_ID`),
  FOREIGN KEY (`Aircrew_ID`) REFERENCES `AIRCREW`(`ID`)
  ON UPDATE CASCADE,
  FOREIGN KEY (`Flight_ID`) REFERENCES `FLIGHT`(`ID`)
ON UPDATE CASCADE);
