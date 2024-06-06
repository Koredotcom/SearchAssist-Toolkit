# Custom Embeddings Flask Application
This Flask application provides an API for generating embeddings for text data using different models. The generated embeddings can be utilized for various natural language processing tasks such as semantic similarity, clustering, and classification.

## Prerequisites
+
Python 3.6 or higher
+
pip package manager
+
Transformers library
+
Sentence Transformers library
+
Tornado web framework
+
NLTK (Natural Language Toolkit) library
Installation
## Clone the repository:

git clone https://github.com/yourusername/your-repository.git
Navigate to the project directory:

cd your-repository
Install the required dependencies:

pip install -r requirements.txt
Usage
Run the Flask application:

python app.py
The application will start and listen on port 5000 by default.

To generate embeddings, send a POST request to the /generate_embeddings endpoint with JSON payload containing the list of sentences and the desired model name.

### Example payload:

json

{
    "sentences": ["Sentence 1", "Sentence 2"],
    "model_name": "e5Base"
}
Replace "e5Base" with the name of the model you want to use.

The application will return JSON response containing the embeddings for the provided sentences.

### Example Output

{
    "embeddings": [
        0.004253577906638384,
        0.0143563412129879,
        -0.01487610675394535,
        0.08480880409479141,
        0.02371254935860634,
        -0.014803698286414146,
        -0.0041594249196350574,
        ...
    ]
}
