const axios = require('axios');
const logger = require('./utils/logger');
const fs = require('fs');
const path = require('path');

// Load crawler configuration
const crawlerConfig = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'config', 'crawler.json'), 'utf-8'));
const ingestConfig = crawlerConfig.ingest;

// Global batch counter
let batchCounter = 0;

// Function to generate unique title with URL hash and batch number
function generateUniqueTitle(originalTitle, url, batchNumber) {
    const urlHash = url.split('/').pop() || 'page';

    return `${originalTitle}_batch_${batchNumber}`;
}

// Function to prepare common configuration
function prepareCommonConfig() {
    const baseConfig = {
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'auth': `${ingestConfig.authToken}`
        },
        timeout: ingestConfig.timeout,
        validateStatus: status => status < 500
    };

    return baseConfig;
}

// Function to prepare UXO API configuration
function prepareUXOConfig(data, uniqueTitle) {
    const uxoUrl = ingestConfig.apiUrls.uxo.replace('{streamId}', ingestConfig.streamId);
    const baseConfig = prepareCommonConfig();
    
    return {
        ...baseConfig,
        url: `${ingestConfig.hostUrl}${uxoUrl}`,
        method: 'POST',
        data: {
            "sourceName": ingestConfig.name,
            "sourceType": "json",
            "documents": [
                {
                    "title": uniqueTitle,
                    "chunks": [
                        {
                            "chunkTitle": data.title || "Chunk Title",
                            "chunkText": data.content,
                            "recordUrl": data.url
                        }
                    ]
                }
            ]
        }
    };
}

// Function to prepare SearchAssist API configuration
function prepareSearchAssistConfig(data) {
    const searchAssistUrl = ingestConfig.apiUrls.searchAssist.replace('{streamId}', ingestConfig.streamId);
    const baseConfig = prepareCommonConfig();
    
    return {
        ...baseConfig,
        url: `${ingestConfig.hostUrl}${searchAssistUrl}`,
        method: 'POST',
        data: {
            "documents": [
                {
                    "title": data?.title,
                    "content": data?.content,
                    "url": data?.url
                }
            ],
            "name": ingestConfig.name
        }
    };
}

// Function to prepare UXO batch configuration
function prepareUXOBatchConfig(documents, uniqueTitle) {
    const uxoUrl = ingestConfig.apiUrls.uxo.replace('{streamId}', ingestConfig.streamId);
    const baseConfig = prepareCommonConfig();
    
    // Create chunks from all documents
    const chunks = documents.map(doc => ({
        "chunkTitle": doc.title || "Chunk Title",
        "chunkText": doc.content,
        "recordUrl": doc.url
    }));

    const uxoDocuments = [
        {
            "title": uniqueTitle,
            "chunks": chunks
        }
    ];

    return {
        ...baseConfig,
        url: `${ingestConfig.hostUrl}${uxoUrl}`,
        method: 'POST',
        data: {
            "sourceName": ingestConfig.name,
            "sourceType": "json",
            "documents": uxoDocuments
        }
    };
}

// Function to prepare SearchAssist batch configuration
function prepareSearchAssistBatchConfig(documents) {
    const searchAssistUrl = ingestConfig.apiUrls.searchAssist.replace('{streamId}', ingestConfig.streamId);
    const baseConfig = prepareCommonConfig();
    
    // Create individual documents for each crawled page
    const searchAssistDocuments = documents.map(doc => ({
        "title": doc.title || "Title",
        "content": doc.content,
        "url": doc.url
    }));

    return {
        ...baseConfig,
        url: `${ingestConfig.hostUrl}${searchAssistUrl}`,
        method: 'POST',
        data: {
            "documents": searchAssistDocuments,
            "name": ingestConfig.name
        }
    };
}

// Function to ingest a single document (for backward compatibility)
async function ingestData(data) {
    if (!data) {
        logger.error('No data to ingest.');
        return;
    }

    if (!ingestConfig.authToken) {
        logger.error('Error: authToken is missing in the configuration.');
        return;
    }

    // Generate unique title
    const uniqueTitle = generateUniqueTitle(data.title, data.url, batchCounter);

    let config;
    logger.info('Ingesting data with unique title: ', uniqueTitle);
    
    if (ingestConfig.isUnifiedXO) {
        // UXO API configuration
        config = prepareUXOConfig(data, uniqueTitle);
    } else {
        // SearchAssist API configuration
        config = prepareSearchAssistConfig(data);
    }

    try {
        const response = await axios.request(config);
        logger.info(response.data);
        logger.info('Data ingested successfully', { 
            status: response.status,
            apiType: ingestConfig.isUnifiedXO ? 'UXO' : 'SearchAssist',
            jobId: response?.data?.data?.jobId,
            originalTitle: data.title,
            uniqueTitle: uniqueTitle
        });
    } catch (error) {
        logger.error('Error ingesting data', {
            error: error.response?.data || error.message,
            apiType: ingestConfig.isUnifiedXO ? 'UXO' : 'SearchAssist',
            originalTitle: data.title,
            uniqueTitle: uniqueTitle
        });
    }
}

// Function to ingest multiple documents in a single API call
async function ingestBatchData(documents) {
    if (!documents || documents.length === 0) {
        logger.error('No documents to ingest.');
        return;
    }

    if (!ingestConfig.authToken) {
        logger.error('Error: authToken is missing in the configuration.');
        return;
    }

    // Increment batch counter
    batchCounter++;

    logger.info(`Preparing to ingest batch ${batchCounter} with ${documents.length} documents`);

    let config;
    if (ingestConfig.isUnifiedXO) {
        // UXO API configuration - single document with all pages as chunks
        const uniqueTitle = generateUniqueTitle("Crawled Pages", documents[0].url, batchCounter);
        config = prepareUXOBatchConfig(documents, uniqueTitle);
        logger.info(`Created single document with ${documents.length} chunks from all crawled pages`);
    } else {
        // SearchAssist API configuration - individual documents for each page
        config = prepareSearchAssistBatchConfig(documents);
        logger.info(`Created ${documents.length} individual documents for SearchAssist`);
    }

    try {
        const response = await axios.request(config);
        logger.info(JSON.stringify(response.data));

        logger.info('Batch data ingested successfully', { 
            status: response.status,
            apiType: ingestConfig.isUnifiedXO ? 'UXO' : 'SearchAssist',
            jobId: response?.data?.data?.jobId,
            documentCount: ingestConfig.isUnifiedXO ? 1 : documents.length,
            chunkCount: ingestConfig.isUnifiedXO ? documents.length : 0,
            batchNumber: batchCounter
        });
    } catch (error) {
        logger.error('Error ingesting batch data', {
            error: error.response?.data || error.message,
            apiType: ingestConfig.isUnifiedXO ? 'UXO' : 'SearchAssist',
            documentCount: ingestConfig.isUnifiedXO ? 1 : documents.length,
            chunkCount: ingestConfig.isUnifiedXO ? documents.length : 0,
            batchNumber: batchCounter
        });
    }
}

// Function to reset batch counter
function resetBatchCounter() {
    batchCounter = 0;
    logger.info('Batch counter reset to 0');
}

module.exports = { ingestData, ingestBatchData, resetBatchCounter }; 