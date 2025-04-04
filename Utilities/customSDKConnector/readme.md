# Custom SDK Connector for SearchAI
## Overview
The Custom SDK Connector is a flexible integration tool that enables seamless data ingestion from various sources into SearchAI. This SDK provides a standardized way to connect and ingest data from external sources while maintaining data structure and metadata integrity, optimized for enterprise RAG (Retrieval-Augmented Generation) applications.

![Architecture Flow](./Assets/flowchart.png)


## Prerequisites
- Node.js 
- SearchAI account with valid credentials
- Source-specific access tokens (e.g., OneNote access token)

## Installation

1. Clone the [repository](https://github.com/Koredotcom/SearchAssist-Toolkit.git):
```bash
git clone https://github.com/Koredotcom/SearchAssist-Toolkit.git
cd Utilities/customSDKConnector
```

2. Install dependencies:
```bash
npm install
```

3. Configure environment variables:
   - Copy `.env.sample` to `.env`
   - Fill in the required credentials:
     ```
     SEARCHAI_HOST_NAME = "Your SearchAI Host"
     SEARCHAI_JWT_TOKEN = "Your JWT Token"
     STREAM_ID = "Your Stream ID"
     INGESTION_BATCH_SIZE = "10"
     ```

## Example Usage

### OneNote Connector

The OneNote connector is included as an example implementation to demonstrate how to build a custom connector. You can find the complete code in `connectors/OneNoteConnector.js`. This connector shows how to:
- Extract content from OneNote notebooks, sections, and pages
- Transform document structure into SearchAI-compatible format
- Manage batch ingestion process to searchai

To run the ingestion after configuration:
```bash
node ingest.js
```

## Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| INGESTION_BATCH_SIZE | Number of chunks per ingestion request | 10 |
| SEARCHAI_HOST_NAME | SearchAI platform hostname | - |
| SEARCHAI_JWT_TOKEN | Authentication token | - |
| STREAM_ID | Target AppId / BotId | - |

## Extending the Connector

To add a new data source:

1. Create a new extractor in the `Extraction` folder
2. Implement the required extraction methodsp
3. Add formatting logic for the new source
4. Update the ingestion pipeline



## Contributing

We welcome contributions to this project! To contribute:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Make your changes and commit them with clear and descriptive messages.
4. Push your changes to your fork.
5. Open a pull request with a detailed description of your changes.


## Changelog

### v1.0.0
- Initial release
- OneNote connector implementation
- Batch processing support

