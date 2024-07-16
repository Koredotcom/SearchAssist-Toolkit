# How to Use Custom Embeddings Support in SearchAssist

We are excited to introduce a powerful new feature in SearchAssist: **Custom Embeddings Support**. This enhancement allows you to integrate any custom embedding model into SearchAssist using an API, enabling more tailored and effective search capabilities.

## What is Custom Embeddings Support?

Custom Embeddings Support in SearchAssist allows you to use your preferred embedding models instead of the default ones. This flexibility is crucial for applications requiring specialized embeddings to improve search accuracy and relevance.

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


**url**: This is the endpoint of the custom embedding model API you want to use.  
**headers**: This includes the authorization token needed to access the API.  
**data**: This contains the sentences or data points that SearchAssist will process to generate embeddings. The placeholder `{{sentences}}` should be used to denote where the actual sentences array will be passed.  
**resolver**: This specifies the path to extract the embeddings from the API response.  


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

## Step 4: Use Custom Embeddings in SearchAssist

Once configured, SearchAssist will utilize the custom embedding model in two critical phases:

1. **Training**: SearchAssist will use the custom embeddings on the ingested data to enhance the training process of your application. By leveraging specialized embeddings during training, you can improve the accuracy and effectiveness of your models.

2. **Searching**: When users interact with SearchAssist for queries or document searches, the configured custom embeddings will be used to generate embeddings in real-time. This ensures that the search results are more relevant and aligned with the specific requirements of your application.

## Benefits of Custom Embeddings Support

- **Flexibility**: Use any embedding model that suits your specific requirements.
- **Improved Accuracy**: Tailored embeddings can lead to more relevant and precise search results.
- **Enhanced Search Experience**: By customizing the embeddings, you can better address the unique needs of your users.

## Conclusion

Custom Embeddings Support in SearchAssist empowers you to improve your search functionality by integrating any custom embedding model through an API. By configuring the necessary parameters (data, URL, headers) and utilizing the `{{sentences}}` placeholder, you can seamlessly enhance your application's search capabilities, providing a more accurate and relevant search experience for your users.

