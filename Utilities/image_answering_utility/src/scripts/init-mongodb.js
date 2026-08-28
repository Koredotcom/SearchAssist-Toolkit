const { exec } = require('child_process');
const logger = require('../services/pdf-processing-service/utils/logger');

function checkMongoDBService() {
    return new Promise((resolve, reject) => {
        // Check if MongoDB service is running
        exec('systemctl status mongodb || systemctl status mongod', (error, stdout, stderr) => {
            if (error) {
                logger.warn('MongoDB service is not running. Attempting to start...');
                startMongoDBService(resolve, reject);
            } else {
                logger.info('MongoDB service is running');
                resolve(true);
            }
        });
    });
}

function startMongoDBService(resolve, reject) {
    exec('sudo systemctl start mongodb || sudo systemctl start mongod', (error, stdout, stderr) => {
        if (error) {
            logger.error('Failed to start MongoDB service. Please install MongoDB:');
            logger.error('sudo apt update');
            logger.error('sudo apt install -y mongodb');
            logger.error('sudo systemctl enable mongodb');
            logger.error('sudo systemctl start mongodb');
            reject(error);
        } else {
            logger.info('MongoDB service started successfully');
            resolve(true);
        }
    });
}

async function init() {
    try {
        await checkMongoDBService();
        logger.info('MongoDB initialization completed');
    } catch (error) {
        logger.error('MongoDB initialization failed:', error);
        process.exit(1);
    }
}

if (require.main === module) {
    init();
}

module.exports = { init }; 