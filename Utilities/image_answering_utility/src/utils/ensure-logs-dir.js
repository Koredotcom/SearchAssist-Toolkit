const fs = require('fs-extra');
const path = require('path');
require('dotenv').config();

function ensureLogsDirectory() {
    const logsDir = path.join(__dirname, '../../logs');
    try {
        fs.ensureDirSync(logsDir);
        process.env.LOGS_DIR = logsDir;
    } catch (error) {
        console.error(`Error creating logs directory: ${error.message}`);
        // Fallback to OS temp directory if project directory is not accessible
        const tempLogsDir = path.join(require('os').tmpdir(), 'pdf-processor-logs');
        fs.ensureDirSync(tempLogsDir);
        process.env.LOGS_DIR = tempLogsDir;
    }
}

module.exports = ensureLogsDirectory; 