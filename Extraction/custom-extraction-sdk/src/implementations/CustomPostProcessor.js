const IPostProcessor = require('../interfaces/IPostProcessor');

class ChunkBuilder {
  constructor() {
    this.chunk = {
      chunkId: '',
      chunkTitle: '',
      chunkText: '',
      docId: '',
      sourceId: '',
      searchIndexId: '',
      streamId: '',
      pageNumber: '',
      sourceName: '',
      docName: '',
      recordTitle: '',
      chunkContent: '',
      chunkVector: '',
      answerType: '',
      extractionMethod: '',
      chunkType: '',
      sourceType: '',
      sourceAcl: [],
      fileType: '',
      chunkMeta: {},
      pipelineId: '',
      extractionStrategy: '',
      createdOn: '',
      modifiedOn: '',
      recordUrl: '',
      sourceUrl: '',
      cfa1: undefined,
      cfa2: undefined,
      cfa3: undefined,
      cfa4: undefined,
      cfa5: undefined,
      cfs1: '',
      cfs2: '',
      cfs3: '',
      cfs4: '',
      cfs5: ''
    };
  }

  withChunkId(chunkId) {
    this.chunk.chunkId = chunkId;
    return this;
  }

  withChunkTitle(title) {
    this.chunk.chunkTitle = title;
    return this;
  }

  withChunkText(text) {
    this.chunk.chunkText = text;
    return this;
  }

  withDocId(docId) {
    this.chunk.docId = docId;
    return this;
  }

  withSourceId(sourceId) {
    this.chunk.sourceId = sourceId;
    return this;
  }

  withSearchIndexId(searchIndexId) {
    this.chunk.searchIndexId = searchIndexId;
    return this;
  }

  withStreamId(streamId) {
    this.chunk.streamId = streamId;
    return this;
  }

  withPageNumber(pageNumber) {
    this.chunk.pageNumber = pageNumber;
    return this;
  }

  withSourceName(sourceName) {
    this.chunk.sourceName = sourceName;
    return this;
  }

  withDocName(docName) {
    this.chunk.docName = docName;
    return this;
  }

  withRecordTitle(recordTitle) {
    this.chunk.recordTitle = recordTitle;
    return this;
  }

  withChunkContent(content) {
    this.chunk.chunkContent = content;
    return this;
  }

  withChunkVector(vector) {
    this.chunk.chunkVector = vector;
    return this;
  }

  withAnswerType(answerType) {
    this.chunk.answerType = answerType;
    return this;
  }

  withExtractionMethod(method) {
    this.chunk.extractionMethod = method;
    return this;
  }

  withChunkType(type) {
    this.chunk.chunkType = type;
    return this;
  }

  withSourceType(type) {
    this.chunk.sourceType = type;
    return this;
  }

  withSourceAcl(acl) {
    this.chunk.sourceAcl = acl;
    return this;
  }

  withFileType(type) {
    this.chunk.fileType = type;
    return this;
  }

  withChunkMeta(meta) {
    this.chunk.chunkMeta = meta;
    return this;
  }

  withPipelineId(id) {
    this.chunk.pipelineId = id;
    return this;
  }

  withExtractionStrategy(strategy) {
    this.chunk.extractionStrategy = strategy;
    return this;
  }

  withCreatedOn(date) {
    this.chunk.createdOn = date;
    return this;
  }

  withModifiedOn(date) {
    this.chunk.modifiedOn = date;
    return this;
  }

  withRecordUrl(url) {
    this.chunk.recordUrl = url;
    return this;
  }

  withSourceUrl(url) {
    this.chunk.sourceUrl = url;
    return this;
  }

  withCustomFieldArray(number, array) {
    if (number >= 1 && number <= 5) {
      this.chunk[`cfa${number}`] = array;
    }
    return this;
  }

  withCustomFieldString(number, value) {
    if (number >= 1 && number <= 5) {
      this.chunk[`cfs${number}`] = value;
    }
    return this;
  }

