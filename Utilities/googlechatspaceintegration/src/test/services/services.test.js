const fs = require('fs').promises;
const path = require('path');

jest.mock('fs', () => ({
    promises: {
        writeFile: jest.fn()
    }
}));

jest.mock('@google-cloud/local-auth', () => ({
    authenticate: jest.fn()
}));

const servicesMockObject = require('./servicesMockData');
const {formatAndStoreMessages} = require('../../services/services');

describe('Testing the format of messages', () => {

    afterEach(() => {
        jest.clearAllMocks();
    });

    test('Test the json format', async () => {
        const messages = servicesMockObject.formatAndStoreMessages.messages;
        const filename = servicesMockObject.formatAndStoreMessages.filename;
        const hasCreateTime = servicesMockObject.formatAndStoreMessages.hasCreateTime;
        const expectedMessages = servicesMockObject.formatAndStoreMessages.expectedMessages;

        await formatAndStoreMessages(messages,filename,hasCreateTime);

        const jsonFilePath = path.join(__dirname, `../../json/${filename}.json`);
        expect(fs.writeFile).toHaveBeenCalledWith(jsonFilePath, JSON.stringify(expectedMessages, null, 4));
    });
});