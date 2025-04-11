const fs = require('fs-extra');
const path = require('path');
const os = require('os');
const logger = require('./logger');

class StorageManager {
    constructor() {
        this.baseDir = this.initializeBaseDirectory();
        this.processingDir = path.join(this.baseDir, 'processing_pdf');
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
            }
        } catch (error) {
            logger.warn(`Cleanup warning for ${directory}: ${error.message}`);
        }
    }

    async cleanupOldDirectories() {
        const MAX_AGE = 2 * 60 * 60 * 1000; // 2 hours
        const now = Date.now();

        try {
            const contents = await fs.readdir(this.processingDir);
            for (const item of contents) {
                const fullPath = path.join(this.processingDir, item);
                try {
                    const stats = await fs.stat(fullPath);
                    if (now - stats.mtimeMs > MAX_AGE) {
                        await fs.remove(fullPath);
                        logger.info(`Cleaned up old directory: ${fullPath}`);
                    }
                } catch (err) {
                    logger.warn(`Error checking directory ${fullPath}: ${err.message}`);
                }
            }
        } catch (err) {
            logger.error(`Error during cleanup: ${err.message}`);
            throw err;
        }
    }

    async getAllPDFFiles(dirPath) {
        let results = [];
        
        try {
            const items = await fs.readdir(dirPath);
            
            for (const item of items) {
                const fullPath = path.join(dirPath, item);
                const stat = await fs.stat(fullPath);
                
                if (stat.isDirectory()) {
                    // Recursively get files from subdirectory
                    logger.info(`Scanning directory: ${fullPath}`);
                    const subDirFiles = await this.getAllPDFFiles(fullPath);
                    results = results.concat(subDirFiles);
                } else if (item.toLowerCase().endsWith('.pdf')) {
                    // Add PDF file to results
                    results.push(fullPath);
                }
            }
        } catch (error) {
            logger.error(`Error scanning directory ${dirPath}: ${error.message}`);
            throw error;
        }
        
        return results;
    }
}

module.exports = { StorageManager }; 