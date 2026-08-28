const logger = require('./logger');

/**
 * Implements exponential backoff retry logic
 * @param {Function} operation - Function to retry
 * @param {Object} options - Retry options
 * @param {number} options.maxRetries - Maximum number of retry attempts
 * @param {number} options.initialDelay - Initial delay in milliseconds
 * @param {number} options.maxDelay - Maximum delay between retries
 * @param {Function} options.shouldRetry - Function to determine if error is retryable
 * @returns {Promise} - Resolves with operation result or rejects with error
 */
async function withRetry(operation, {
    maxRetries = 3,
    initialDelay = 1000,
    maxDelay = 10000,
    shouldRetry = () => true
} = {}) {
    let lastError;
    let delay = initialDelay;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            return await operation();
        } catch (error) {
            lastError = error;
            
            if (!shouldRetry(error) || attempt === maxRetries) {
                throw error;
            }

            logger.warn(`Operation failed, attempt ${attempt}/${maxRetries}. Error: ${error.message}`);
            logger.info(`Retrying in ${delay}ms...`);

            await new Promise(resolve => setTimeout(resolve, delay));
            // Exponential backoff with max delay cap
            delay = Math.min(delay * 2, maxDelay);
        }
    }

    throw lastError;
}

module.exports = {
    withRetry
}; 