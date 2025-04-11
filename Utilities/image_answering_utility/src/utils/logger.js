const winston = require('winston');
const path = require('path');
const fs = require('fs-extra');
require('dotenv').config({ path: path.join(__dirname, '../../config/.env') });

// Define log directory
const LOG_DIR = path.join(__dirname, '../../logs');

// Ensure logs directory exists
fs.ensureDirSync(LOG_DIR);

// Define log format
const logFormat = winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(({ timestamp, level, message, service }) => {
        return `${timestamp} [${service}] [${level.toUpperCase()}]: ${message}`;
    })
);

/**
 * Creates a logger instance for a specific service
 * @param {string} serviceName - Name of the service (e.g., 'pdf-processing', 'pdf-image')
 * @returns {winston.Logger} - Configured logger instance
 */
function createLogger(serviceName) {
    return winston.createLogger({
        level: process.env.LOG_LEVEL || 'info',
        format: logFormat,
        defaultMeta: { service: serviceName },
        transports: [
            // Error logs
            new winston.transports.File({
                filename: path.join(LOG_DIR, `${serviceName}-error.log`),
                level: 'error'
            }),
            // Combined logs
            new winston.transports.File({
                filename: path.join(LOG_DIR, `${serviceName}.log`)
            }),
            // Console output
            new winston.transports.Console({
                format: winston.format.combine(
                    winston.format.colorize(),
                    logFormat
                )
            })
        ]
    });
}

// Export the logger factory
module.exports = {
    createLogger,
    LOG_DIR
}; 