module.exports = {
    CONNECTOR_API: {
        url: "{hostUrl}/api/public/bot/{streamId}/connectors",
        method: "GET"
    },
    PERMISSION_ENTITIES: {
        url: "{hostUrl}/api/public/bot/{streamId}/connector/{connectorId}/permission-entities",
        method: "GET"
    },
    ONBOARD_USER: {
        url: "{hostUrl}/api/public/bot/{streamId}/connector/{connectorId}/permission-entities/{permissionEntityId}",
        method: "PUT"
    },
    CREDENTIALS_API: {
        url: "{hostUrl}/api/1.1/internal/streams/{streamId}/connectors/{connectorId}/connectorCredentials",
        method: "GET"
    }
}