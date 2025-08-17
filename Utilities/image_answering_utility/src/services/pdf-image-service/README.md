# PDF Image Service

A robust Node.js service for converting PDF files to high-quality images with AWS S3 integration.

## Features

- Convert PDF files to high-quality PNG images
- Concurrent processing with configurable limits
- Automatic AWS S3 upload with presigned URLs
- Optional base64 image data output
- Temporary file management and cleanup
- GraphicsMagick integration for image processing
- Comprehensive error handling and logging

## Prerequisites

- Node.js (v14 or higher recommended)
- GraphicsMagick (`gm`) must be installed on the system
- AWS S3 bucket and credentials configured
- Sufficient storage space for temporary file processing

## Installation

1. Install GraphicsMagick on your system:
   bash
   # For Ubuntu/Debian
   sudo apt-get install graphicsmagick

   # For macOS
   brew install graphicsmagick
   

2. Install Node.js dependencies:
   bash
   npm install
   

## Configuration

### S3 Configuration

Configure your AWS S3 settings in `config/s3Config.js`:
- Bucket name
- Region
- Access credentials
- Default folder path
- URL expiration time for presigned URLs

### Environment Variables

The service supports customization of PDF to image conversion settings through environment variables. Create a `.env` file in the `config` directory with the following variables:


# PDF & Image Processing Configuration
PDF_IMAGE_DENSITY=150      # DPI setting for image conversion
PDF_IMAGE_FORMAT=png       # Output image format
PDF_IMAGE_WIDTH=1200      # Maximum width of output images
PDF_IMAGE_HEIGHT=1600     # Maximum height of output images
PDF_IMAGE_QUALITY=80      # Image quality (1-100)
PDF_PRESERVE_ASPECT_RATIO=true  # Maintain original aspect ratio


All environment variables are optional and have default values:
- `PDF_IMAGE_DENSITY`: Default 150 DPI
- `PDF_IMAGE_FORMAT`: Default 'png'
- `PDF_IMAGE_WIDTH`: Default 1200px
- `PDF_IMAGE_HEIGHT`: Default 1600px
- `PDF_IMAGE_QUALITY`: Default 80
- `PDF_PRESERVE_ASPECT_RATIO`: Default true



### Response Format

The service returns an array of processed pages with the following structure:

javascript
[
    {
        page_number: 1,
        image_url: "https://s3-presigned-url...",
        base64_data: "base64_string..."  // if includeBase64 is true
    },
    // ... additional pages
]


## Architecture

The service is organized into several components:

- **ImageController**: Main entry point for the service
- **PDFImageService**: Core conversion and processing logic
- **StorageManager**: Handles temporary file operations
- **S3Config**: AWS S3 configuration and client setup

## Error Handling

The service includes comprehensive error handling for:
- Missing dependencies
- File access issues
- PDF conversion failures
- S3 upload errors
- Cleanup operations

All errors are logged using the built-in logger utility.

## Performance

- Configurable concurrency limit (default: 3 concurrent processes)
- Batch processing for memory efficiency
- Automatic cleanup of temporary files
- Optimized image quality settings (150 DPI, 80% quality)

## Image Processing Settings

Default image conversion settings:
- Format: PNG
- Density: 150 DPI
- Width: 1200px
- Height: 1600px
- Quality: 80%
- Aspect Ratio: Preserved





