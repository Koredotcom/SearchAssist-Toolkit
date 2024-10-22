const express = require('express')
const app = express()
//basic config
app.use(express.urlencoded({ extended: true }));
app.use(express.json({ limit: '5mb' }))
require("dotenv").config()
//error handler middleware
app.use((err, req, res, next) =>{
    console.error(err.stack);

    // Set the response status code (default to 500 for server errors)
    const statusCode = err.statusCode || 500;

    // Send a JSON response with the error message
    res.status(statusCode).json({
        success: false,
        message: err.message || 'Internal Server Error',
    });
})

//route to home  page
app.get('/', (req, res) => {
    res.send('This Server Contains Custom Connector Service Endpoints')
})

//route to config endpoint
const config_endpoint = require('./routes/config.route.js')
app.use(config_endpoint)

//route to content api 
const content_endpoint = require('./routes/content.route.js')
app.use(content_endpoint)

app.listen(3232, () => {
    console.log('Server started Lisenting 🚀🚀🚀🚀')
})