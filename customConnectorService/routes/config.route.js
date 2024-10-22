const route = require('express').Router()
const { get_config_controller } = require("../controller/config.controller")
const { checkAuthorized } = require("../middleware/authorization")

//route  to create ticket
route.get('/searchAssistant/getConfig', checkAuthorized, get_config_controller)

module.exports = route