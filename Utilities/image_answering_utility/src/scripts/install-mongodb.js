const { exec } = require('child_process');
const util = require('util');
const execAsync = util.promisify(exec);
const logger = require('../services/pdf-processing-service/utils/logger');

async function installMongoDB() {
    try {
        // Import MongoDB public GPG key
        logger.info('Importing MongoDB public GPG key...');
        await execAsync('curl -fsSL https://pgp.mongodb.com/server-6.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-6.0.gpg --dearmor');

        // Create list file for MongoDB
        logger.info('Creating MongoDB list file...');
        const release = await execAsync('lsb_release -c -s');
        const codename = release.stdout.trim();
        
        const repoLine = `deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu ${codename}/mongodb-org/6.0 multiverse`;
        await execAsync(`echo "${repoLine}" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list`);

        // Update package list
        logger.info('Updating package list...');
        await execAsync('sudo apt-get update');

        // Install MongoDB
        logger.info('Installing MongoDB...');
        await execAsync('sudo apt-get install -y mongodb-org');

        // Start MongoDB service
        logger.info('Starting MongoDB service...');
        await execAsync('sudo systemctl start mongod');

        // Enable MongoDB service
        logger.info('Enabling MongoDB service...');
        await execAsync('sudo systemctl enable mongod');

        logger.info('MongoDB installation completed successfully');
        
        // Verify MongoDB is running
        const status = await execAsync('sudo systemctl status mongod');
        logger.info('MongoDB Status:', status.stdout);

    } catch (error) {
        logger.error('Error installing MongoDB:', error.message);
        throw error;
    }
}

async function init() {
    try {
        await installMongoDB();
    } catch (error) {
        logger.error('MongoDB installation failed');
        process.exit(1);
    }
}

if (require.main === module) {
    init();
}

module.exports = { installMongoDB }; 