const fs = require('fs-extra');
const path = require('path');
const { fromPath } = require('pdf2pic');
const { PutObjectCommand } = require('@aws-sdk/client-s3');
const { execSync } = require('child_process');
const logger = require('../utils/logger');
const { s3Config } = require('../config/s3Config');
const { StorageManager } = require('../utils/StorageManager');

// Add environment variable configuration with defaults
const pdfConfig = {
    density: process.env.PDF_IMAGE_DENSITY ? parseInt(process.env.PDF_IMAGE_DENSITY) : 150,
    format: process.env.PDF_IMAGE_FORMAT || 'png',
    width: process.env.PDF_IMAGE_WIDTH ? parseInt(process.env.PDF_IMAGE_WIDTH) : 1200,
    height: process.env.PDF_IMAGE_HEIGHT ? parseInt(process.env.PDF_IMAGE_HEIGHT) : 1600,
    preserveAspectRatio: process.env.PDF_PRESERVE_ASPECT_RATIO === 'false' ? false : true,
    quality: process.env.PDF_IMAGE_QUALITY ? parseInt(process.env.PDF_IMAGE_QUALITY) : 80
};

class PDFImageService {
    constructor() {
        this.storageManager = new StorageManager();
        this.checkDependencies();
        // Initialize concurrency limit with dynamic import
        this.initializeConcurrencyLimit();
        this.activeConversions = new Set();
    }

    async initializeConcurrencyLimit() {
        const { default: pLimit } = await import('p-limit');
        this.concurrencyLimit = pLimit(3); // Process 5 files at a time
    }

    checkDependencies() {
        try {
            execSync('gm version');
        } catch (error) {
            logger.error('GraphicsMagick is not installed. Please install it first.');
            throw new Error('GraphicsMagick is required but not installed');
        }
    }

    async convertPDFToImages(pdfPath, filename, includeBase64 = false, uniqueId = null) {
        // Ensure concurrency limit is initialized
        if (!this.concurrencyLimit) {
            await this.initializeConcurrencyLimit();
        }

        // Verify file exists and is accessible
        try {
            await fs.access(pdfPath);
        } catch (error) {
            throw new Error(`PDF file not accessible at path ${pdfPath}: ${error.message}`);
        }

        const sanitizedFilename = filename.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
        const processId = uniqueId || `f_${sanitizedFilename}_${Date.now()}`;
        let processDir = null;

        // Add to active conversions
        this.activeConversions.add(processId);

        try {
            processDir = await this.storageManager.createTempDirectory(processId);
            // Use concurrency limit for the conversion
            return await this.concurrencyLimit(async () => {
                logger.info(`[${processId}] Starting conversion of ${filename} from ${pdfPath}`);
                const convert = fromPath(pdfPath, {
                    density: pdfConfig.density,
                    format: pdfConfig.format,
                    width: pdfConfig.width,
                    height: pdfConfig.height,
                    preserveAspectRatio: pdfConfig.preserveAspectRatio,
                    quality: pdfConfig.quality,
                    saveFilename: `page`,
                    savePath: processDir
                });

                const pages = await convert.bulk(-1);
                logger.info(`[${processId}] Converted PDF to ${pages.length} images`);

                return await this.processPages(pages, processId, includeBase64);
            });
        } catch (error) {
            logger.error(`[${processId}] Error during PDF conversion: ${error.message}`);
            throw error;
        } finally {
            try {
                // Remove from active conversions
                this.activeConversions.delete(processId);
                
                if (processDir) {
                    // Ensure cleanup is complete
                    await this.storageManager.cleanup(processDir);
                    
                    // Double-check if directory still exists
                    if (await fs.pathExists(processDir)) {
                        logger.error(`Failed to remove directory: ${processDir}`);
                        // Try one more time with force
                        await fs.rm(processDir, { recursive: true, force: true });
                    }
                }
            } catch (cleanupError) {
                logger.error(`[${processId}] Cleanup error: ${cleanupError.message}`);
                // Don't throw cleanup errors, but log them
            }
        }
    }

    async processPages(pages, processId, includeBase64) {
        // Process pages in batches to avoid memory issues
        const batchSize = 5;
        const results = [];
        
        for (let i = 0; i < pages.length; i += batchSize) {
            const batch = pages.slice(i, i + batchSize);
            const batchPromises = batch.map(async (page, index) => {
                const pageNumber = i + index + 1;
                try {
                    const imgBuffer = await fs.readFile(page.path);
                    const result = {
                        page_number: pageNumber,
                        image_url: null,
                        base64_data: includeBase64 ? imgBuffer.toString('base64') : undefined
                    };

                    const s3Key = `${processId}/page_${pageNumber}.png`.replace(/\\/g, '/');
                    await this.uploadToS3(s3Key, imgBuffer);
                    result.image_url = await this.generatePresignedUrl(s3Key);

                    logger.info(`[${processId}] Processed page ${pageNumber}`);
                    return result;
                } catch (error) {
                    logger.error(`[${processId}] Error processing page ${pageNumber}: ${error.message}`);
                    return {
                        page_number: pageNumber,
                        error: error.message
                    };
                }
            });

            const batchResults = await Promise.all(batchPromises);
            results.push(...batchResults);
        }
        
        return results;
    }

    async uploadToS3(key, buffer) {
        try {
            const s3Key = path.posix.join(s3Config.folderPath, key);
            const command = new PutObjectCommand({
                Bucket: s3Config.bucketName,
                Key: s3Key,
                Body: buffer,
                ContentType: 'image/png'
            });
            await s3Config.client.send(command);
            return s3Key;
        } catch (error) {
            logger.error(`Error uploading to S3: ${error.message}`);
            throw error;
        }
    }

    async generatePresignedUrl(key) {
        try {
            const s3Key = path.posix.join(s3Config.folderPath, key);
            return await s3Config.generatePresignedUrl(s3Key);
        } catch (error) {
            logger.error(`Error generating presigned URL: ${error.message}`);
            throw error;
        }
    }

}

module.exports = { PDFImageService }; 