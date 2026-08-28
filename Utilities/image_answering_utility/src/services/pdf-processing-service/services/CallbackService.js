const axios = require('axios');
const logger = require('../utils/logger');
const config = require('../config/serviceConfig');
const { FileStatus } = require('../models/FileStatus');

class CallbackService {
    constructor() {
        this.client = axios.create({
            headers: {
                'Content-Type': 'application/json'
            }
        });
    }

    async sendCallback(filename, s3Url, success = true, error = null, uniqueId) {
        const status = success ? "completed" : "failed";
        const callbackData = {
            filename,
            uniqueId,
            status,
            timestamp: new Date().toISOString(),
            s3_url: s3Url,
            error: error
        };

        // Update MongoDB status
        try {
            await FileStatus.findOneAndUpdate(
                { uniqueId },
                { 
                    status,
                    s3Url,
                    error,
                    filename
                },
                { upsert: true }
            );
            logger.info(`MongoDB status updated for ${filename} (ID: ${uniqueId})`);
        } catch (dbError) {
            logger.error(`Failed to update MongoDB status for ${filename} (ID: ${uniqueId}): ${dbError.message}`);
        }

        // Send callback to external service
        for (let attempt = 1; attempt <= config.callbackRetries; attempt++) {
            try {
                const response = await this.client.post(
                    config.callbackServiceUrl,
                    callbackData
                );
                
                if (response.status === 200) {
                    logger.info(`Callback sent successfully for ${filename} (ID: ${uniqueId})`);
                    return;
                }
            } catch (error) {
                logger.warn(`Callback attempt ${attempt} failed for ${filename} (ID: ${uniqueId}): ${error.message}`);
                if (attempt < config.callbackRetries) {
                    await new Promise(resolve => setTimeout(resolve, config.callbackRetryDelay));
                }
            }
        }
        
        logger.error(`All callback attempts failed for ${filename} (ID: ${uniqueId})`);
    }
}

module.exports = { CallbackService }; 