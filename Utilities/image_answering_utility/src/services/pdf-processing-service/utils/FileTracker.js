const path = require('path');
const crypto = require('crypto');
const logger = require('./logger');
const { FileRecord } = require('../models/FileRecord');
const { MongoManager } = require('./MongoManager');

class FileTracker {
    constructor() {
        // Ensure MongoDB connection
        MongoManager.reconnectIfNeeded();
    }

    async generateUniqueId(filename) {
        const timestamp = Date.now();
        return `${filename.replace(/[^a-zA-Z0-9]/g, '_')}_${timestamp}`;
    }

    async trackFile(filename, filePath, uniqueId) {
        try {
            await MongoManager.reconnectIfNeeded();
            
            const record = new FileRecord({
                uniqueId,
                filename,
                filePath,
                status: 'processing',
                startTime: new Date()
            });

            await record.save();
            logger.info(`Tracking file: ${filename} (ID: ${uniqueId})`);
        } catch (error) {
            logger.error(`Error tracking file ${filename}: ${error.message}`);
            throw error;
        }
    }

    async updateStatus(uniqueId, status, details = {}) {
        try {
            await MongoManager.reconnectIfNeeded();
            
            const updateData = {
                status,
                lastUpdated: new Date(),
                ...details
            };

            if (status === 'completed' || status === 'failed') {
                updateData.completedTime = new Date();
            }

            const record = await FileRecord.findOneAndUpdate(
                { uniqueId },
                updateData,
                { new: true }
            );

            if (record) {
                logger.info(`Updated status for ${uniqueId} to ${status}`);
            }
        } catch (error) {
            logger.error(`Error updating status for ${uniqueId}: ${error.message}`);
            throw error;
        }
    }

    async getStatus(uniqueId) {
        try {
            await MongoManager.reconnectIfNeeded();
            
            const record = await FileRecord.findOne({ uniqueId });
            return record ? record.toObject() : null;
        } catch (error) {
            logger.error(`Error getting status for ${uniqueId}: ${error.message}`);
            return null;
        }
    }

    async cleanupOldRecords(maxAge = 7 * 24 * 60 * 60 * 1000) { // 7 days
        try {
            await MongoManager.reconnectIfNeeded();
            
            const cutoffDate = new Date(Date.now() - maxAge);
            const result = await FileRecord.deleteMany({
                lastUpdated: { $lt: cutoffDate }
            });

            logger.info(`Cleaned up ${result.deletedCount} old records`);
        } catch (error) {
            logger.error(`Error cleaning up records: ${error.message}`);
        }
    }
}

module.exports = { FileTracker }; 