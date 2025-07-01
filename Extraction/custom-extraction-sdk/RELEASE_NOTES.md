# Custom Extraction SDK v1.0.0 - Getting Started Guide

Welcome to the Custom Extraction SDK! This guide will help you set up and customize your document extraction pipeline in just a few steps.

## 🚀 Quick Start (5 minutes)

### 1. Prerequisites
- Node.js 14.0.0 or higher
- NPM package manager
- Your SearchAI API key (Optional)

### 2. Installation & Setup
```bash
# Install dependencies
npm install

# Start the server
npm start
```
Your extraction service will be running at `http://localhost:6606/searchAssistant/checkCustom/`

### 3. Configure Your API Key
Open `src/config/config.js` and update your API key:
```javascript
API: {
  HEADERS: {
    API_KEY: 'your-searchai-api-key-here'  // Replace with your actual API key
  }
}
```

## 🛠️ What You Need to Customize

The SDK comes with three main files you can customize based on your needs:

### 1. **CustomPreProcessor.js** - Prepare Your Data
**Location:** `src/implementations/CustomPreProcessor.js`
**What it does:** Receives and organizes incoming document data
**When to modify:** If you need to transform or validate data before processing

**Example customization:**
```javascript
process(headers, body, files) {
  // Add your custom validation logic here
  if (!body.docId) {
    throw new Error('Document ID is required');
  }
  
  // Your existing code continues...
  const requestWrapper = new RequestWrapper(headers, body, files);
  return requestWrapper;
}
```

### 2. **CustomExtractionLogic.js** - Extract Your Content
**Location:** `src/implementations/CustomExtractionLogic.js`
**What it does:** The main extraction logic for different document types
**When to modify:** To implement your specific extraction rules

**Built-in strategies for:**
- 📄 **Files** (PDFs, Word docs, etc.)
- 🌐 **Web pages**
- 📊 **Structured data**
- ❓ **FAQ documents**
- 🔌 **Connector data** (Confluence, SharePoint, etc.)

**Example customization:**
```javascript
// In FileExtractionStrategy class
execute(requestWrapper) {
  const fileName = requestWrapper.getFileTitle();
  const fileType = requestWrapper.getFileType();
  
  // Your custom extraction logic here
  if (fileType === 'pdf') {
    return this.extractFromPDF(requestWrapper);
  }
  
  return [{ chunkText: "Your extracted content", chunkTitle: fileName }];
}
```

### 3. **CustomPostProcessor.js** - Format Your Output
**Location:** `src/implementations/CustomPostProcessor.js`
**What it does:** Formats extracted content into chunks for SearchAI
**When to modify:** To customize how your content is structured and sent back

**Example customization:**
```javascript
async postProcess(extractedData, type = 'builder') {
  const chunks = [];
  
  for (const item of extractedData) {
    // Add your custom formatting logic
    const chunk = {
      chunkText: item.chunkText,
      chunkTitle: item.chunkTitle,
      // Add custom fields
      customField: 'your-value',
      priority: this.calculatePriority(item)
    };
    chunks.push(chunk);
  }
  
  return chunks;
}
```

## 🎯 Common Use Cases & Examples

### Use Case 1: Custom PDF Processing
Modify `CustomExtractionLogic.js` to add special handling for PDFs:
```javascript
if (requestWrapper.getFileType() === 'pdf') {
  // Your PDF-specific logic
  const pdfContent = await this.processPDF(requestWrapper.getDownloadUrl());
  return this.formatPDFContent(pdfContent);
}
```

### Use Case 2: Add Metadata Enrichment
Modify `CustomPostProcessor.js` to add metadata:
```javascript
const chunk = {
  chunkText: item.chunkText,
  chunkTitle: item.chunkTitle,
  // Add metadata
  extractedAt: new Date().toISOString(),
  documentType: requestWrapper.getSourceType(),
  confidence: this.calculateConfidence(item)
};
```

### Use Case 3: External Service Integration
Modify `CustomExtractionLogic.js` to call external APIs:
```javascript
async extract(requestWrapper) {
  const externalData = await this.callExternalService(
    requestWrapper.getDownloadUrl()
  );
  return this.processExternalData(externalData);
}
```

## 🔧 Development & Testing

### Development Mode (with auto-restart)
```bash
npm run dev
```

### Test Your Changes
```bash
# Run the demo to test your customizations
node src/demo.js

# Run unit tests
npm test

# Check code quality
npm run lint
```

### Debug Mode
Set environment variable for detailed logging:
```bash
DEBUG=* npm start
```

## 📋 Configuration Options

Edit `src/config/config.js` to customize:

- **Server Port:** Change `SERVER.PORT` (default: 6606)
- **Processing Delay:** Adjust `PROCESSING.DELAY_MS` for async processing
- **Supported Connectors:** Modify `CONNECTORS.CONFIGURED_CONNECTORS` array
- **Error Messages:** Customize `ERROR_MESSAGES` for your language/needs

## 🔍 Understanding the Data Flow

1. **Request comes in** → `CustomPreProcessor` organizes the data
2. **Data gets processed** → `CustomExtractionLogic` extracts content
3. **Content gets formatted** → `CustomPostProcessor` creates chunks
4. **Chunks get sent back** → `CallbackService` delivers to SearchAI

## 🆘 Troubleshooting

### Common Issues:

**Server won't start:**
- Check if port 6606 is available
- Verify Node.js version: `node --version`

**API key errors:**
- Ensure your API key is correctly set in `config.js`
- Check that your API key has proper permissions

**Processing failures:**
- Check the console logs for detailed error messages
- Verify your custom logic doesn't throw unhandled exceptions

### Getting Help:
- Check the console output for detailed error messages
- Use the demo file (`src/demo.js`) to test your changes
- Enable debug mode for more detailed logging

## 📚 What's Included

- ✅ **Complete extraction pipeline** ready to use
- ✅ **Multiple extraction strategies** for different content types
- ✅ **Flexible configuration** system
- ✅ **Built-in error handling** and logging
- ✅ **Development tools** (hot-reload, testing, linting)
- ✅ **Example implementations** to get you started

---

**Ready to start?** Run `npm install && npm start` and begin customizing your extraction logic!

**Need help?** Check the demo file or reach out to our support team. 