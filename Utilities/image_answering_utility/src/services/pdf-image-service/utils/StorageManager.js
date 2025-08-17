const fs = require('fs-extra');
const path = require('path');
const os = require('os');
const logger = require('./logger');

class StorageManager {
    constructor() {
        this.baseDir = this.initializeBaseDirectory();
        this.processingDir = path.join(this.baseDir, 'processing_pdf_images');
        this.initializeDirectories();
    }

    initializeBaseDirectory() {
        const projectBaseDir = path.join(__dirname, '../../../../storage');
        try {
            fs.mkdirSync(projectBaseDir, { recursive: true });
            return projectBaseDir;
        } catch (error) {
            logger.warn(`Failed to create project storage directory: ${error.message}`);
            const tempBaseDir = path.join(os.tmpdir(), 'pdf-processor');
            fs.mkdirSync(tempBaseDir, { recursive: true });
            return tempBaseDir;
        }
    }

    initializeDirectories() {
        try {
            fs.mkdirSync(this.processingDir, { recursive: true });
            logger.info('Storage directories initialized successfully');
        } catch (error) {
            logger.error(`Error initializing directories: ${error.message}`);
            throw error;
        }
    }

    async createTempDirectory(processId) {
        const tempDir = path.join(this.processingDir, processId);
        try {
            await fs.mkdir(tempDir, { recursive: true });
            logger.info(`Created temporary directory: ${tempDir}`);
            return tempDir;
        } catch (error) {
            logger.error(`Error creating temp directory: ${error.message}`);
            throw error;
        }
    }

    async cleanup(directory) {
        try {
            if (await fs.pathExists(directory)) {
                await fs.remove(directory);
                logger.info(`Cleaned up directory: ${directory}`);
                
                if (await fs.pathExists(directory)) {
                    logger.warn(`Directory still exists after cleanup: ${directory}`);
                    await fs.rm(directory, { recursive: true, force: true });
                }
            }
        } catch (error) {
            logger.error(`Cleanup error for ${directory}: ${error.message}`);
            throw error;
        }
    }

}

module.exports = { StorageManager }; 