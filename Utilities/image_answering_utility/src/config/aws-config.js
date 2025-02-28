const { S3Client, PutObjectCommand, GetObjectCommand } = require('@aws-sdk/client-s3');
const { getSignedUrl } = require('@aws-sdk/s3-request-presigner');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../../config/.env') });

// Create an S3 client
const s3 = new S3Client({
    region: process.env.AWS_REGION,
    credentials: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
    },
    maxAttempts: 3,
    forcePathStyle: true // Use path-style URLs for S3
});

const S3_BUCKET_NAME = process.env.S3_BUCKET_NAME;
const S3_FOLDER_PATH = process.env.S3_FOLDER_PATH || '';

// Function to generate presigned URL for getting objects
async function generatePresignedUrl(key) {
    try {
        const command = new GetObjectCommand({
            Bucket: S3_BUCKET_NAME,
            Key: key
        });
        return await getSignedUrl(s3, command, { 
            expiresIn: parseInt(process.env.S3_URL_EXPIRY, 10) || 604800 
        });
    } catch (error) {
        console.error(`Error generating presigned URL: ${error.message}`);
        throw error;
    }
}

// Function to upload data to S3
async function uploadToS3(key, data) {
    try {
        const s3Key = path.join(S3_FOLDER_PATH, key).replace(/\\/g, '/');
        const putCommand = new PutObjectCommand({
            Bucket: S3_BUCKET_NAME,
            Key: s3Key,
            Body: typeof data === 'string' ? data : JSON.stringify(data),
            ContentType: 'application/json'
        });

        await s3.send(putCommand);
        
        // Generate presigned URL for the uploaded object
        return await generatePresignedUrl(s3Key);
    } catch (error) {
        console.error(`Error uploading to S3: ${error.message}`);
        throw error;
    }
}

module.exports = {
    s3,
    S3_BUCKET_NAME,
    uploadToS3,
    generatePresignedUrl
}; 