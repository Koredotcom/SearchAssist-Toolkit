const fs = require('fs').promises;
const path = require('path');
const axios = require('axios');
const { ChatServiceClient } = require('@google-apps/chat');
const authorize = require('../middlewares/authorize');
const { DateTime } = require('luxon');
const threadModel = require('../models/thread');

const SPACES_TOKEN_PATH = path.join(process.cwd(), './json/spacestoken.json');
const MESSAGES_TOKEN_PATH = path.join(process.cwd(), './json/messagesstoken.json');

exports.getAnswer = async (req, res) => {
    try {
        const message = req.body.message;
        const threadName = req.body.thread;
        const result = "this is a sample response";//Dharvik's end point
        await this.sendResponse(result, threadName);
        return res.status(200).json({ message: "Response sent successfully" });
    }
    catch(error) {
        res.status(500).json({error: error});
    }
}

exports.pushOneWeekThreads = async (req, res) => {
    try {
        const messages = await this.getLatestMessages(process.env.SPACE_NAME);
        await this.formatAndStoreMessages(messages,"latestmessages",true);
        await threadModel.deleteMany({});
        const filePath = './json/latestmessages.json';
        const data = await fs.readFile(filePath, 'utf8');
        const jsonData = JSON.parse(data);
        for (const thread in jsonData) {
            const entry = {
                name: thread,
                messages: jsonData[thread].threads,
                createTime: Number(jsonData[thread].createTime)
            }
            await threadModel.create(entry);
        }
        res.status(201).json({message: "Threads added successfully"});
    }
    catch (error) {
        res.status(500).json({error: error});
    }
}

exports.sendResponse = async (responseText, threadName) => {
    const url = process.env.WEBHOOK_URL;
    try {
        const res = await axios.post(url, {
            text: responseText,
            thread: {name: threadName}
        });
        return res;
    }
    catch (error) {
        if (axios.isAxiosError(error)) {
            console.error(`Axios request error: ${error.code}`);

            if (error.res) {
                console.error(`Status code: ${error.res.status}`);
                console.error(`res data: ${error.res.data}`);

            }
            else if (error.request) {
                console.error('No res received.');
            }
            else {
                console.error('Error setting up request:', error.message);

            }
        }
        else {
            console.error('Unexpected error:', error);
        }
    }
}

exports.getLatestMessages = async (spaceName) => {
    try {
        const SCOPES = ['https://www.googleapis.com/auth/chat.messages.readonly'];
        const authClient = await authorize(SCOPES, MESSAGES_TOKEN_PATH);

        const chatClient = new ChatServiceClient({
            authClient: authClient,
            scopes: SCOPES,
        });

        const request = {
            parent: spaceName,
            pageSize: 100000
        };

        const messages = []
        const oneWeekAgo = DateTime.now().minus({ days: 7 }) / 1000;

        const pageResult = chatClient.listMessagesAsync(request);

        for await (const response of pageResult) {

            const messageTime = response.createTime.seconds;
            console.log(messageTime + " " + oneWeekAgo);
            if (messageTime > oneWeekAgo) {
                messages.push(response);
            }
        }
        return messages;

    } catch (err) {
        console.error('Error fetching messages:', err);
        return null;
    }
}

exports.listSpaces = async () => {
    const SCOPES = ['https://www.googleapis.com/auth/chat.spaces.readonly'];
    const authClient = await authorize(SCOPES, SPACES_TOKEN_PATH);

    const chatClient = new ChatServiceClient({
        authClient: authClient,
        scopes: SCOPES,
    });

    const request = {
        // Filter spaces by space type (SPACE or GROUP_CHAT or DIRECT_MESSAGE)
        filter: 'space_type = "SPACE"'
    };

    const pageResult = chatClient.listSpacesAsync(request);

    for await (const response of pageResult) {
        console.log(response);
    }
}

exports.getAllMessages = async (spaceName) => {
    try {
        const SCOPES = ['https://www.googleapis.com/auth/chat.messages.readonly'];
        const authClient = await authorize(SCOPES, MESSAGES_TOKEN_PATH);

        const chatClient = new ChatServiceClient({
            authClient: authClient,
            scopes: SCOPES,
        });

        const request = {
            parent: spaceName
        };

        const messages = []

        const pageResult = chatClient.listMessagesAsync(request);

        for await (const response of pageResult) {
            console.log(response);
            messages.push(response);
        }
        return messages;

    } catch (err) {
        console.error('Error fetching messages:', err);
        return null;
    }
}

exports.formatAndStoreMessages = async (messages, filename, hasCreateTime) => {
    const threadText = {};

    messages.forEach(message => {
        const text = message.argumentText ? message.argumentText.trim() : "";
        if (message.quotedMessageMetadata) {
            const quotedThreadName = message.quotedMessageMetadata.name.split('.')[0];
            const threadName = quotedThreadName.split('messages')[0] + 'threads' + quotedThreadName.split('messages')[1];
            if (text) {
                if (hasCreateTime) {
                    if (!threadText[threadName]) {
                        threadText[threadName] = {
                            threads: new Set()
                        }
                    }
                    threadText[threadName].threads.add(text);
                    threadText[threadName].createTime = message.createTime.seconds;
                }
                else {
                    if (!threadText[threadName]) {
                        threadText[threadName] = new Set();
                    }
                    threadText[threadName].add(text);
                }
            }
        }
        else {
            const threadName = message.thread.name;
            if (text) {
                if (hasCreateTime) {
                    if (!threadText[threadName]) {
                        threadText[threadName] = {
                            threads: new Set()
                        }
                    }
                    threadText[threadName].threads.add(text);
                    threadText[threadName].createTime = message.createTime.seconds;
                }
                else {
                    if (!threadText[threadName]) {
                        threadText[threadName] = new Set();
                    }
                    threadText[threadName].add(text);
                }
            }
        }
    });

    const filteredThreads = {};
    for (const thread in threadText) {
        if (hasCreateTime) {
            if (threadText[thread].threads.size > 1) {
                filteredThreads[thread] = {
                    threads: Array.from(threadText[thread].threads),
                    createTime: threadText[thread].createTime
                }
            }
        }
        else {
            if (threadText[thread].size > 0) {
                filteredThreads[thread] = Array.from(threadText[thread]);
            }
        }
    }

    const jsonFilePath = path.join(__dirname, `../json/${filename}.json`);

    await fs.writeFile(jsonFilePath, JSON.stringify(filteredThreads, null, 4));
}

