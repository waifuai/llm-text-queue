import pytest
from unittest.mock import patch
from src import respond
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch

def test_generate_suffix_success():
    with patch('src.respond.generator') as mock_generator:
        mock_generator.return_value = [{'generated_text': 'test prompt test suffix'}]
        suffix = respond.generate_suffix('test prompt')
        assert suffix == ' test suffix'

def test_generate_suffix_runtime_error():
    with patch('src.respond.generator') as mock_generator:
        mock_generator.side_effect = RuntimeError('test error')
        suffix = respond.generate_suffix('test prompt')
        assert suffix == ''

def test_waifu_reply():
    with patch('src.respond.generate_suffix') as mock_generate_suffix:
        mock_generate_suffix.return_value = "test suffix\n"
        reply = respond.waifu_reply("test prompt")
        assert reply == "test suffix"

def test_predict_response():
    with patch('src.respond.waifu_reply') as mock_waifu_reply:
        mock_waifu_reply.return_value = "test reply"
        response = respond.predict_response("test prompt")
        assert response == "test reply"

def test_model_loading():
    tokenizer = AutoTokenizer.from_pretrained(respond.MODEL_PATH)
    model = AutoModelForCausalLM.from_pretrained(respond.MODEL_PATH)
    assert tokenizer is not None
    assert model is not None