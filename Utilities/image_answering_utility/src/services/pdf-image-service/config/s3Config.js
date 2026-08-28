const { S3Client, PutObjectCommand, GetObjectCommand } = require('@aws-sdk/client-s3');
const { getSignedUrl } = require('@aws-sdk/s3-request-presigner');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../../../../config/.env') });

const s3Client = new S3Client({
    region: process.env.AWS_REGION,
    credentials: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
    },
    maxAttempts: 3,
    forcePathStyle: true
});

const s3Config = {
    client: s3Client,
    bucketName: process.env.S3_BUCKET_NAME,
    folderPath: process.env.S3_FOLDER_PATH || '',
    urlExpiry: parseInt(process.env.S3_URL_EXPIRY, 10) || 604800,

    // Normalize S3 key to use forward slashes and remove any double slashes
    normalizeKey(key) {
        return key.replace(/\\/g, '/').replace(/\/+/g, '/').replace(/^\//, '');
    },

    async uploadToS3(key, data) {
        try {
            const s3Key = this.normalizeKey(key);
            const putCommand = new PutObjectCommand({
                Bucket: this.bucketName,
                Key: s3Key,
                Body: typeof data === 'string' ? data : JSON.stringify(data),
                ContentType: 'application/json'
            });

            await this.client.send(putCommand);
            return await this.generatePresignedUrl(s3Key);
        } catch (error) {
            throw new Error(`Error uploading to S3: ${error.message}`);
        }
    },

    async generatePresignedUrl(key) {
        try {
            const s3Key = this.normalizeKey(key);
            const command = new GetObjectCommand({
                Bucket: this.bucketName,
                Key: s3Key
            });
            return await getSignedUrl(this.client, command, { 
                expiresIn: this.urlExpiry 
            });
        } catch (error) {
            throw new Error(`Error generating presigned URL: ${error.message}`);
        }
    }
};

module.exports = { s3Config }; 