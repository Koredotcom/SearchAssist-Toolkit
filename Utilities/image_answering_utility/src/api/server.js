const express = require('express');
const ProcessingController = require('../services/pdf-processing-service/controllers/ProcessingController');
const { pdfQueue } = require('../config/queue-config');
const { createLogger } = require('../utils/logger');
const path = require('path');
const axios = require('axios');
const fs = require('fs').promises;
const fsSync = require('fs');
const { promisify } = require('util');
const stream = require('stream');
const pipeline = promisify(stream.pipeline);
const extract = require('extract-zip');
const { exec } = require('child_process');
const util = require('util');
const execAsync = util.promisify(exec);
const { createWriteStream } = require('fs');
require('dotenv').config({ path: path.join(__dirname, '../../config/.env') });
const ensureLogsDirectory = require('../utils/ensure-logs-dir');
const { StorageManager } = require('../services/pdf-processing-service/utils/StorageManager');
const os = require('os');
const { FileStatus } = require('../services/pdf-processing-service/models/FileStatus');
const mongoose = require('mongoose');
const { MongoManager } = require('../services/pdf-processing-service/utils/MongoManager');

// Initialize controllers and utilities
const processingController = new ProcessingController();
const storageManager = new StorageManager();

// Ensure logs directory exists
ensureLogsDirectory();

const app = express();
app.use(express.json());

// Setup logger for API service
const logger = createLogger('api-service');

// Replace hardcoded values with environment variables
// const DOWNLOADS_DIR = path.join(__dirname, '../../', process.env.DOWNLOADS_DIR);
const PORT = process.env.PORT || 3000;

// // Create downloads directory if it doesn't exist
// if (!fsSync.existsSync(DOWNLOADS_DIR)) {
//     fsSync.mkdirSync(DOWNLOADS_DIR, { recursive: true });
// }

// Add MongoDB connection
MongoManager.connect()
    .then(() => {
        app.listen(PORT, () => {
            logger.info(`Server is running on port ${PORT}`);
        });
    })
    .catch(err => {
        logger.error('Failed to initialize MongoDB:', err);
        // Still start the server even if MongoDB fails
        app.listen(PORT, () => {
            logger.info(`Server is running on port ${PORT} (without MongoDB)`);
        });
    });

// Set up periodic cleanup of old directories (every 1 hour)
setInterval(async () => {
    try {
        await storageManager.cleanupOldDirectories();
    } catch (error) {
        logger.error(`Error during periodic cleanup: ${error.message}`);
    }
}, 60 * 60 * 1000); // 1 hour

// Update the processDirectoryFromUrl function to use the functions from queue-config
async function processDirectoryFromUrl(downloadUrl, include_base64, uniqueId) {
    const tempDir = await storageManager.createTempDirectory(uniqueId);
    
    try {
        // Clean the filename by removing query parameters
        const url = new URL(downloadUrl);
        const originalFileName = path.basename(url.pathname);
        const cleanFileName = originalFileName.split('?')[0];
        
        // Download file to temp directory with clean filename
        const downloadedFile = path.join(tempDir, cleanFileName);
        
        // Use the functions from queue-config module
        const { downloadFile, isArchive, extractInPlace } = require('../config/queue-config');
        await downloadFile(downloadUrl, downloadedFile);
        
        // If it's an archive, extract in the same directory
        if (isArchive(downloadedFile)) {
            await extractInPlace(downloadedFile, tempDir);
            await fs.unlink(downloadedFile);
        }
        
        // Retrieve all PDF files in the temp directory
        const pdfFiles = await storageManager.getAllPDFFiles(tempDir);
        
        let results;
        if (pdfFiles.length === 1) {
            const singlePDFPath = pdfFiles[0];
            const singleResult = await processingController.processSinglePDF(singlePDFPath, {
                include_base64,
                uniqueId
            });
            results = [singleResult];
        } else {
            results = await processingController.processDirectory(tempDir, {
                include_base64,
                uniqueId
            });
        }
        
        return results;
    } finally {
        await storageManager.cleanup(tempDir);
    }
}

// Track active processing count
let activeProcessingCount = 0;

