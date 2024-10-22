const route = require('express').Router()
const { get_content_controller } = require("../controller/content.controller")
const { checkAuthorized } = require("../middleware/authorization")

//route  to get content 
route.get('/searchAssistant/getContent', checkAuthorized, get_content_controller)

module.exports = route