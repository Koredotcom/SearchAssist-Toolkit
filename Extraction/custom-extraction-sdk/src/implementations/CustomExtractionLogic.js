const IExtractionLogic = require('../interfaces/IExtractionLogic');

class CustomExtractionLogic extends IExtractionLogic {
  async extract(requestWrapper) {
    // Using direct getters instead of getBodyField
    const docId = requestWrapper.getDocumentId();
    const documentMeta = requestWrapper.getDocumentMeta();
    const chunkId = requestWrapper.getChunkId();
    const sourceId = requestWrapper.getSourceId();
    const searchIndexId = requestWrapper.getSearchIndexId();
    const title = requestWrapper.getTitle();
    const extractionMethod = requestWrapper.getExtractionMethod();
    const extractionMethodType = requestWrapper.getExtractionMethodType();
    const content = requestWrapper.getContent();
    const text = requestWrapper.getText();
    
    // Example extraction logic
    const extractedChunks = [
      {
        chunkId: chunkId || "",
        docId: docId || "",
        sourceId: sourceId || "",
        searchIndexId: searchIndexId || "",
        chunkText: text || content || `This is an extracted chunk from document ${docId}`,
        chunkTitle: title || "Custom Extraction",
        extractionMethod: extractionMethod || "myMethod",
        metadata: documentMeta || {}
      }
    ];

    return extractedChunks;
  }
}

module.exports = CustomExtractionLogic; 