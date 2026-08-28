const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../../../../config/.env') });

const config = {
    // Service URLs
    markdownServiceUrl: process.env.MARKDOWN_SERVICE_URL,
    callbackServiceUrl: process.env.CALLBACK_SERVICE_URL,

    // Processing configuration
    maxConcurrentFiles: parseInt(process.env.MAX_CONCURRENT_FILES, 10),
    maxRetries: parseInt(process.env.MAX_RETRIES, 10),
    retryDelay: parseInt(process.env.RETRY_DELAY, 10),
    requestTimeout: parseInt(process.env.REQUEST_TIMEOUT, 10),

    // Callback configuration
    callbackRetries: parseInt(process.env.CALLBACK_RETRIES, 10),
    callbackRetryDelay: parseInt(process.env.CALLBACK_RETRY_DELAY, 10),

    // Output configuration
    outputDir: path.join(__dirname, '../../../../output'),

    // Validate required configuration
    validate() {
        const required = [
            'markdownServiceUrl',
            'callbackServiceUrl',
            'maxConcurrentFiles',
            'maxRetries',
            'retryDelay',
            'requestTimeout'
        ];

        for (const key of required) {
            if (!this[key]) {
                throw new Error(`Missing required configuration: ${key}`);
            }
        }
    }
};

// Validate configuration on load
config.validate();

module.exports = config; 