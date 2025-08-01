const axios = require('axios');
const logger = require('./utils/logger');
const fs = require('fs');
const path = require('path');

// Load crawler configuration
const crawlerConfig = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'config', 'crawler.json'), 'utf-8'));
const ingestConfig = crawlerConfig.ingest;

async function ingestData(data) {
    if (!data) {
        logger.error('No data to ingest.');
        return;
    }

    if (!ingestConfig.authToken) {
        logger.error('Error: authToken is missing in the configuration.');
        return;
    }

    let config;
    logger.info('Ingesting data of Title: ', data?.title);
    if (ingestConfig.isUnifiedXO) {
        // UXO API configuration
        const uxoUrl = ingestConfig.apiUrls.uxo.replace('{streamId}', ingestConfig.streamId);
        config = {
            url: `${ingestConfig.hostUrl}${uxoUrl}`,
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Auth': `${ingestConfig.authToken}`
            },
            timeout: ingestConfig.timeout,
            validateStatus: status => status < 500,
            data: {
                "sourceName": ingestConfig.name,
                "sourceType": "json",
                "documents": [
                    {
                        "title": data.title,
                        "chunks": [
                            {
                                "chunkTitle": data.title,
                                "chunkText": data.content,
                                "recordUrl": data.url
                            }
                        ]
                    }
                ]
            }
        };
    } else {
        // SearchAssist API configuration
        const searchAssistUrl = ingestConfig.apiUrls.searchAssist.replace('{streamId}', ingestConfig.streamId);
        config = {
            url: `${ingestConfig.hostUrl}${searchAssistUrl}`,
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Auth': `${ingestConfig.authToken}`
            },
            timeout: ingestConfig.timeout,
            validateStatus: status => status < 500,
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

    try {
        const response = await axios.request(config);
        logger.info(response.data);
        logger.info('Data ingested successfully', { 
            status: response.status,
            apiType: ingestConfig.isUnifiedXO ? 'UXO' : 'SearchAssist',
            jobId: response?.data?.data?.jobId
        });
    } catch (error) {
        logger.error('Error ingesting data', {
            error: error.response?.data || error.message,
            apiType: ingestConfig.isUnifiedXO ? 'UXO' : 'SearchAssist'
        });
    }
}

module.exports = ingestData; 