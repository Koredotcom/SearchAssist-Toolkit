const express = require('express')
const dotenv = require('dotenv');
const configDB = require('./config/db');

const app = express()

dotenv.config();
configDB();

app.use(express.json())

app.use(require('./controllers/routes'));

app.listen(5000, ()=>{
    console.log("Server running");
});
