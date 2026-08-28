const Queue = require('bull');
const ProcessingController = require('../services/pdf-processing-service/controllers/ProcessingController');
const { StorageManager } = require('../services/pdf-processing-service/utils/StorageManager');
const { createLogger } = require('../utils/logger');
const axios = require('axios');
const path = require('path');
const { promisify } = require('util');
const stream = require('stream');
const pipeline = promisify(stream.pipeline);
const { createWriteStream } = require('fs');
const fsSync = require('fs');
const extract = require('extract-zip');
const { exec } = require('child_process');
const util = require('util');
const execAsync = util.promisify(exec);
const fs = require('fs').promises;
require('dotenv').config({ path: path.join(__dirname, '../../config/.env') });
const ensureLogsDirectory = require('../utils/ensure-logs-dir');

// Initialize controllers and utilities
const processingController = new ProcessingController();
const storageManager = new StorageManager();

// Ensure logs directory exists
ensureLogsDirectory();

// Add DOWNLOADS_DIR constant at the top level
// const DOWNLOADS_DIR = path.join(__dirname, '../../', process.env.DOWNLOADS_DIR);

// Setup logger for queue service
const logger = createLogger('queue-service');

// Helper function to check if file is an archive
function isArchive(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    return ['.zip', '.tar', '.gz', '.tgz'].includes(ext);
}

// Helper function to extract archive
async function extractInPlace(archivePath, extractDir) {
    const ext = path.extname(archivePath).toLowerCase();
    
    if (ext === '.zip') {
        await extract(archivePath, { dir: extractDir });
    } else if (['.tar', '.gz', '.tgz'].includes(ext)) {
        await execAsync(`tar -xf "${archivePath}" -C "${extractDir}"`);
    }
}

// Helper function to download file
async function downloadFile(url, outputPath) {
    try {
        const response = await axios({
            method: 'GET',
            url: url,
            responseType: 'stream',
            maxBodyLength: Infinity,
            maxContentLength: Infinity,
            timeout: 0
        });

        await pipeline(response.data, createWriteStream(outputPath));
        logger.info(`File downloaded to: ${outputPath}`);
    } catch (error) {
        logger.error(`Error downloading file: ${error.message}`);
        throw error;
    }
}

// Create a processing queue with concurrency limit
const pdfQueue = new Queue('pdf-processing', {
    redis: {
        host: process.env.REDIS_HOST,
        port: parseInt(process.env.REDIS_PORT, 10)
    }
});

// Process URL type jobs
async function processUrlJob(job) {
    const { downloadUrl, include_base64, uniqueId } = job.data;
    
    // Log the uniqueId we're processing to track it
    logger.info(`Processing queued URL job with uniqueId: ${uniqueId}`);
    
    // Update status to processing in database before starting actual work
    try {
        const { FileRecord } = require('../services/pdf-processing-service/models/FileRecord');
        await FileRecord.findOneAndUpdate(
            { uniqueId },
            { 
                status: 'processing',
                lastUpdated: new Date()
            },
            { new: true }
        );
        logger.info(`Updated status to processing for queued job with uniqueId: ${uniqueId}`);
    } catch (error) {
        logger.error(`Failed to update status for ${uniqueId}: ${error.message}`);
    }
    
    const tempDir = await storageManager.createTempDirectory(uniqueId);
    
    try {
        // Clean the filename
        const url = new URL(downloadUrl);
        const cleanFileName = path.basename(url.pathname).split('?')[0];
        const downloadedFile = path.join(tempDir, cleanFileName);
        
        await downloadFile(downloadUrl, downloadedFile);
        
        if (isArchive(downloadedFile)) {
            await extractInPlace(downloadedFile, tempDir);
            await fs.unlink(downloadedFile);
        }
        
        // Pass the original uniqueId explicitly
        const pdfFiles = await storageManager.getAllPDFFiles(tempDir);
        
        let results;
        if (pdfFiles.length === 1) {
            const singlePDFPath = pdfFiles[0];
            const singleResult = await processingController.processSinglePDF(singlePDFPath, {
                include_base64,
                uniqueId  // Ensure uniqueId is passed correctly
            });
            results = [singleResult];
        } else {
            results = await processingController.processDirectory(tempDir, {
                include_base64,
                uniqueId  // Ensure uniqueId is passed correctly
            });
        }
        
        job.progress(100);
        
        logger.info(`Completed URL job with uniqueId: ${uniqueId}`);
        return {
            status: 'completed',
            uniqueId, // Return the uniqueId in the result
            successful: results.filter(r => r.success).length,
            failed: results.filter(r => !r.success).length
        };
    } finally {
        await storageManager.cleanup(tempDir);
    }
}

// Process local directory type jobs
async function processLocalDirectoryJob(job) {
    const { directoryPath, include_base64, uniqueId } = job.data;
    
    // Log the uniqueId we're processing to track it
    logger.info(`Processing queued local directory job with uniqueId: ${uniqueId}`);
    
    // Update status to processing in database before starting actual work
    try {
        const { FileRecord } = require('../services/pdf-processing-service/models/FileRecord');
        await FileRecord.findOneAndUpdate(
            { uniqueId },
            { 
                status: 'processing',
                lastUpdated: new Date()
            },
            { new: true }
        );
        logger.info(`Updated status to processing for queued job with uniqueId: ${uniqueId}`);
    } catch (error) {
        logger.error(`Failed to update status for ${uniqueId}: ${error.message}`);
    }
    
    const results = await processingController.processDirectory(directoryPath, {
        include_base64,
        uniqueId // Ensure uniqueId is passed correctly
    });
    
    job.progress(100);
    
    logger.info(`Completed local directory job with uniqueId: ${uniqueId}`);
    return {
        status: 'completed',
        uniqueId, // Return the uniqueId in the result
        successful: results.filter(r => r.success).length,
        failed: results.filter(r => !r.success).length
    };
}

// Set maximum concurrent jobs from environment variable
// But limit to 1 for PDF processing to ensure sequential processing
const MAX_CONCURRENCY = Math.min(parseInt(process.env.QUEUE_CONCURRENCY, 10) || 1, 1);
logger.info(`Setting queue concurrency to ${MAX_CONCURRENCY} to ensure sequential processing`);

pdfQueue.process(MAX_CONCURRENCY, async (job) => {
    try {
        logger.info(`Processing queued job ${job.id}`);

        if (job.data.type === 'local_directory') {
            return await processLocalDirectoryJob(job);
        } else if (job.data.type === 'url') {
            return await processUrlJob(job);
        } else {
            throw new Error(`Unknown job type: ${job.data.type}`);
        }
    } catch (error) {
        logger.error(`Queue job ${job.id} failed: ${error.message}`);
        throw error;
    }
});

// Log queue events
pdfQueue.on('completed', (job, result) => {
    logger.info(`Job ${job.id} completed. Success: ${result.successful}, Failed: ${result.failed}, UniqueId: ${result.uniqueId || job.data.uniqueId || 'unknown'}`);
});

pdfQueue.on('failed', (job, error) => {
    logger.error(`Job ${job.id} failed: ${error.message}`);
});

pdfQueue.on('stalled', (job) => {
    logger.warn(`Job ${job.id} stalled`);
});

// Export the utility functions along with pdfQueue
module.exports = { 
    pdfQueue,
    downloadFile,
    isArchive,
    extractInPlace
};
