const logger = require('./logger');
const { s3Config } = require('../config/s3Config');
const { CallbackService } = require('../services/CallbackService');
const { FileRecord } = require('../models/FileRecord');

class ResultsManager {
    constructor() {
        this.callbackService = new CallbackService();
    }

    async saveResults(filename, markdownResult, imageResults, uniqueId) {
        try {
            // Combine results
            const combinedResult = await this.combineResults(filename, markdownResult, imageResults, uniqueId);

            // Update database directly instead of using callback
            await FileRecord.findOneAndUpdate(
                { uniqueId },
                {
                    status: 'completed',
                    s3Url: combinedResult.s3_url,
                    completedTime: new Date(),
                    lastUpdated: new Date()
                },
                { new: true }
            );
            
            // Comment out callback service
            // await this.callbackService.sendCallback(filename, combinedResult.s3_url, true, null, uniqueId);
            
            logger.info(`Results saved for ${filename} (ID: ${uniqueId})`);
            return combinedResult;
        } catch (error) {
            logger.error(`Error in saveResults for ${filename} (ID: ${uniqueId}): ${error.message}`);
            
            // Update database with error status
            await FileRecord.findOneAndUpdate(
                { uniqueId },
                {
                    status: 'failed',
                    error: error.message,
                    lastUpdated: new Date()
                },
                { new: true }
            );

            // Comment out callback service
            // await this.callbackService.sendCallback(
            //     filename,
            //     null,
            //     false,
            //     error.message,
            //     uniqueId
            // );
            throw error;
        }
    }

    async combineResults(filename, markdownResult, imageResults, uniqueId) {
        try {
            // Extract relevant data from both results
            const combinedData = {
                status: "success",
                filename: filename,
                uniqueId: uniqueId,
                timestamp: new Date().toISOString(),
                pages: []
            };

            // Ensure both results exist and have the expected structure
            if (!markdownResult || !markdownResult.chunks) {
                throw new Error('Invalid markdown result structure');
            }

            if (!Array.isArray(imageResults)) {
                throw new Error('Invalid image result structure');
            }

            // Sort image results by page number
            const sortedImageResults = imageResults.sort((a, b) => a.page_number - b.page_number);

            // Combine page data
            for (let i = 0; i < sortedImageResults.length; i++) {
                const imagePage = sortedImageResults[i];
                const pageNumber = imagePage.page_number;
                const markdownPage = markdownResult.chunks.find(
                    chunk => chunk.page_number === pageNumber
                );

                combinedData.pages.push({
                    page_number: pageNumber,
                    image_url: imagePage.image_url,
                    base64_data: imagePage.base64_data,
                    markdown_text: markdownPage ? markdownPage.chunkText : '',
                    // markdown_metadata: markdownPage ? markdownPage.metadata : {}
                });
            }

            // Add total pages and file info
            combinedData.total_pages = sortedImageResults.length;
            combinedData.has_base64 = sortedImageResults.some(page => !!page.base64_data);

            // Upload to S3
            const s3Key = `final_results/${uniqueId}/${filename.replace('.pdf', '')}_combined.json`;
            const s3Url = await this.uploadToS3(s3Key, combinedData);
            
            // Add S3 URL to the response
            combinedData.s3_url = s3Url;
            
            logger.info(`Combined result uploaded to S3: ${s3Url}`);
            return combinedData;

        } catch (error) {
            logger.error(`Error combining results for ${filename}: ${error.message}`);
            throw error;
        }
    }

    async uploadToS3(key, data) {
        try {
            return await s3Config.uploadToS3(key, data);
        } catch (error) {
            logger.error(`Error uploading to S3: ${error.message}`);
            throw error;
        }
    }
}

module.exports = { ResultsManager }; 
