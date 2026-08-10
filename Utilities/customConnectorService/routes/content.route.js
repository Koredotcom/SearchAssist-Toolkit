const route = require('express').Router()
const {
    get_content_controller,
    get_deleted_items_controller
} = require("../controller/content.controller")
const { checkAuthorized } = require("../middleware/authorization")

route.get('/getContent', checkAuthorized, get_content_controller)
route.get('/getDeletedItems', checkAuthorized, get_deleted_items_controller)

module.exports = route
