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

    const config = {
        url: `${ingestConfig.hostUrl}/searchassistapi/external/stream/${ingestConfig.streamId}/ingest?contentSource=manual&extractionType=data&index=true`,
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
                    "title": data.title,
                    "content": data.content,
                    "url": data.url
                }
            ],
            "name": ingestConfig.name
        }
    };

    try {
        const response = await axios.request(config);
        logger.info('Data ingested successfully', { 
            status: response.status
        });
    } catch (error) {
        logger.error('Error ingesting data', {
            error: error.response?.data || error.message
        });
    }
}

module.exports = ingestData; 