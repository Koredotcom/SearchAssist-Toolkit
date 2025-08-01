const fs = require('fs');
const path = require('path');

class Logger {
    constructor() {
        this.logDir = path.join(process.cwd(), 'logs');
        this.ensureLogDirectory();
    }

    ensureLogDirectory() {
        if (!fs.existsSync(this.logDir)) {
            fs.mkdirSync(this.logDir, { recursive: true });
        }

        const today = new Date();
        const date = today.toISOString().split('T')[0]; // Gets YYYY-MM-DD format
        this.currentLogFile = path.join(this.logDir, `${date}-crawler.log`);
    }

    formatMessage(level, message, meta = {}) {
        const timestamp = new Date().toISOString();
        const metaStr = Object.keys(meta).length ? JSON.stringify(meta) : '';
        return `[${timestamp}] ${level.toUpperCase()}: ${message} ${metaStr}\n`;
    }

    log(level, message, meta = {}) {
        const logEntry = this.formatMessage(level, message, meta);
        fs.appendFileSync(this.currentLogFile, logEntry);
        
        // Also log to console
        console.log(logEntry.trim());
    }

    info(message, meta = {}) {
        this.log('INFO', message, meta);
    }

    error(message, meta = {}) {
        this.log('ERROR', message, meta);
    }

    warn(message, meta = {}) {
        this.log('WARN', message, meta);
    }

    debug(message, meta = {}) {
        this.log('DEBUG', message, meta);
    }
}

// Create and export a singleton instance
const logger = new Logger();
module.exports = logger; 