  build() {
    if (!this.chunk.chunkText || !this.chunk.chunkTitle) {
      throw new Error('chunkText and chunkTitle are required');
    }
    return { ...this.chunk };
  }
}

class CustomPostProcessor extends IPostProcessor {
  constructor(batchSize = 5) {
    super();
    this.batchSize = batchSize;
  }

  async postProcess(extractedData, type) {
    const postProcessMethod = this.getPostProcessMethod(type);
    return await postProcessMethod(extractedData);
  }

  getPostProcessMethod(type) {
    switch (type) {
      case 'json':
        return this.postProcessJson.bind(this);
      case 'builder':
      default:
        return this.postProcessBuilder.bind(this);
    }
  }

  async postProcessBuilder(extractedData) {
    return extractedData.map(data => {
      return new ChunkBuilder()
        .withChunkId(data.chunkId || "")
        .withChunkTitle(data.chunkTitle || "Title")
        .withChunkText(data.chunkText || "Text")
        .withDocId(data.docId || "fk")
        .withSourceId(data.sourceId || "")
        .withPageNumber(data.pageNumber || 6)
        .withChunkContent(data.chunkContent || "scsc")
        .withChunkMeta(data.chunkMeta || {})
        .withCreatedOn(data.createdOn || new Date().toISOString())
        .withModifiedOn(data.modifiedOn || new Date().toISOString())
        .build();
    });
  }

  async postProcessJson(extractedData) {
    return extractedData.map(data => {
      return {
        chunkId: data.chunkId || "",
        chunkTitle: data.chunkTitle || "Title",
        chunkText: data.chunkText || "Text",
        docId: data.docId || "fk",
        sourceId: data.sourceId || "",
        searchIndexId: data.searchIndexId || "",
        streamId: data.streamId || "",
        pageNumber: data.pageNumber || 6,
        sourceName: data.sourceName || "",
        docName: data.docName || "",
        recordTitle: data.recordTitle || "",
        chunkContent: data.chunkContent || "scsc",
        chunkVector: data.chunkVector || "",
        answerType: data.answerType || "",
        extractionMethod: data.extractionMethod || "",
        chunkType: data.chunkType || "",
        sourceType: data.sourceType || "",
        sourceAcl: data.sourceAcl || [],
        fileType: data.fileType || "",
        chunkMeta: data.chunkMeta || {},
        pipelineId: data.pipelineId || "",
        extractionStrategy: data.extractionStrategy || "",
        createdOn: data.createdOn || new Date().toISOString(),
        modifiedOn: data.modifiedOn || new Date().toISOString(),
        recordUrl: data.recordUrl || "",
        sourceUrl: data.sourceUrl || "",
        cfa1: data.cfa1,
        cfa2: data.cfa2,
        cfa3: data.cfa3,
        cfa4: data.cfa4,
        cfa5: data.cfa5,
        cfs1: data.cfs1 || "",
        cfs2: data.cfs2 || "",
        cfs3: data.cfs3 || "",
        cfs4: data.cfs4 || "",
        cfs5: data.cfs5 || ""
      };
    });
  }

  async formatResponse(requestWrapper, chunks, batchIndex = 0) {
    const totalBatches = Math.ceil(chunks.length / this.batchSize);
    const startIndex = batchIndex * this.batchSize;
    const endIndex = Math.min(startIndex + this.batchSize, chunks.length);
    const currentBatchChunks = chunks.slice(startIndex, endIndex);
    const isLastBatch = endIndex >= chunks.length;

    return {
      strategiesBatchId: requestWrapper.getStrategyBatchId(),
      docId: requestWrapper.getDocumentId(),
      traceId: requestWrapper.getTraceId(),
      batchIndex: batchIndex,
      totalBatches: totalBatches,
      lastBatch: isLastBatch,
      chunkData: currentBatchChunks
    };
  }

  getBatchCount(chunks) {
    return Math.ceil(chunks.length / this.batchSize);
  }
}

module.exports = CustomPostProcessor; 