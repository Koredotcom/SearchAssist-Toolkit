const mongoose = require('mongoose');

const threadSchema = mongoose.Schema({
    name: { type: String, unique: true },
    messages: [String],
    createTime: Number
});

const threadModel = mongoose.model('threads', threadSchema);

module.exports = threadModel;