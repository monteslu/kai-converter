#!/usr/bin/env python3
"""
LLM provider abstraction for lyrics correction.
Supports OpenAI, local LM Studio, Anthropic Claude, and other OpenAI-compatible APIs.
"""

import os
import json
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def complete_chat(self, messages: list, model: str = None, temperature: float = 0.1) -> str:
        """Complete a chat conversation and return the response text."""
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")
        
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package required. Run: pip install openai")
    
    def complete_chat(self, messages: list, model: str = "gpt-4o", temperature: float = 0.1) -> str:
        # GPT-5 models only support default temperature of 1.0
        if model.startswith("gpt-5"):
            temperature = 1.0

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature
        )
        return response.choices[0].message.content

class LMStudioProvider(LLMProvider):
    """Local LM Studio provider (OpenAI-compatible API)."""
    
    def __init__(self, base_url: str = "http://localhost:1234", api_key: str = "lm-studio"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
    
    def complete_chat(self, messages: list, model: str = "local-model", temperature: float = 0.1) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error {response.status_code}: {response.reason}")
            print(f"Response headers: {dict(response.headers)}")
            print(f"Response body: {response.text}")
            
            try:
                error_json = response.json()
                print(f"Parsed error: {error_json}")
                if 'error' in error_json:
                    error_msg = error_json['error']
                    if isinstance(error_msg, dict):
                        raise Exception(f"LM Studio error: {error_msg.get('message', error_msg)}")
                    else:
                        raise Exception(f"LM Studio error: {error_msg}")
                else:
                    raise Exception(f"LM Studio API error: {error_json}")
            except ValueError:
                # Not valid JSON
                raise Exception(f"LM Studio API error (HTTP {response.status_code}): {response.text}")
        except Exception as e:
            if "LM Studio" in str(e):
                raise e
            else:
                raise Exception(f"LM Studio connection error: {e}")

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.")
        
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package required. Run: pip install anthropic")
    
    def complete_chat(self, messages: list, model: str = "claude-3-5-sonnet-20241022", temperature: float = 0.1) -> str:
        # Convert OpenAI format to Anthropic format
        system_message = ""
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                user_messages.append(msg)
        
        response = self.client.messages.create(
            model=model,
            system=system_message,
            messages=user_messages,
            max_tokens=4000,
            temperature=temperature
        )
        
        return response.content[0].text

class GeminiProvider(LLMProvider):
    """Google Gemini provider."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key required. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.genai = genai
        except ImportError:
            raise ImportError("google-generativeai package required. Run: pip install google-generativeai")
    
    def complete_chat(self, messages: list, model: str = "gemini-1.5-pro", temperature: float = 0.1) -> str:
        # Convert OpenAI format to Gemini format
        system_prompt = ""
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "user":
                user_messages.append(msg["content"])
            elif msg["role"] == "assistant":
                user_messages.append(f"Assistant: {msg['content']}")
        
        # Combine system prompt with user messages
        full_prompt = system_prompt + "\n\n" + "\n\n".join(user_messages)
        
        # Configure generation settings
        generation_config = self.genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=4000,
        )
        
        # Create model and generate
        gemini_model = self.genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config,
        )
        
        response = gemini_model.generate_content(full_prompt)
        return response.text

class OpenAICompatibleProvider(LLMProvider):
    """Generic OpenAI-compatible API provider (Ollama, Together, etc.)."""
    
    def __init__(self, base_url: str, api_key: str = "dummy"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
    
    def complete_chat(self, messages: list, model: str, temperature: float = 0.1) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4000
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]

def get_llm_provider(provider_type: str = None, **kwargs) -> LLMProvider:
    """Factory function to get an LLM provider."""
    
    # Auto-detect provider if not specified
    if not provider_type:
        if os.getenv("OPENAI_API_KEY"):
            provider_type = "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            provider_type = "anthropic"
        elif os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            provider_type = "gemini"
        else:
            provider_type = "lmstudio"  # Default to local
    
    provider_type = provider_type.lower()
    
    if provider_type == "openai":
        return OpenAIProvider(**kwargs)
    elif provider_type == "lmstudio":
        return LMStudioProvider(**kwargs)
    elif provider_type == "anthropic":
        return AnthropicProvider(**kwargs)
    elif provider_type == "gemini":
        return GeminiProvider(**kwargs)
    elif provider_type == "openai-compatible":
        return OpenAICompatibleProvider(**kwargs)
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")

# Valid provider types for validation
VALID_PROVIDERS = ["openai", "lmstudio", "anthropic", "gemini", "openai-compatible", "auto"]

# Default model mappings for each provider
DEFAULT_MODELS = {
    "openai": "gpt-4o",  # Fast and reliable for lyrics correction
    "lmstudio": "local-model",
    "anthropic": "claude-3-5-sonnet-20241022",
    "gemini": "gemini-2.5-flash",  # Latest fast text generation model
    "openai-compatible": "llama-3.1-8b-instruct"  # Example
}

def get_default_model(provider_type: str) -> str:
    """Get default model for a provider."""
    return DEFAULT_MODELS.get(provider_type.lower(), "gpt-4o")