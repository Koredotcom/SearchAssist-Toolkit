# Universal Connector Integration API for Kore.ai

This Node.js Express API serves as a universal integration system between various collaboration platforms and Kore.ai (conversational AI platform). It provides functionality to onboard users from different connector platforms to Kore.ai search connectors using an extensible architecture.

**Currently Supported Connectors:**
- LumApps (collaboration platform)

**Extensible Design:** The system is designed to support any connector type by simply adding two files per connector.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Adding New Connectors](#adding-new-connectors)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## 🔍 Overview

The application provides:
- **Universal Connector Architecture**: Extensible system supporting multiple collaboration platforms
- **Kore.ai Integration**: Seamless connection to Kore.ai search connectors and permission entities
- **User Onboarding**: Automated user onboarding from various platforms to Kore.ai
- **RESTful API**: Simple API endpoints for managing integrations
- **Easy Extension**: Add new connectors by creating just two files (constants + service)

### Architecture Benefits:
- **Modular Design**: Each connector is self-contained
- **Scalable**: Add unlimited connector types without modifying core logic
- **Maintainable**: Clear separation of concerns between connectors
- **Flexible Authentication**: Support for both config-based and request-based authentication

## 🛠 Prerequisites

Before setting up the application, ensure you have the following installed:

- **Node.js** (v14 or higher)
- **npm** (comes with Node.js)
- Access to your collaboration platform(s) (e.g., LumApps, Slack, Microsoft Teams, etc.)
- Access to Kore.ai platform with valid credentials
- API credentials for your connector platform(s)

## 📦 Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd /path/to/lumapps_racl
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

   This will install the following dependencies:
   - `express` - Web framework for Node.js
   - `axios` - HTTP client for API requests
   - `body-parser` - Parse incoming request bodies
   - `cors` - Enable Cross-Origin Resource Sharing

## ⚙️ Configuration

### 1. Update Configuration File

The application uses `config.js` for configuration. Update the following parameters with your actual credentials:

```javascript
module.exports = {
    hostUrl: "<hostUrl>",                       // Kore.ai platform URL (e.g., "https://platform.kore.ai")
    streamId: "<streamId>",                     // Your Kore.ai stream ID
    jwt: "<jwt>",                               // JWT token for authentication
    apiKey: "<apiKey>"                          // API key for Kore.ai (optional - not required if you pass accessToken in request body)
}
```

**Note:** The `apiKey` field is optional. You can either:
- Configure the `apiKey` in the config file for automatic authentication, OR
- Pass the `accessToken` in the request body when calling the API endpoints

### 2. Environment-specific Configuration (Recommended)

For production deployments, consider using environment variables:

Create a `.env` file (not included in the repository):
```env
KORE_HOST_URL=https://platform.kore.ai
KORE_STREAM_ID=your-stream-id
KORE_JWT_TOKEN=your-jwt-token
KORE_API_KEY=your-api-key  # Optional - leave empty if using request-based authentication
PORT=3100
```

Then update `config.js` to use environment variables:
```javascript
module.exports = {
    hostUrl: process.env.KORE_HOST_URL || "https://platform.kore.ai",
    streamId: process.env.KORE_STREAM_ID,
    jwt: process.env.KORE_JWT_TOKEN,
    apiKey: process.env.KORE_API_KEY || ""  // Optional - can be empty string
}
```

## 🚀 Running the Application

### Development Mode

```bash
npm start
```

Or directly with Node.js:
```bash
node index.js
```

The application will start on **port 3100** by default.

You should see the following output:
```
running on port 3100
```

### Production Mode

For production deployment, consider using process managers like PM2:

```bash
# Install PM2 globally
npm install -g pm2

# Start the application with PM2
pm2 start index.js --name "lumapps-racl"

# View logs
pm2 logs lumapps-racl

# Restart the application
pm2 restart lumapps-racl
```

## 🔌 API Endpoints

### Base URL
```
http://localhost:3100
```

### Available Endpoints

#### `PUT /onboard-users`
Onboards users from any supported connector platform (communities/groups/channels) to Kore.ai search connectors.

**Authentication Options:**
The API supports two authentication methods:
1. **Config-based**: Set `apiKey` in `config.js` - no need to pass `accessToken` in request
2. **Request-based**: Pass `accessToken` in request body if `apiKey` is not configured

**Request Body:**
```json
{
    "type": "connector-type",
    "accessToken": "platform-access-token" // Optional - Required only if apiKey is not configured in config.js
}
```

**Parameters:**
- `type` (required): The connector type (e.g., "lumapps", "slack", "teams", etc.)
- `accessToken` (conditional): Platform-specific access token - required if `apiKey` is not provided in config.js

**Response:**
- **200 OK**: Users onboarded successfully
- **500 Internal Server Error**: Error onboarding users

**Example Requests:**

*With accessToken (when apiKey not configured):*
```bash
# For LumApps connector
curl -X PUT http://localhost:3100/onboard-users \
  -H "Content-Type: application/json" \
  -d '{
    "type": "lumapps",
    "accessToken": "your-lumapps-access-token"
  }'

# For other connectors (example)
curl -X PUT http://localhost:3100/onboard-users \
  -H "Content-Type: application/json" \
  -d '{
    "type": "slack",
    "accessToken": "your-slack-access-token"
  }'
```

*Without accessToken (when apiKey is configured in config.js):*
```bash
curl -X PUT http://localhost:3100/onboard-users \
  -H "Content-Type: application/json" \
  -d '{
    "type": "lumapps"
  }'
```

## 🔧 Adding New Connectors

The system is designed for easy extensibility. To add a new connector, you only need to create **two files**:

### Step 1: Add Constants File
Create a new file in `constants/` directory:

**Example: `constants/slack.js`**
```javascript
module.exports = {
    SLACK_USERS_API: {
        url: "https://slack.com/api/users.list",
        method: "GET"
    },
    SLACK_CHANNELS_API: {
        url: "https://slack.com/api/conversations.list", 
        method: "GET"
    }
    // Add other Slack-specific API endpoints
}
```

### Step 2: Add Service File
Create a new file in `services/` directory:

**Example: `services/slackservice.js`**
```javascript
const axios = require("axios");
const constants = require("../constants/slack");

exports.getUsersByChannelId = async (hostUrl, channelId, accessToken) => {
    // Implement Slack-specific logic to fetch users
    const response = await axios.get(constants.SLACK_USERS_API.url, {
        headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
        }
    });
    
    // Transform response to match expected format
    return response.data.members.map(member => ({
        userId: member.id,
        email: member.profile.email,
        // ... other required fields
    }));
};

exports.getUsersByCommunityId = async (hostUrl, communityId, accessToken) => {
    // Implement community-specific logic if applicable
    // Or reuse getUsersByChannelId if communities are channels
    return this.getUsersByChannelId(hostUrl, communityId, accessToken);
};
```

### Step 3: Update Search Service (Optional)
If your connector requires special handling, you may need to update the logic in `services/searchservice.js` in the `onboardUser` function:

```javascript
// In services/searchservice.js - onboardUser function
for (const entity of permissionEntities) {
    let users = [];
    if(entity.type === "group") {
        if (type === "lumapps") {
            users = await lumappsService.getUsersByFeedId(connector?.configuration?.hostUrl, entity.entityId, accessToken);
        } else if (type === "slack") {
            users = await slackService.getUsersByChannelId(connector?.configuration?.hostUrl, entity.entityId, accessToken);
        }
        // Add more connector types as needed
    }
    // ... rest of the logic
}
```

### Connector Requirements
Each connector service should implement:
- `getUsersByFeedId()` or equivalent for group-type entities
- `getUsersByCommunityId()` or equivalent for community-type entities
- Return user objects in the expected format with required fields

### That's it! 
Your new connector is now ready to use. Simply call the API with `"type": "your-connector-name"`.

## 📁 Project Structure

```
lumapps_racl/
├── config.js                 # Configuration file
├── index.js                  # Main application entry point
├── package.json              # Project dependencies and metadata
├── package-lock.json         # Locked dependency versions
├── controller/
│   └── search.js            # Search controller routes (universal)
├── services/
│   ├── searchservice.js     # Core search service logic (universal)
│   └── lumappsservice.js    # LumApps connector implementation
│   └── [connector]service.js # Additional connector implementations
├── constants/
│   ├── search.js           # Core API endpoint constants
│   └── lumapps.js          # LumApps-specific constants
│   └── [connector].js      # Additional connector constants
└── README.md               # This documentation file
```

### File Structure Explanation:
- **Core Files** (`config.js`, `index.js`, `controller/search.js`, `services/searchservice.js`): Universal logic that works with all connectors
- **Connector-Specific Files**: Each connector has its own service file in `services/` and constants file in `constants/`
- **Extensible Pattern**: Add new connectors by creating `[connector]service.js` and `[connector].js` files

## 🔧 Troubleshooting

### Common Issues

1. **Port 3100 already in use:**
   ```bash
   # Find the process using port 3100
   lsof -i :3100
   
   # Kill the process (replace PID with actual process ID)
   kill -9 <PID>
   ```

2. **Authentication errors:**
   - Verify your JWT token in `config.js`
   - **For config-based auth**: Ensure your API key is correctly set in `config.js`
   - **For request-based auth**: Ensure you're passing a valid `accessToken` in the request body
   - Ensure your Kore.ai credentials have the necessary permissions
   - Check if tokens have expired
   - **Note**: You must use either `apiKey` in config OR `accessToken` in request - not both

3. **CORS issues:**
   - The application is configured to allow all origins (`origin: '*'`)
   - Modify CORS settings in `index.js` if needed for production

4. **Connection timeouts:**
   - Verify network connectivity to Kore.ai and your connector platforms
   - Check if your firewall allows outbound HTTPS connections
   - Ensure API endpoints for your specific connector are accessible

### Debug Mode

To enable detailed logging, you can modify the application to include debug statements or use Node.js debugging:

```bash
# Run with Node.js debugging
node --inspect index.js

# Or with additional environment variable
DEBUG=* node index.js
```

### Logs

Monitor application logs for errors:
- Console output shows basic application status
- Add custom logging as needed for your debugging requirements

## 📝 Notes

- **Universal Architecture**: The system supports any connector type - simply add two files per connector
- **Authentication Flexibility**: The application supports two authentication methods:
  - **Config-based**: Set `apiKey` in `config.js` for automatic authentication
  - **Request-based**: Pass `accessToken` in API request body for per-request authentication
- **Extensibility**: Adding new connectors requires only:
  - Constants file in `constants/[connector].js`
  - Service file in `services/[connector]service.js`
  - Optional updates to `searchservice.js` for special handling
- Ensure proper network connectivity to both your connector platforms and Kore.ai
- Keep your API credentials secure and never commit them to version control
- Consider implementing rate limiting for production deployments
- The application uses CORS with `origin: '*'` - modify this for production security

## 🤝 Support

For issues related to:
- **Connector integrations**: Consult the specific platform's API documentation
- **Kore.ai integration**: Refer to Kore.ai platform documentation
- **Adding new connectors**: Follow the extensibility guide in this README
- **Application bugs**: Check the console logs and verify configuration settings
- **Architecture questions**: Review the universal connector design pattern 