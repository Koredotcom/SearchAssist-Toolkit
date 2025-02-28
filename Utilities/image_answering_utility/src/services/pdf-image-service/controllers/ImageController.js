const { PDFImageService } = require('../services/PDFImageService');
const logger = require('../utils/logger');

class ImageController {
    constructor() {
        this.pdfImageService = new PDFImageService();
    }

    async convertToImages(pdfPath, filename, options = {}) {
        const { includeBase64 = false, uniqueId = null } = options;
        
        try {
            logger.info(`Starting PDF to image conversion for ${filename} from path: ${pdfPath}`);
            const result = await this.pdfImageService.convertPDFToImages(pdfPath, filename, includeBase64, uniqueId);
            logger.info(`Successfully converted ${filename} to images`);
            return result;
        } catch (error) {
            logger.error(`Error converting PDF to images for ${filename}: ${error.message}`);
            logger.error(`File path: ${pdfPath}`);
            throw new Error(`Failed to convert PDF to images: ${error.message}`);
        }
    }

    async generateImageUrl(key) {
        try {
            return await this.pdfImageService.generatePresignedUrl(key);
        } catch (error) {
            logger.error(`Error generating image URL for ${key}: ${error.message}`);
            throw error;
        }
    }

}

module.exports = ImageController; 