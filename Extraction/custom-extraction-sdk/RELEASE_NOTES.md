# Custom Extraction SDK Release Notes

## Version 1.0.0 (Initial Release)

### Overview
Custom Extraction SDK is a comprehensive toolkit for document extraction and processing, providing a flexible framework for handling custom document processing workflows.

### Features
- **Document Processing Pipeline**: Complete pipeline for document extraction and processing
- **Custom Pre-processing Support**: Ability to implement custom pre-processing logic
- **Custom Post-processing Support**: Flexible post-processing capabilities
- **External Service Integration**: Built-in support for external processing services
- **File Handling**: Robust file handling using Formidable (v3.5.1)
- **HTTP Client**: Integrated HTTP client using Axios (v1.6.7)

### Technical Requirements
- Node.js version >= 14.0.0
- NPM package manager

### Configuration
- **API Key Setup**: 
  - Required: SearchAI API key
  - Location: Configure your API key in `src/config/config.js`
  - How to obtain: Get your API key from the SearchAI application
  - Important: Keep your API key secure and never commit it to version control

### Key Components and Usage

1. **RequestWrapper Utility**
   - Provides extensive getter methods for accessing document fields
   - Examples include: getDocumentId(), getFileTitle(), getSourceType(), etc.
   - Use these getters to access any field from the request payload
   - All field access is standardized through these getter methods

2. **CustomExtractionLogic Implementation**
   - Extend or modify extraction logic using RequestWrapper getters
   - Access document fields through RequestWrapper methods
   - Implement custom extraction strategies based on content type
   - Example: `requestWrapper.getDownloadUrl()` to get file download URL

3. **CustomPostProcessor Implementation**
   - Use RequestWrapper getters to access fields for post-processing
   - Build response chunks using the ChunkBuilder
   - Customize post-processing logic based on document type
   - Example: `requestWrapper.getFileTitle()` to set chunk titles

### Development Tools
- **Testing**: Jest framework for unit testing
- **Code Quality**: ESLint for code linting
- **Development**: Nodemon for hot-reloading during development

### Scripts
- `npm start`: Launch the production server
- `npm run dev`: Start development server with hot-reload

### Dependencies
- **Production Dependencies**:
  - axios: ^1.6.7
  - formidable: ^3.5.1

- **Development Dependencies**:
  - eslint: ^8.56.0
  - jest: ^29.7.0
  - nodemon: ^3.0.3

### License
ISC License

---

For more information about using the SDK, please refer to the documentation.
To report issues or contribute to the project, please visit our repository. 