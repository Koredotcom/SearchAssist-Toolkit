const axios = require("axios");
const constants = require("../constants/lumapps");

exports.getUsersByFeedId = async (hostUrl, feedId, accessToken) => {
    const feeds = [];
    let cursor = true;
    while (cursor) {
        if (cursor === true) {
            cursor = '';
        }
        const url = constants.FEEDS_API_BY_ID.url.replace("{hostUrl}", hostUrl);
        const response = await axios.get(url, {
            params: {
                feeds: feedId,
                cursor: cursor
            },
            headers: {
                "Authorization": `Bearer ${accessToken}`,
                "Content-Type": "application/json"
            }
        });
        feeds.push(...response.data?.items);
        cursor = response.data?.cursor || false;
    }
    const users = feeds?.filter(feed => feed.email)?.map(feed => feed.email);
    return users;
}

exports.getUsersByCommunityId = async (hostUrl, communityId, accessToken) => {
    const users = [];
    let cursor = true;
    while (cursor) {
        if (cursor === true) {
            cursor = '';
        }
        const url = constants.COMMUNITY_API.url.replace("{hostUrl}", hostUrl);
        const response = await axios.post(url,
            {
                cursor: cursor,
                uid: communityId
            },
            {
                headers: {
                    "Authorization": `Bearer ${accessToken}`,
                    "Content-Type": "application/json"
                }
            });
        users.push(...response.data?.items);
        cursor = response.data?.cursor || false;
    }
    return users.filter(user => user.email)?.map(user => user.email);
}

exports.getUsers = async (connector, entity, accessToken) => {
    let users = [];
    if(entity.type === "group") {
        users = await lumappsService.getUsersByFeedId(connector?.configuration?.hostUrl, entity.entityId, accessToken);
   }
   else {
       users = await lumappsService.getUsersByCommunityId(connector?.configuration?.hostUrl, entity.entityId, accessToken);
   }
   return users || [];
}