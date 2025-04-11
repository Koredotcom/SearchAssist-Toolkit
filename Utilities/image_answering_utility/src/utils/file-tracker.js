const fs = require('fs').promises;
const path = require('path');
require('dotenv').config();

class FileTracker {
    constructor() {
        this.records = new Map();
        this.logFile = path.join(process.env.LOGS_DIR, 'file_processing_records.json');
    }

    generateUniqueId(filename) {
        return `${filename.replace('.pdf', '')}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    async trackFile(filename, originalPath, existingUniqueId = null) {
        const uniqueId = existingUniqueId || this.generateUniqueId(filename);
        const record = {
            uniqueId,
            filename,
            originalPath,
            startTime: new Date().toISOString(),
            status: 'processing',
            completedTime: null,
            error: null,
            s3Url: null
        };

        this.records.set(uniqueId, record);
        await this.saveRecords();
        return uniqueId;
    }

    async updateStatus(uniqueId, status, details = {}) {
        if (!this.records.has(uniqueId)) {
            throw new Error(`No record found for ID: ${uniqueId}`);
        }

        const record = this.records.get(uniqueId);
        record.status = status;
        record.completedTime = new Date().toISOString();

        if (details.error) {
            record.error = details.error;
        }
        if (details.s3Url) {
            record.s3Url = details.s3Url;
        }

        await this.saveRecords();
        return record;
    }

    getRecord(uniqueId) {
        return this.records.get(uniqueId);
    }

    async saveRecords() {
        const recordsArray = Array.from(this.records.values());
        await fs.writeFile(
            this.logFile,
            JSON.stringify(recordsArray, null, 2),
            'utf8'
        );
    }

    async loadRecords() {
        try {
            const data = await fs.readFile(this.logFile, 'utf8');
            const records = JSON.parse(data);
            this.records = new Map(
                records.map(record => [record.uniqueId, record])
            );
        } catch (error) {
            if (error.code !== 'ENOENT') {
                throw error;
            }
        }
    }
}

module.exports = new FileTracker(); 