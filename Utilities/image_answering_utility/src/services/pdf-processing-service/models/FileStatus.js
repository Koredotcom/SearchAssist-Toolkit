const mongoose = require('mongoose');

const fileStatusSchema = new mongoose.Schema({
    uniqueId: {
        type: String,
        required: true,
        unique: true,
        index: true
    },
    filename: {
        type: String,
        required: true
    },
    status: {
        type: String,
        enum: ['processing', 'completed', 'failed'],
        default: 'processing'
    },
    s3Url: String,
    error: String,
    createdAt: {
        type: Date,
        default: Date.now
    },
    updatedAt: {
        type: Date,
        default: Date.now
    }
});

fileStatusSchema.pre('save', function(next) {
    this.updatedAt = new Date();
    next();
});

const FileStatus = mongoose.model('FileStatus', fileStatusSchema);

module.exports = { FileStatus }; 