// Function to check if system is overloaded
function isSystemOverloaded() {
    const MAX_CONCURRENT = parseInt(process.env.MAX_CONCURRENT_PROCESSING, 10) || 3;
    return activeProcessingCount >= MAX_CONCURRENT;
}

// Function to get accurate queue position
async function getQueuePosition(jobId) {
    const [activeJobs, waitingJobs] = await Promise.all([
        pdfQueue.getActive(),
        pdfQueue.getWaiting()
    ]);

    // Find position in waiting queue
    const position = waitingJobs.findIndex(job => job.id === jobId);
    
    if (position === -1) {
        // If not found in waiting queue, it might be active or completed
        return activeJobs.findIndex(job => job.id === jobId);
    }

    // Position is number of active jobs plus position in waiting queue
    return activeJobs.length + position;
}

// Middleware to log requests
app.use((req, res, next) => {
    logger.info(`${req.method} ${req.path} - ${req.ip}`);
    next();
});

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({ status: 'healthy' });
});

// Modified processing endpoint with queue support
app.post('/process-directory-from-url', async (req, res) => {
    try {
        const { downloadUrl, include_base64 = false } = req.body;

        if (!downloadUrl) {
            return res.status(400).json({
                status: 'error',
                message: 'Download URL is required'
            });
        }

        // Generate a unique ID that includes both timestamp and URL info
        const urlObj = new URL(downloadUrl);
        const filename = path.basename(urlObj.pathname).split('?')[0];
        const timestamp = Date.now();
        const uniqueId = `${filename.replace(/[^a-zA-Z0-9]/g, '_')}_${timestamp}`;

        // Check if system is overloaded
        if (isSystemOverloaded()) {
            logger.info(`System overloaded, queueing request for ${downloadUrl}`);
            
            // Add to queue with uniqueId
            const job = await pdfQueue.add({
                downloadUrl,
                include_base64,
                uniqueId,
                type: 'url'  // Add type to distinguish URL processing
            }, {
                attempts: 3,
                backoff: {
                    type: 'exponential',
                    delay: 5000
                }
            });

            // Get accurate queue position
            const [queuePosition, counts] = await Promise.all([
                getQueuePosition(job.id),
                pdfQueue.getJobCounts()
            ]);

            return res.json({
                status: 'queued',
                message: 'Request queued for processing',
                jobId: job.id,
                queuePosition: queuePosition,
                totalJobs: counts.active + counts.waiting,
                uniqueId
            });
        }

        // If system not overloaded, process immediately
        activeProcessingCount++;
        logger.info(`Starting download from: ${downloadUrl}`);
        
        // Send acknowledgment with uniqueId
        res.json({
            status: 'processing',
            message: 'PDF processing started',
            uniqueId
        });

        try {
            const results = await processDirectoryFromUrl(downloadUrl, include_base64, uniqueId);
            logger.info(`Processing completed for ${downloadUrl}`);
            logger.info(`Successful: ${results.filter(r => r.success).length}`);
            logger.info(`Failed: ${results.filter(r => !r.success).length}`);
        } finally {
            activeProcessingCount--;
        }

    } catch (error) {
        logger.error('Error in process-directory-from-url:', error);
        if (!res.headersSent) {
            res.status(500).json({
                status: 'error',
                message: error.message
            });
        }
    }
});

// Add queue status endpoint
app.get('/queue-status', async (req, res) => {
    try {
        const counts = await pdfQueue.getJobCounts();
        const activeJobs = await pdfQueue.getActive();
        const waitingJobs = await pdfQueue.getWaiting();

        res.json({
            status: 'success',
            activeProcessing: activeProcessingCount,
            queueCounts: counts,
            activeJobs: activeJobs.map(job => ({
                id: job.id,
                timestamp: job.timestamp,
                progress: job.progress()
            })),
            waitingJobs: waitingJobs.map(job => ({
                id: job.id,
                timestamp: job.timestamp
            }))
        });
    } catch (error) {
        res.status(500).json({
            status: 'error',
            message: error.message
        });
    }
});

