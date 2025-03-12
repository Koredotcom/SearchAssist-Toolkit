const { PDFProcessingService } = require('../services/PDFProcessingService');
const logger = require('../utils/logger');

class ProcessingController {
    constructor() {
        this.processingService = new PDFProcessingService();
    }

    async processSinglePDF(filePath, options = {}) {
        const { include_base64 = false, uniqueId = null } = options;
        const filename = require('path').basename(filePath);

        try {
            logger.info(`Starting to process PDF: ${filename} (ID: ${uniqueId || 'N/A'})`);
            const result = await this.processingService.processPDF(filePath, filename, include_base64, uniqueId);
            logger.info(`Completed processing PDF: ${filename} (ID: ${uniqueId || 'N/A'})`);
            return result;
        } catch (error) {
            logger.error(`Error processing PDF ${filename}: ${error.message}`);
            throw error;
        }
    }

    async processDirectory(inputPath, options = {}) {
        const { include_base64 = false, uniqueId = null } = options;

        try {
            logger.info(`Starting directory processing: ${inputPath} (ID: ${uniqueId || 'N/A'})`);
            const results = await this.processingService.processAllPDFs(inputPath, include_base64, uniqueId);
            logger.info(`Completed directory processing: ${inputPath} (ID: ${uniqueId || 'N/A'})`);
            return results;
        } catch (error) {
            logger.error(`Error processing directory ${inputPath} (ID: ${uniqueId || 'N/A'}): ${error.message}`);
            throw error;
        }
    }

    async getProcessingStatus(uniqueId) {
        try {
            return await this.processingService.getStatus(uniqueId);
        } catch (error) {
            logger.error(`Error getting status for ${uniqueId}: ${error.message}`);
            throw error;
        }
    }
}

module.exports = ProcessingController; 
