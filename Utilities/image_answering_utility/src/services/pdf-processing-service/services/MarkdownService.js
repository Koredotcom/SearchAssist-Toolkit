const FormData = require('form-data');
const { createReadStream } = require('fs');
const axios = require('axios');
const logger = require('../utils/logger');
const config = require('../config/serviceConfig');
const { withRetry } = require('../utils/retryUtils');

class MarkdownService {
    constructor() {
        this.client = axios.create({
            timeout: config.requestTimeout,
            maxBodyLength: Infinity,
            maxContentLength: Infinity
        });
    }

    async processFile(filePath, uniqueId) {
        let fileStream = null;
        const filename = require('path').basename(filePath);

        try {
            // Wrap the entire processing logic in retry mechanism
            return await withRetry(
                async () => {
                    // Create a new form and stream for each attempt
                    if (fileStream) {
                        fileStream.destroy();
                    }
                    
                    fileStream = createReadStream(filePath);
                    const formData = new FormData();
                    
                    // Handle stream errors
                    fileStream.on('error', (error) => {
                        logger.error(`[${uniqueId}] Stream error for ${filename}: ${error.message}`);
                        fileStream.destroy();
                        throw error;
                    });

                    formData.append('file', fileStream, {
                        filename: filename,
                        contentType: 'application/pdf'
                    });

                    logger.info(`[${uniqueId}] Sending PDF to markdown service: ${filename}`);
                    
                    const response = await this.client.post(config.markdownServiceUrl, formData, {
                        headers: {
                            ...formData.getHeaders(),
                            'Accept': 'application/json',
                            'Connection': 'keep-alive'
                        },
                        validateStatus: status => status >= 200 && status < 500,
                        timeout: config.requestTimeout || 300000, // 5 minutes default
                    });

                    if (response.status !== 200) {
                        throw new Error(`Markdown service error (${response.status}): ${JSON.stringify(response.data)}`);
                    }

                    logger.info(`[${uniqueId}] Successfully processed markdown for: ${filename}`);
                    return response.data;
                },
                {
                    maxRetries: 3,
                    initialDelay: 2000, // Start with 2 seconds delay
                    maxDelay: 10000,    // Max 10 seconds delay
                    shouldRetry: (error) => {
                        // Retry on connection errors and 5xx server errors
                        const isConnectionError = error.code === 'ECONNREFUSED' || 
                                                error.code === 'ECONNRESET' || 
                                                error.code === 'ETIMEDOUT';
                        const isServerError = error.response?.status >= 500;
                        const isRetryable = isConnectionError || isServerError;
                        
                        if (isRetryable) {
                            logger.info(`[${uniqueId}] Error is retryable: ${error.message}`);
                        }
                        return isRetryable;
                    }
                }
            );
        } catch (error) {
            logger.error(`[${uniqueId}] Error in markdown processing for ${filename}: ${error.message}`);
            if (error.response?.data) {
                logger.error(`[${uniqueId}] Response data: ${JSON.stringify(error.response.data)}`);
            }
            throw new Error(`Markdown processing failed: ${error.message}`);
        } finally {
            if (fileStream) {
                fileStream.destroy();
            }
        }
    }
}

module.exports = { MarkdownService }; 