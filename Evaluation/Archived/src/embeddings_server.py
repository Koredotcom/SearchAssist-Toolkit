from flask import Flask, request, jsonify
import numpy as np
import re
import nltk
from sentence_transformers import SentenceTransformer
import os
 
# sync_model = SyncModel()
# os.environ['NLTK_DATA'] = '/home/Aakansh.Dudam/Documents/server'

app = Flask(__name__)

# model_path ="BAAI/bge-base-en"
model_path ="../multi-qa-mpnet-base-cos-v1"
# model_path = "/var/www/multi-qa-mpnet-base-cos-v1"

model_st = SentenceTransformer(model_path)

class EmbeddingGenerator:
    def __init__(self, model_path):
        self.model_st = SentenceTransformer(model_path)
    
    def get_combined_sentences(self, sentences):
        combined_sentences = list()
        prev_sentence = ""
        prev_len = 0
        for i in range(len(sentences)):
            curr_sentence = sentences[i]
            curr_len = len(nltk.word_tokenize(curr_sentence))
            if curr_len > 128:
                combined_sentences.append(prev_sentence)
                combined_sentences.append(curr_sentence)
                prev_sentence = ""
                prev_len = 0
            elif prev_len + curr_len > 128:
                combined_sentences.append(prev_sentence)
                prev_sentence = curr_sentence
                prev_len = curr_len
            else:
                prev_sentence += curr_sentence
                prev_len += curr_len

        if prev_sentence:
            combined_sentences.append(prev_sentence)
        return combined_sentences

    def generate_vector(self,request_payload):
    # text can be a sentence or list of sentences
        text = request_payload.get("inputs")
        # print(text)
        try:
            if isinstance(text, str):
        # Process a single sentence
                if len(text.split()) > 512:
                    sentences = list(re.findall(r'[^!?。.？！]+[!?。.？！]?', text.replace('\n', ' ')))
                    # print("sentences", sentences)
                    combined_sentences = self.  get_combined_sentences(sentences)
                    sentence_embeddings = np.mean(model_st.encode(combined_sentences), axis=0)
                else:
                    sentence_embeddings = model_st.encode(text)

                vectors = sentence_embeddings.tolist()
            elif isinstance(text, list):
        # Process a list of sentences
                vectors = []
                for sentence in text:
                    if len(sentence.split()) > 512:
                        sentences = list(re.findall(r'[^!?。.？！]+[!?。.？！]?', sentence.replace('\n', ' ')))
                        combined_sentences = self.get_combined_sentences(sentences)
                        sentence_embedding = np.mean(model_st.encode(combined_sentences), axis=0)
                    else:
                        sentence_embedding = model_st.encode(sentence)

                        vectors.append(sentence_embedding.tolist())
            else:
                raise ValueError("Invalid input format. 'text' should be either a string or a list of strings.")

                # print("sentence_embeddings",sentence_embeddings)

            response=vectors
        except Exception as e:
            print(f"An exception occurred: {e}")
            vectors = [0] * 768
            response = {"vector": vectors, "model": "Sentence Transformers", "status_code": 400,
                        "msg": "Something went wrong while generating vectors"}
                        
        return response
    
        
embedding_generator = EmbeddingGenerator(model_path)

@app.route('/process_string/embed', methods=['POST']) 
def vectors():
    request_payload = request.json
    response = embedding_generator.generate_vector(request_payload)
    # return jsonify({'response': response})
    return response

if __name__ == '__main__':
    app.run(debug=True)



