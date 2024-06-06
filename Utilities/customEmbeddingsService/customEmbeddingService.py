from flask import Flask, jsonify, request
from tornado.httpserver import HTTPServer
from tornado.wsgi import WSGIContainer
from tornado.ioloop import IOLoop
from transformers import AutoTokenizer, AutoModel
import torch
import traceback
import re
import nltk
from sentence_transformers import SentenceTransformer
from flask import request, make_response
import json
import openai
openai.api_key = "OpenAI-key"

app = Flask(__name__)

# # Load the Hugging Face model
# tokenizer = AutoTokenizer.from_pretrained("model_name")
# model = AutoModel.from_pretrained("model_name")

from sentence_transformers import SentenceTransformer

e5_model_path = "/var/www/multilingual-e5-base"

model_dict ={
    "e5Base": SentenceTransformer(e5_model_path)
}

# Function to load the Hugging Face model based on the provided model name
def load_model(model_name):
    encoder= model_dict.get(model_name)
    return encoder

def get_combined_sentences( max_seq_length, sentences):
        combined_sentences = list()
        try:
            prev_sentence = ""
            prev_len = 0
            for i in range(len(sentences)):
                curr_sentence = sentences[i]
                curr_len = len(nltk.word_tokenize(curr_sentence))
                if curr_len > max_seq_length:
                    combined_sentences.append(prev_sentence)
                    combined_sentences.append(curr_sentence)
                    prev_sentence = ""
                    prev_len = 0
                elif prev_len + curr_len > max_seq_length:
                    combined_sentences.append(prev_sentence)
                    prev_sentence = curr_sentence
                    prev_len = curr_len
                else:
                    prev_sentence += curr_sentence
                    prev_len += curr_len

            if prev_sentence:
                combined_sentences.append(prev_sentence)
        except Exception as e:
            print(traceback.format_exc())
        return combined_sentences


def split_sentences(max_seq_length, sentences):
    processed_sentences = []
    try:
        for text in sentences:
            if isinstance(text, str) and len(text.split()) > max_seq_length:
                sentences = list(re.findall(r'[^!?。.？！]+[!?。.？！]?', text.replace('\n', ' ')))
                combined_sentences = get_combined_sentences(max_seq_length, sentences)
                processed_sentences.append(combined_sentences)
            else:
                processed_sentences.append(text)
    except Exception as e:
        print(traceback.format_exc())
    return processed_sentences

def generate_ada_embeddings(sentences):
    embeddings = list()
    for text in sentences:
        response = openai.embeddings.create(input=text, model='text-embedding-ada-002')
        embedding = response.data[0].embedding
        embeddings.append(embedding)
    return embeddings

# Function to generate embeddings
def generate_embeddings(sentence_list, model_name):
    if model_name == "ADA":
        embeddings = generate_ada_embeddings(sentence_list)
    else:
        encoder = load_model(model_name)
        max_seq_length = 512
        sentences = split_sentences(max_seq_length, sentence_list)
        embeddings = encoder.encode(sentences, batch_size=1)
        embeddings = embeddings.tolist()
    return embeddings

# Route to handle requests using Flask
@app.route('/generate_embeddings', methods=['POST'])
def handle_request():
    try:
        data = request.get_json()
        print("sentence vector gen req payload: ", data)
        text = data.get("sentences", [""])
        model_name = data.get("model_name", [""])
        embeddings = generate_embeddings(text, model_name)
        response = {"embeddings": embeddings}
        response = make_response(json.dumps(response), response.get("status_code", 200))
        response.headers['Content-Type'] = 'application/json'
        return response
    except Exception as e:
        print("Sentence vector gen failed with an error: \n",traceback.format_exc())
        response = {"embeddings": [0]}
        response = make_response(json.dumps(response), response.get("status_code", 400))
        response.headers['Content-Type'] = 'application/json'
        return response

if __name__ == '__main__':
    # Create a Tornado WSGIContainer for Flask
    flask_app = WSGIContainer(app)

    # Create a Tornado HTTPServer with Flask application
    server = HTTPServer(flask_app)

    # Start the Tornado server
    server.listen(5000)
    print("=="*5," Custom Embeddings server started ", "=="*5)
    # Start the Tornado IOLoop
    IOLoop.current().start()
