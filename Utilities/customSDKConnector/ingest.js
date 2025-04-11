const axios = require('axios');
require('dotenv').config();
const { executeExtraction, formatContent } = require('./Extraction/OneNote/oneNote');


async function ingestData(chunks) {
    const url = `https://${process.env.SEARCHAI_HOST_NAME}/api/public/bot/${process.env.STREAM_ID}/ingest-data`;
    const authToken = process.env.SEARCHAI_JWT_TOKEN;
    
    const payload = {
        sourceName: "CUSTOMSDK",
        sourceType: "json",
        documents: [
            {
                title: "CUSTOMSDK_DOCUMENT",
                chunks: chunks
            }
        ]
    };
    
    try {
        const response = await axios.post(url, payload, {
            headers: {
                'Content-Type': 'application/json',
                'auth': authToken
            }
        });
        console.log('Response:', response.data);
    } catch (error) {
        console.error('Error:', error.response ? error.response.data : error.message);
    }
}

async function ingestionPipeLine() {
  console.log("Starting ingestion pipeline")
  const extracted_content = await executeExtraction();
  console.log("Completed extraction")
  const formatted_chunks = await formatContent(extracted_content);
  console.log("Completed formatting")
  const batch_size = parseInt(process.env.INGESTION_BATCH_SIZE) || 10;
  for (let i = 0; i < formatted_chunks.length; i += batch_size) {
    const batch = formatted_chunks.slice(i, i + batch_size);
    await ingestData(batch);
  }
  console.log("Completed ingestion")
}
//run the ingestion pipeline
ingestionPipeLine();