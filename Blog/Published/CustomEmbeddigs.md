
# Custom Embeddings Support in SearchAssist
*Author: Riyaz Ahmed*

## Introduction

Semantic search surpasses traditional keyword matching by understanding context and meaning. While SearchAssist's default embedding models offer robust capabilities, highly specialized, domain-specific data can challenge these models. To address this, we introduce Custom Embeddings Support in SearchAssist, allowing the integration of any custom embedding model to handle unique and specialized data effectively.

For a detailed explanation of what embeddings are and how they work, you can refer to this [comprehensive guide on Hugging Face](https://huggingface.co/blog/getting-started-with-embeddings).

## Custom Embeddings Support in SearchAssist

Custom Embeddings Support in SearchAssist allows you to use your preferred embedding models instead of the default ones. This flexibility is crucial for improving search accuracy and relevance for specialized applications. You can integrate any custom embedding model through an API, enhancing your application's ability to handle unique data and deliver precise search results.

By leveraging custom embeddings, you can ensure your search functionality is finely tuned to your specific requirements. This capability allows SearchAssist to effectively process specialized data, improving overall search performance and maintaining accuracy as data grows and diversifies.

## How to Integrate Custom Embeddings in SearchAssist

Integrating a custom embedding model in SearchAssist is straightforward. You need to configure the API parameters: `data`, `url`, and `headers`, and set the necessary configuration keys. Here’s a step-by-step guide:

### Step 1: Configure SearchAssist

To enable custom embeddings support in SearchAssist, set the following configuration keys:

- **dev_use_custom_vector_model**: Set this to `true` to enable the use of a custom vector model.
- **custom_vector_gen_payload**: Pass the API payload in this key.

### Step 2: Prepare Your API Request

To use a custom embedding model, you need to set up your API request as follows:

```json
{
    "url": "https://api-inference.huggingface.co/models/BAAI/bge-base-en-v1.5",
    "headers": {
        "Authorization": "Bearer hf_********"
    },
    "data": {
        "inputs": "{{sentences}}"
    },
    "resolver": "$[*]"
}
```

- **url**: This is the endpoint of the custom embedding model API you want to use.  
- **headers**: This includes the authorization token needed to access the API.  
- **data**: This contains the sentences or data points that SearchAssist will process to generate embeddings. The placeholder `{{sentences}}` should be used to denote where the actual sentences array will be passed.  
- **resolver**: This specifies the path to extract the embeddings from the API response.  

## Example Configurations

Here are two examples of configuring templates for different embedding services:

### Example 1: OpenAI Embeddings

For OpenAI embeddings, the configuration would be:

```json
{
    "url": "https://api.openai.com/v1/embeddings",
    "headers": {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-********"
    },
    "data": {
        "input": "{{sentences}}",
        "model": "text-embedding-3-small"
    },
    "resolver": "$..embedding"
}
```

### Example 2: Hugging Face API Embeddings

For Hugging Face API embeddings, the configuration would be:

```json
{
    "url": "https://api-inference.huggingface.co/models/BAAI/bge-base-en-v1.5",
    "headers": {
        "Authorization": "Bearer hf_********"
    },
    "data": {
        "inputs": "{{sentences}}"
    },
    "resolver": "$[*]"
}
```

## Conclusion

Custom Embeddings Support in SearchAssist empowers you to improve your search functionality by integrating any custom embedding model through an API. By configuring the necessary parameters (data, URL, headers) and utilizing the `{{sentences}}` placeholder, you can seamlessly enhance your application's search capabilities, providing a more accurate and relevant search experience for your users.