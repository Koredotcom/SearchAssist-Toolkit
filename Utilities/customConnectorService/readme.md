# Custom Connector SDK

## Overview
The **Custom Connector SDK** is designed for users who want to integrate custom connectors beyond the pre-built connectors in Search Assist. This SDK is built using **Node.js** and provides flexibility for extending the default functionalities of Search Assist.

## Project Structure

- customConnectorService
    - .env
    - config/
        - config.json
    - routes/
        - content.route.js
    - controllers/
        - content.controller.js
    - server.js
    - package.json

## Getting Started

### Clone the Repository
To get started with the Custom Connector SDK, clone the repository:

```
git clone git@bitbucket.org:koreteam1/searchassist-common.git
```
```
cd customConnectorService
```

### Install Dependencies
Once in the project directory, install the necessary dependencies:

```bash
npm install
```

### Packages Used
The SDK leverages the following Node.js packages:

- **dotenv**: For environment variable management.
- **axios**: For making HTTP requests.
- **express**: For setting up the server and API routes.

### Run the Server
To start the service, run the following command:

```bash
node server.js
```

## Code Changes to Use Custom Connector SDK
To integrate your custom connector, make the following code changes:

1. **config/config.json**: Contains configuration details such as API URL, authentication details, lookup fields, and optional incremental/deletion settings.
2. **.env**: Update the authorization key used to authorize incoming requests.
3. **content.controller.js**: Customize how data from your connector is handled and returned. Ensure that `isContentAvailable` is included in the response.

### Steps to Add a Custom Connector
1. **Prepare config.json**: Create a config file containing the authentication details, API URL, lookup fields, and other necessary settings for your connector. Place this file in `config/config.json`.

   **Sample config.json:**
   ```json
   {
     "name": "customConnector",
     "type": "customConnector",
     "authDetails": {
       "username": "YOUR_USERNAME",
       "password": "YOUR_PASSWORD",
       "authorizationType": "BasicAuth"
     },
     "configuration": {
       "api": {
         "contentUrl": "https://api.example.com/v1/documents",
         "method": "GET"
       },
       "pagination": {
         "limit": "limit",
         "offset": "offset"
       },
       "lookupFields": {
         "rootField": "data",
         "id": "id",
         "title": "title",
         "content": "body",
         "url": "url",
         "doc_created_on": "createdAt",
         "doc_updated_on": "updatedAt",
         "type": "type",
         "sys_racl": "permissions"
       },
       "deletionUrl": "https://api.example.com/v1/documents/deleted"
     }
   }
   ```

2. **Update .env**: Add or update the `Authorization` value in `.env`. This value is used when Search Assist calls the Custom Connector SDK.

3. **Update content.controller.js**: Modify `get_content_controller` if your source requires custom handling. Ensure that the response includes `isContentAvailable`.

   Note: `isContentAvailable` is mandatory because it tells Search Assist whether another page should be requested.

## API Endpoints
The SDK provides these API endpoints used by Search Assist:

### Get Content
This endpoint retrieves content based on the limit and offset parameters.

#### Sample CURL Request:
```bash
curl --location '{{protocol}}://{{hostname}}/getContent?limit=1&offset=0' \
--header 'Authorization: ENTER YOUR AUTH KEY'
```

#### Sample Response:
```json
{
    "data": [
        {
            "id": "doc-123",
            "title": "Getting started",
            "content": "...",
            "url": "https://api.example.com/docs/doc-123",
            "type": "article",
            "doc_created_on": "2024-01-12T13:11:58.000Z",
            "doc_updated_on": "2024-01-12T13:14:30.000Z",
            "sys_racl": ["*"]
        }
    ],
    "isContentAvailable": false
}
```

### Incremental Sync
During incremental sync, SearchAI sends `isIncremental=true` and `lastSyncTime` to `/getContent`.

```bash
curl --location '{{protocol}}://{{hostname}}/getContent?limit=30&offset=0&isIncremental=true&lastSyncTime=2025-11-19T11:46:04.830Z' \
--header 'Authorization: ENTER YOUR AUTH KEY'
```

If your source accepts these parameters directly, no extra configuration is required. Otherwise, configure `configuration.api.incrementalQuery`:

```json
"incrementalQuery": {
  "queryParam": "filter",
  "template": "updatedAt>={date}",
  "dateFormat": "YYYY-MM-DD HH:mm:ss",
  "separator": "^"
}
```

- **queryParam**: Source query parameter that carries the filter.
- **template**: Source-specific filter expression. `{date}` is replaced with `lastSyncTime`.
- **dateFormat**: Optional UTC format using `YYYY`, `MM`, `DD`, `HH`, `mm`, and `ss`. Omit it to use ISO format.
- **separator**: Optional separator used when appending the filter to an existing query.

Keep source-specific syntax inside `template`; no controller change is needed.

### Get Deleted Items
After an incremental sync, SearchAI calls this endpoint with `lastSyncTime`, `limit`, and `offset`.

#### Request
```bash
curl --location '{{protocol}}://{{hostname}}/getDeletedItems?lastSyncTime=2025-11-19T11:46:04.830Z&limit=30&offset=0' \
--header 'Authorization: ENTER YOUR AUTH KEY'
```

#### Response (required by SearchAI)
```json
{
  "ids": ["doc-123", "doc-456"],
  "isContentAvailable": false
}
```

Set `deletionUrl` in `config.json` to your source deleted-items API. If `deletionUrl` is omitted, the SDK returns an empty list.

If your source API already returns `{ "ids": [...], "isContentAvailable": true|false }`, no additional configuration is required.

If your source returns raw rows, configure `deletionQuery`:

```json
"deletionQuery": {
  "queryParam": "filter",
  "template": "deletedAt>={date}",
  "dateFormat": "YYYY-MM-DD HH:mm:ss",
  "fieldsParam": "fields",
  "rootField": "items",
  "idField": "documentId"
}
```

- **queryParam**: Source query parameter that carries the delete filter.
- **template**: Source-specific filter expression. `{date}` is replaced with `lastSyncTime`.
- **dateFormat**: Optional UTC date format. Omit it to use ISO format.
- **fieldsParam**: Optional parameter used to request only the id field.
- **rootField**: Response property containing deleted rows.
- **idField**: Property containing the deleted document id.

The deleted ids must match the ids returned by `/getContent`. For raw response rows, the SDK infers `isContentAvailable` from whether the returned page is full.

### Parameters:
- **limit**: The number of records to retrieve.
- **offset**: The starting point for the records.
- **isIncremental**: Indicates an incremental `/getContent` request.
- **lastSyncTime**: ISO timestamp of the last successful sync.

Note: For all endpoints, the Authorization header is mandatory. It should contain the Base64-encoded value of the authorization key set in the `.env` file.

## Testing the SDK

1. **Install Dependencies**:
   ```bash
   npm install
   ```

2. **Run the Server**:
   ```bash
   node server.js
   ```

3. **Send Test Requests**: Use an API client such as Postman to test `/getContent` and, when enabled, `/getDeletedItems`.

## Conclusion
The Custom Connector SDK provides a flexible way to integrate custom connectors into the Search Assist platform. Configure your API, field mappings, incremental query, and deletion query according to your source system.
