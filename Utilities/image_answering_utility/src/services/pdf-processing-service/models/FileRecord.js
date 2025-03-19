const mongoose = require('mongoose');

const fileRecordSchema = new mongoose.Schema({
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
    filePath: String,
    originalPath: String,
    status: {
        type: String,
        enum: ['processing', 'completed', 'failed'],
        default: 'processing'
    },
    startTime: {
        type: Date,
        default: Date.now
    },
    completedTime: Date,
    lastUpdated: {
        type: Date,
        default: Date.now
    },
    error: String,
    s3Url: String
});

// Update lastUpdated timestamp before saving
fileRecordSchema.pre('save', function(next) {
    this.lastUpdated = new Date();
    next();
});

const FileRecord = mongoose.model('FileRecord', fileRecordSchema);

module.exports = { FileRecord }; 