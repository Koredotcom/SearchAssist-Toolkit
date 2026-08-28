const mongoose = require("mongoose");

module.exports = async () => {
    try {
        mongoose.connect(process.env.MONGO_URL);
        console.log("connected to DB");
    }
    catch(error) {
        console.log("Error in connecting DB "+error);
    }
}