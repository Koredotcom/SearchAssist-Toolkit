const cors = require("cors");
const express = require("express");
const bodyparser = require("body-parser");

const app=express();
app.use(cors({
    origin: '*'
}));
app.use(bodyparser.urlencoded({extended : true}));
app.use(bodyparser.json());
app.use(require("./controller/search"));

app.listen(3100,()=>{
    console.log("running on port 3100");
});