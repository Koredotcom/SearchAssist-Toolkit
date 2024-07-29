
# src/utils/dataProcessing.py

import json
from loguru import logger


def trim_predictions_to_max_token_length(prediction, tokenizer, max_token_length=75):
    tokenized_prediction = tokenizer.encode(prediction)
    trimmed_tokenized_prediction = tokenized_prediction[1: max_token_length + 1]
    return tokenizer.decode(trimmed_tokenized_prediction)


