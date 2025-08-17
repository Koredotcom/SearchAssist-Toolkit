require('dotenv').config();

module.exports = {
    uri: process.env.MONGODB_URI || 'mongodb://127.0.0.1:27017/pdf-processor',
    options: {
        useNewUrlParser: true,
        useUnifiedTopology: true
    }
}; 