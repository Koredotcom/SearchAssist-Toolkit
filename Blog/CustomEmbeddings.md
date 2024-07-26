
# Custom Embeddings Support in SearchAssist

## Introduction

In the world of search technology, delivering accurate and relevant results is paramount. Unlike traditional search methods, which rely on keyword matching, semantic search understands the context and meaning behind the words, delivering more relevant and accurate results. Default embedding models in SearchAssist serve most clients well, offering robust semantic search capabilities by transforming text data into meaningful vector representations. However, as data continues to expand and diversify, challenges arise. What if your application involves highly specialized, domain-specific data that isn't covered by our default models? This gap can lead to less accurate search results, impacting user experience and satisfaction.

To address this challenge, we introduce Custom Embeddings Support in SearchAssist. This powerful feature allows you to integrate any custom embedding model, providing the flexibility needed to handle unique and specialized data. By leveraging custom embeddings, you can ensure that your search functionality is not only effective but also finely tuned to your specific requirements.

For a detailed explanation of what embeddings are and how they work, you can refer to this [comprehensive guide on Hugging Face](https://huggingface.co/blog/getting-started-with-embeddings).

## Custom Embeddings Support in SearchAssist

Custom Embeddings Support in SearchAssist allows you to use your preferred embedding models instead of the default ones. This flexibility is crucial for applications requiring specialized embeddings to improve search accuracy and relevance. With this feature, you can integrate any custom embedding model through an API, enhancing your application's ability to handle unique data and deliver precise search results.

By using custom embeddings, you can tailor the search functionality to better align with your specific data and use cases. Whether your data is from a specialized domain or requires unique processing, custom embeddings ensure that SearchAssist can meet your needs effectively.

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