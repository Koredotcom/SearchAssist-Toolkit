# Question Generation Configuration Documentation

This document explains all the configuration parameters in the `question_generation` section of `config.json`.

## Core Parameters

### `num_questions` (default: 100)
- **Purpose**: Number of evaluation questions to generate
- **Usage**: Controls the total number of questions created for evaluation

### `chunks_per_question` (default: 50)
- **Purpose**: Number of chunks to fetch from API per question (also used as API limit)
- **Usage**: Determines how many chunks are retrieved from the chunk list API for each question

### `questions_per_batch` (default: 5)
- **Purpose**: Number of questions to generate in each batch (for parallel processing)
- **Usage**: Controls concurrency and batch processing for question generation

### `min_chunks_per_question` (default: 1)
- **Purpose**: Minimum chunks required per question (if fewer chunks available, still proceed)
- **Usage**: Sets the lower bound for chunks needed to generate a question

### `max_chunks_per_question` (default: 10)
- **Purpose**: Maximum chunks to use per question (limits chunks_per_question if needed)
- **Usage**: Caps the number of chunks actually used for question generation

## API and Retry Configuration

### `max_pagination_attempts` (default: 10)
- **Purpose**: Maximum attempts when paginating through chunk list API
- **Usage**: Controls how many times to retry chunk fetching with different skip values

### `max_api_retries` (default: 3)
- **Purpose**: Maximum retries for individual API calls (LLM, chunk list API)
- **Usage**: Number of times to retry a single API call when it fails

### `max_generation_attempts` (default: 20)
- **Purpose**: Maximum attempts for entire question generation process
- **Usage**: Controls how many complete generation cycles to attempt to get the target number of questions

## LLM Configuration

### `llm_temperature` (default: 0.7)
- **Purpose**: LLM temperature for question generation (0.0 = deterministic, 1.0 = creative)
- **Usage**: Controls randomness in question generation

### `llm_max_tokens` (default: 100)
- **Purpose**: Maximum tokens for LLM responses
- **Usage**: Limits the length of generated questions

## Content Processing

### `target_specific_data` (default: false)
- **Purpose**: Whether to target specific data chunks or use random chunks
- **Usage**: Controls chunk selection strategy

### `elaborate_queries` (default: false)
- **Purpose**: Generate elaborate queries (detailed) vs simple queries (concise)
- **Usage**: Controls the complexity and length of generated questions

### `default_total_chunks` (default: 10000)
- **Purpose**: Default total chunks available (used when API doesn't provide count)
- **Usage**: Fallback value for chunk count estimation

### `min_chunks_for_generation` (default: 3)
- **Purpose**: Minimum chunks needed to attempt question generation
- **Usage**: Prevents generation with insufficient content

## Language Filtering

### `language_filter.enabled` (default: true)
- **Purpose**: Enable/disable language filtering
- **Usage**: Master switch for language-based chunk filtering

### `language_filter.target_language` (default: "en")
- **Purpose**: Target language for generated questions
- **Usage**: Specifies the language for question generation

### `language_filter.allowed_languages` (default: ["en"])
- **Purpose**: List of allowed languages for chunk filtering
- **Usage**: Controls which language chunks are included

### `language_filter.exclude_code_content` (default: true)
- **Purpose**: Exclude chunks that contain code content
- **Usage**: Filters out code-heavy chunks from question generation

## API Configuration

### `chunk_list_api.url_template` (default: "https://{domain}/api/public/bot/{streamId}/chunk/list")
- **Purpose**: URL template for chunk list API (domain and streamId are replaced)
- **Usage**: Template for constructing the chunk list API endpoint

## Usage Examples

### For High-Quality Questions (Conservative)
```json
{
  "num_questions": 50,
  "chunks_per_question": 100,
  "llm_temperature": 0.3,
  "elaborate_queries": true,
  "max_api_retries": 5
}
```

### For Fast Generation (Aggressive)
```json
{
  "num_questions": 200,
  "chunks_per_question": 20,
  "llm_temperature": 0.8,
  "elaborate_queries": false,
  "max_api_retries": 2
}
```

### For Multi-Language Support
```json
{
  "language_filter": {
    "enabled": true,
    "target_language": "en",
    "allowed_languages": ["en", "es", "fr"],
    "exclude_code_content": true
  }
}
``` 