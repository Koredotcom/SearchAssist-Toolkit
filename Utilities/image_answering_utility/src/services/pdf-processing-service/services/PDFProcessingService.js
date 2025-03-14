const fs = require('fs-extra');
const path = require('path');
const FormData = require('form-data');
const { createReadStream } = require('fs');
const logger = require('../utils/logger');
const { MarkdownService } = require('./MarkdownService');
const { ResultsManager } = require('../utils/ResultsManager');
const { FileTracker } = require('../utils/FileTracker');
const { StorageManager } = require('../utils/StorageManager');
const ImageController = require('../../pdf-image-service/controllers/ImageController');
const { FileStatus } = require('../models/FileStatus');

class PDFProcessingService {
    constructor() {
        this.markdownService = new MarkdownService();
        this.resultsManager = new ResultsManager();
        this.fileTracker = new FileTracker();
        this.storageManager = new StorageManager();
        this.imageController = new ImageController();
    }

    async processPDF(filePath, filename, include_base64 = false, uniqueId = null) {
        const startTime = Date.now();
        
        // Use provided uniqueId or generate new one
        const fileUniqueId = uniqueId || await this.fileTracker.generateUniqueId(filename);
        
        try {
            // Verify file exists and is accessible
            try {
                await fs.access(filePath);
            } catch (error) {
                throw new Error(`PDF file not accessible: ${error.message}`);
            }

            // Track file processing
            await this.fileTracker.trackFile(filename, filePath, fileUniqueId);
            logger.info(`Starting to process: ${filename} (ID: ${fileUniqueId})`);

            const fileStats = await fs.stat(filePath);
            logger.info(`File size: ${(fileStats.size / (1024 * 1024)).toFixed(2)} MB`);

            // Process PDF with proper error handling
            let markdownResult = null;
            let imageResults = null;

            try {
                [markdownResult, imageResults] = await Promise.all([
                    this.processMarkdown(filePath, fileUniqueId).catch(error => {
                        logger.error(`Markdown processing failed for ${filename}: ${error.message}`);
                        return null;
                    }),
                    this.processImages(filePath, include_base64, fileUniqueId).catch(error => {
                        logger.error(`Image processing failed for ${filename}: ${error.message}`);
                        return null;
                    })
                ]);

                if (!markdownResult && !imageResults) {
                    throw new Error('Both markdown and image processing failed');
                }
            } catch (error) {
                logger.error(`Processing failed for ${filename}: ${error.message}`);
                throw error;
            }

            // Save and combine results
            const results = await this.resultsManager.saveResults(
                filename,
                markdownResult,
                imageResults,
                fileUniqueId
            );

            const processingTime = (Date.now() - startTime) / 1000;
            await this.fileTracker.updateStatus(fileUniqueId, 'completed', {
                s3Url: results.s3_url
            });
            
            
            return {
                filename,
                uniqueId: fileUniqueId,
                success: true,
                processingTime,
                s3_url: results.s3_url,
                markdown_status: markdownResult ? 'success' : 'failed',
                image_status: imageResults ? 'success' : 'failed'
            };

        } catch (error) {
            const processingTime = (Date.now() - startTime) / 1000;
            await this.fileTracker.updateStatus(fileUniqueId, 'failed', {
                error: error.message
            });

            return {
                filename,
                uniqueId: fileUniqueId,
                success: false,
                error: error.message,
                processingTime
            };
        }
    }

    async processMarkdown(filePath, uniqueId) {
        try {
            return await this.markdownService.processFile(filePath, uniqueId);
        } catch (error) {
            if (error.message.includes('service is currently unavailable')) {
                throw error; // Propagate service unavailability errors
            }
            logger.error(`Error in markdown processing: ${error.message}`);
            throw new Error(`Markdown processing failed: ${error.message}`);
        }
    }

    async processImages(filePath, include_base64, uniqueId) {
        try {
            return await this.imageController.convertToImages(filePath, path.basename(filePath), {
                includeBase64: include_base64,
                uniqueId
            });
        } catch (error) {
            logger.error(`Error in image processing: ${error.message}`);
            throw new Error(`Image processing failed: ${error.message}`);
        }
    }

    async processAllPDFs(inputFolderPath, include_base64 = false, uniqueId = null) {
        const processId = uniqueId || `batch_${Date.now()}`;
        const tempDir = await this.storageManager.createTempDirectory(processId);
        
        try {
            // Copy files to temp directory
            const files = await this.storageManager.getAllPDFFiles(inputFolderPath);
            const tempFiles = await Promise.all(files.map(async (file) => {
                const tempFile = path.join(tempDir, path.basename(file));
                await fs.copyFile(file, tempFile);
                return tempFile;
            }));

            // Get concurrency limit from env or default to 3
            const BATCH_SIZE = parseInt(process.env.MAX_CONCURRENT_PROCESSING, 10) || 3;
            logger.info(`Processing PDFs with batch size: ${BATCH_SIZE}`);

            // Process files in concurrent batches
            const results = [];
            for (let i = 0; i < tempFiles.length; i += BATCH_SIZE) {
                const batch = tempFiles.slice(i, i + BATCH_SIZE);
                logger.info(`Processing batch ${Math.floor(i/BATCH_SIZE) + 1} of ${Math.ceil(tempFiles.length/BATCH_SIZE)}`);
                
                const batchResults = await Promise.all(batch.map(async (filePath) => {
                    try {
                        const filename = path.basename(filePath);
                        // Create a unique ID for each file that includes the batch ID
                        const fileUniqueId = uniqueId ? 
                            `${uniqueId}_${filename.replace(/\.[^/.]+$/, '')}` : 
                            await this.fileTracker.generateUniqueId(filename);
                            
                        logger.info(`Starting to process ${filename} with ID: ${fileUniqueId}`);
                        const result = await this.processPDF(filePath, filename, include_base64, fileUniqueId);
                        logger.info(`Completed processing ${filename}`);
                        return result;
                    } catch (error) {
                        const filename = path.basename(filePath);
                        logger.error(`Error processing ${filename}: ${error.message}`);
                        const errorUniqueId = uniqueId ? 
                            `${uniqueId}_${filename.replace(/\.[^/.]+$/, '')}` : 
                            await this.fileTracker.generateUniqueId(filename);
                        return {
                            filename,
                            success: false,
                            error: error.message,
                            uniqueId: errorUniqueId
                        };
                    }
                }));

                results.push(...batchResults);
                logger.info(`Completed batch ${Math.floor(i/BATCH_SIZE) + 1}`);
            }

            return results;
        } finally {
            await this.storageManager.cleanup(tempDir);
        }
    }

    async getStatus(uniqueId) {
        return this.fileTracker.getStatus(uniqueId);
    }
}

module.exports = { PDFProcessingService }; 
