const lumappsService = require("./lumappsservice");

exports.getService = (connectorType) => {
    switch(connectorType){
        case "lumapps":
            return lumappsService;
        default:
            return null;
    }
}
