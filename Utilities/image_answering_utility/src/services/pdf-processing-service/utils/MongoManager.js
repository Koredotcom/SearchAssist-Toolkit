const mongoose = require('mongoose');
const logger = require('./logger');
const config = require('../../../config/mongodb-config');

class MongoManager {
    static async connect() {
        try {
            await mongoose.connect(config.uri, {
                serverSelectionTimeoutMS: 5000, // 5 second timeout
                socketTimeoutMS: 45000, // 45 second timeout
                family: 4 // Use IPv4, skip trying IPv6
            });
            logger.info('Successfully connected to MongoDB');
        } catch (error) {
            logger.error(`MongoDB connection error: ${error.message}`);
            // Don't throw error - allow app to function without DB
        }
    }

    static async disconnect() {
        try {
            await mongoose.disconnect();
            logger.info('Disconnected from MongoDB');
        } catch (error) {
            logger.error(`MongoDB disconnect error: ${error.message}`);
        }
    }

    static async isConnected() {
        return mongoose.connection.readyState === 1;
    }

    static async reconnectIfNeeded() {
        if (mongoose.connection.readyState !== 1) {
            await this.connect();
        }
    }
}

module.exports = { MongoManager }; 