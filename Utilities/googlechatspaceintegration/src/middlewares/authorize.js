const fs = require('fs').promises;
const path = require('path');
const process = require('process');
const { authenticate } = require('@google-cloud/local-auth');
const { auth } = require('google-auth-library');

const CREDENTIALS_PATH = path.join(process.cwd(), './json/credentials.json');

async function loadSavedCredentialsIfExist(TOKEN_PATH) {
    try {
        const content = await fs.readFile(TOKEN_PATH);
        const credentials = JSON.parse(content);
        return auth.fromJSON(credentials);
    } catch (err) {
        console.log(err);
        return null;
    }
}


async function saveCredentials(client, TOKEN_PATH) {
    const content = await fs.readFile(CREDENTIALS_PATH);
    const keys = JSON.parse(content);
    const key = keys.installed || keys.web;
    const payload = JSON.stringify({
        type: 'authorized_user',
        client_id: key.client_id,
        client_secret: key.client_secret,
        refresh_token: client.credentials.refresh_token,
    });
    await fs.writeFile(TOKEN_PATH, payload);
}

async function authorize(SCOPES,TOKEN_PATH) {
    let client = await loadSavedCredentialsIfExist(TOKEN_PATH);
    if (client) {
        return client;
    }
    client = await authenticate({
        scopes: SCOPES,
        keyfilePath: CREDENTIALS_PATH,
    });
    if (client.credentials) {
        await saveCredentials(client, TOKEN_PATH);
    }
    return client;
}

module.exports = authorize;