const config = require("../config");
const constants = require("../constants/search");
const axios = require("axios");
const baseService = require("./baseService");

exports.getConnector = async (type) => {
    const url = constants.CONNECTOR_API.url.replace("{hostUrl}", config.hostUrl).replace("{streamId}", config.streamId);
    const response = await axios.get(url, {
        headers: {
            "auth": `${config.jwt}`,
            'Accept': 'application/json',
            "Content-Type": "application/json"
        }
    });
    const connectors = response.data?.connectors;
    let requestedConnector = null;
    for (const connector of connectors) {
        if (connector.type === type) {
            requestedConnector = connector;
            break;
        }
    }
    return requestedConnector;
}

exports.getPermissionEntities = async (connectorId) => {
    let recordsAvailable = true;
    const limit = 50;
    let offset = 0;
    const permissionEntities = [];
    while (recordsAvailable) {
        const url = constants.PERMISSION_ENTITIES.url.replace("{hostUrl}", config.hostUrl).replace("{streamId}", config.streamId).replace("{connectorId}", connectorId);
        const response = await axios.get(url, {
            params: {
                limit: limit,
                offset: offset
            },
            headers: {
                "auth": `${config.jwt}`,
                "Content-Type": "application/json"
            }
        });
        permissionEntities.push(...response.data);
        if (response.data.length < limit) {
            recordsAvailable = false;
        }
        offset += limit;
    }
    return permissionEntities;
}

exports.onboardUser = async (req, res) => {
    try {
        let { type, accessToken } = req.body;
        const connector = await this.getConnector(type);
        const permissionEntities = await this.getPermissionEntities(connector?._id);
        let credentials = null;
        if (!accessToken) {
            credentials = await this.getCredentials(connector?._id, config.streamId);
            accessToken = credentials?.tokenCredentials?.accessToken;
        }
        const connectorService = baseService.getService(type);
        for (const entity of permissionEntities) {
            let users = [];
            users = await connectorService.getUsers(connector, entity, accessToken);

            if (users.length === 0) continue;

            const onboardUrl = constants.ONBOARD_USER.url.replace("{hostUrl}", config.hostUrl).replace("{streamId}", config.streamId).replace("{connectorId}", connector?._id).replace("{permissionEntityId}", entity.entityId);
            const response = await axios.put(onboardUrl,
                {
                    userList: users
                },
                {
                    headers: {
                        "auth": `${config.jwt}`,
                        "Content-Type": "application/json"
                    }
                });
            console.log(response.data);
        }
        return res.status(200).json({ message: "Users onboarded successfully" });
    } catch (error) {
        console.log(error);
        return res.status(500).json({ message: "Error onboarding users" });
    }
}

exports.getCredentials = async (connectorId, streamId) => {
    const url = constants.CREDENTIALS_API.url.replace("{hostUrl}", config.hostUrl).replace("{connectorId}", connectorId).replace("{streamId}", streamId);
    const response = await axios.get(url, {
        headers: {
            "apiKey": `${config.apiKey}`,
            "Content-Type": "application/json"
        }
    });
    return response.data;
}