// Enhanced processing status endpoint
app.get('/processing-status/:processingId', async (req, res) => {
    const { processingId } = req.params;

    try {
        // Get processing status from controller
        const status = await processingController.getProcessingStatus(processingId);

        // Check queue for this processing ID if no status found
        if (!status) {
            const jobs = await pdfQueue.getJobs();
            const queuedJob = jobs.find(job => job.data.uniqueId === processingId);

            if (queuedJob) {
                return res.json({
                    status: 'success',
                    processingStatus: {
                        processingId,
                        queueStatus: {
                            status: await queuedJob.getState(),
                            progress: await queuedJob.progress(),
                            position: await queuedJob.queue.getJobCounts()
                        }
                    }
                });
            }
        }

        res.json({
            status: 'success',
            processingStatus: status || { processingId, status: 'not_found' }
        });
    } catch (error) {
        res.status(500).json({
            status: 'error',
            message: error.message
        });
    }
});

// Add new endpoint for processing local directory
app.post('/process-local-directory', async (req, res) => {
    try {
        const { directoryPath, include_base64 = false } = req.body;

        if (!directoryPath) {
            return res.status(400).json({
                status: 'error',
                message: 'Directory path is required'
            });
        }

        // Validate if directory exists
        try {
            const stats = await fs.stat(directoryPath);
            if (!stats.isDirectory()) {
                return res.status(400).json({
                    status: 'error',
                    message: 'Provided path is not a directory'
                });
            }
        } catch (error) {
            return res.status(400).json({
                status: 'error',
                message: `Directory does not exist or is not accessible: ${error.message}`
            });
        }

        // Generate unique ID
        const uniqueId = `local_${Date.now()}`;

        // Check if system is overloaded
        if (isSystemOverloaded()) {
            logger.info(`System overloaded, queueing request for directory: ${directoryPath}`);
            
            // Add to queue
            const job = await pdfQueue.add({
                type: 'local_directory',
                directoryPath,
                include_base64,
                uniqueId
            }, {
                attempts: 3,
                backoff: {
                    type: 'exponential',
                    delay: 5000
                }
            });

            return res.json({
                status: 'queued',
                message: 'Request queued for processing',
                jobId: job.id,
                queuePosition: await pdfQueue.getJobCounts().then(counts => counts.waiting),
                uniqueId
            });
        }

        // If system not overloaded, process immediately
        activeProcessingCount++;
        logger.info(`Starting processing for directory: ${directoryPath}`);
        
        res.json({
            status: 'processing',
            message: 'Directory processing started',
            uniqueId
        });

        try {
            const results = await processingController.processDirectory(directoryPath, {
                include_base64,
                uniqueId
            });

            logger.info(`Processing completed for directory: ${directoryPath}`);
            logger.info(`Successful: ${results.filter(r => r.success).length}`);
            logger.info(`Failed: ${results.filter(r => !r.success).length}`);

        } finally {
            activeProcessingCount--;
        }

    } catch (error) {
        logger.error('Error in process-local-directory:', error);
        if (!res.headersSent) {
            res.status(500).json({
                status: 'error',
                message: error.message
            });
        }
    }
});

// Add new endpoint for file status
app.get('/file-status/:uniqueId', async (req, res) => {
    try {
        const { uniqueId } = req.params;
        
        const fileStatus = await FileStatus.findOne({ uniqueId });
        
        if (!fileStatus) {
            return res.status(404).json({
                status: 'error',
                message: 'File status not found'
            });
        }

        res.json({
            status: 'success',
            data: {
                uniqueId: fileStatus.uniqueId,
                filename: fileStatus.filename,
                status: fileStatus.status,
                s3Url: fileStatus.s3Url,
                error: fileStatus.error,
                createdAt: fileStatus.createdAt,
                updatedAt: fileStatus.updatedAt
            }
        });
    } catch (error) {
        logger.error('Error fetching file status:', error);
        res.status(500).json({
            status: 'error',
            message: 'Internal server error'
        });
    }
});

// Error handling middleware
app.use((err, req, res, next) => {
    logger.error(`Error: ${err.message}`);
    res.status(500).json({ error: 'Internal Server Error' });
}); 
