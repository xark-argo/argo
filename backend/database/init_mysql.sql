-- MySQL Database Setup Script for Argo
-- This script creates the database and user for Argo application

-- Create database
CREATE DATABASE IF NOT EXISTS argo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (adjust password as needed)
CREATE USER IF NOT EXISTS 'argo'@'localhost' IDENTIFIED BY 'argo';
CREATE USER IF NOT EXISTS 'argo'@'%' IDENTIFIED BY 'argo';

-- Grant privileges
GRANT ALL PRIVILEGES ON argo.* TO 'argo'@'localhost';
GRANT ALL PRIVILEGES ON argo.* TO 'argo'@'%';

-- Flush privileges
FLUSH PRIVILEGES;

-- Show databases to confirm
SHOW DATABASES;

-- Use the argo database
USE argo;

-- Show current user and database
SELECT USER(), DATABASE();