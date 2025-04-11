const path = require('path');
const crypto = require('crypto');
const logger = require('./logger');
const { FileRecord } = require('../models/FileRecord');
const { MongoManager } = require('./MongoManager');
const mongoose = require('mongoose');

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
            
            // First check if record already exists with processing status
            const existingRecord = await FileRecord.findOne({ uniqueId });
            
            if (existingRecord && existingRecord.status === 'processing') {
                // Record already exists with processing status, just update lastUpdated
                logger.info(`File ${filename} (ID: ${uniqueId}) already in processing state, continuing processing`);
                await FileRecord.findOneAndUpdate(
                    { uniqueId },
                    {
                        lastUpdated: new Date()
                    },
                    { new: true }
                );
                return existingRecord;
            }
            
            // Otherwise create or update record with processing status
            const record = await FileRecord.findOneAndUpdate(
                { uniqueId },
                {
                    filename,
                    filePath,
                    status: 'processing',
                    startTime: new Date(),
                    lastUpdated: new Date()
                },
                { 
                    upsert: true,
                    new: true,
                    setDefaultsOnInsert: true
                }
            );
            
            logger.info(`Tracking file: ${filename} (ID: ${uniqueId})`);
            return record;
        } catch (error) {
            logger.error(`Error tracking file ${filename}: ${error.message}`);
            throw error;
        }
    }

    async updateStatus(uniqueId, status, additionalData = {}) {
        try {
            await MongoManager.reconnectIfNeeded();
            
            const updateData = {
                status,
                lastUpdated: new Date(),
                ...additionalData
            };
            
            if (status === 'completed') {
                updateData.completedTime = new Date();
            }
            
            const record = await FileRecord.findOneAndUpdate(
                { uniqueId },
                updateData,
                { new: true }
            );
            
            if (!record) {
                throw new Error(`No record found for ID: ${uniqueId}`);
            }
            
            logger.info(`Updated status for ${uniqueId} to ${status}`);
            return record;
        } catch (error) {
            logger.error(`Error updating status for ${uniqueId}: ${error.message}`);
            throw error;
        }
    }

    async getStatus(uniqueId) {
        try {
            await MongoManager.reconnectIfNeeded();
            return await FileRecord.findOne({ uniqueId });
        } catch (error) {
            logger.error(`Error getting status for ${uniqueId}: ${error.message}`);
            throw error;
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
