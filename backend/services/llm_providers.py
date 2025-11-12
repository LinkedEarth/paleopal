#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM Providers for PaleoPal

This module provides a flexible abstraction for connecting to various
Language Learning Models (LLMs) including Ollama, OpenAI, Claude, etc.
"""

import abc
import json
import logging
import os
import sys
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

# Add the parent directory to the path to import from backend
sys.path.append(str(Path(__file__).parent.parent))
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, XAI_API_KEY

# Import providers (with conditional imports to handle missing dependencies)
try:
    import ollama
except ImportError:
    ollama = None

try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Add imports at the top (LangChain 0.2+)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.outputs import ChatGeneration
from pydantic import Field

# Configure logging
logger = logging.getLogger(__name__)


def clean_reasoning_response(response: str) -> str:
    """
    Clean response from reasoning models that include thinking tags.
    
    Args:
        response: Raw response from the model
        
    Returns:
        Cleaned response with reasoning tags removed
    """
    import re
    
    # Remove thinking tags and their content
    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
    response = re.sub(r'<thinking>.*?</thinking>', '', response, flags=re.DOTALL)
    response = re.sub(r'<thought>.*?</thought>', '', response, flags=re.DOTALL)
    
    # Clean up extra whitespace
    response = re.sub(r'\n\s*\n', '\n', response)
    response = response.strip()
    
    return response


def extract_json_from_response(response: str) -> str:
    """
    Extract JSON from a response that might contain additional text.
    
    Args:
        response: Response that might contain JSON
        
    Returns:
        Extracted JSON string, or original response if no JSON found
    """
    import re
    import json
    
    # First, clean common prefixes that reasoning models add
    response = response.strip()
    
    # Remove common prefixes like "json", "```json", "Here's the JSON:", etc.
    prefixes_to_remove = [
        r'^json\s*',
        r'^```json\s*',
        r'^```\s*',
        r'^Here\'s the JSON:\s*',
        r'^Response:\s*',
        r'^Answer:\s*',
        r'^Result:\s*',
        r'^Output:\s*'
    ]
    
    for prefix in prefixes_to_remove:
        response = re.sub(prefix, '', response, flags=re.IGNORECASE)
    
    # Remove trailing markdown blocks
    response = re.sub(r'\s*```\s*$', '', response)
    
    # First try to find JSON in code blocks
    json_pattern = re.compile(r'```(?:json)?\s*(\{.*?\})\s*```', re.DOTALL)
    match = json_pattern.search(response)
    
    if match:
        json_candidate = match.group(1)
        try:
            # Validate it's proper JSON
            json.loads(json_candidate)
            return json_candidate
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON object in the response (including nested objects)
    brace_pattern = re.compile(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', re.DOTALL)
    matches = brace_pattern.findall(response)
    
    for match in matches:
        try:
            # Validate it's proper JSON
            json.loads(match)
            return match
        except json.JSONDecodeError:
            continue
    
    # Try to find simpler patterns that might be JSON-like
    # Look for patterns like { "key": "value" }
    simple_json_pattern = re.compile(r'\{\s*"[^"]+"\s*:\s*[^}]+\}', re.DOTALL)
    matches = simple_json_pattern.findall(response)
    
    for match in matches:
        try:
            json.loads(match)
            return match
        except json.JSONDecodeError:
            continue
    
    # Enhanced line-by-line parsing to handle malformed starts
    lines = response.split('\n')
    json_lines = []
    in_json = False
    brace_count = 0
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Look for the start of JSON (could be just { or after some text)
        if '{' in line and not in_json:
            # Find the position of the first {
            brace_pos = line.find('{')
            if brace_pos >= 0:
                # Start from the { character
                line = line[brace_pos:]
                in_json = True
                json_lines = [line]
                brace_count = line.count('{') - line.count('}')
                
                # Check if this line completes the JSON
                if brace_count <= 0:
                    candidate = line
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        in_json = False
                        json_lines = []
                        brace_count = 0
                        
        elif in_json:
            json_lines.append(line)
            brace_count += line.count('{') - line.count('}')
            
            # Check if we've closed all braces
            if brace_count <= 0:
                candidate = '\n'.join(json_lines)
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    # Try just the lines that might be valid JSON
                    for i in range(len(json_lines)):
                        partial_candidate = '\n'.join(json_lines[:i+1])
                        try:
                            json.loads(partial_candidate)
                            return partial_candidate
                        except json.JSONDecodeError:
                            continue
                
                # Reset if we couldn't parse
                in_json = False
                json_lines = []
                brace_count = 0
    
    # Last resort: try to extract anything that looks like it might be JSON
    # Look for content between the first { and last }
    first_brace = response.find('{')
    last_brace = response.rfind('}')
    
    if first_brace >= 0 and last_brace > first_brace:
        candidate = response[first_brace:last_brace + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
    
    # If no JSON found, return original response
    return response


class LLMProvider(abc.ABC):
    """
    Abstract base class for LLM providers.
    All LLM provider implementations should inherit from this class.
    """
    
    @abc.abstractmethod
    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a response from the LLM based on the given messages.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
                    (e.g., [{"role": "user", "content": "Hello"}])
            
        Returns:
            str: The LLM's response
        """
        pass
    
    @abc.abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available for use.
        
        Returns:
            bool: True if the provider is available, False otherwise
        """
        pass


class OllamaProvider(LLMProvider):
    """
    Provider for Ollama LLMs (local models like Llama2, DeepSeek, etc.)
    """
    
    def __init__(self, model_name: str = "deepseek-r1"):
        """
        Initialize the Ollama provider.
        
        Args:
            model_name (str): The name of the Ollama model to use
        """
        self.model_name = model_name
        
        # Import config settings for reasoning models
        try:
            from config import (
                OLLAMA_REASONING_MODELS, 
                OLLAMA_JSON_TEMPERATURE, 
                OLLAMA_JSON_TOP_P, 
                OLLAMA_JSON_REPEAT_PENALTY
            )
            self.reasoning_models = OLLAMA_REASONING_MODELS
            self.json_temperature = OLLAMA_JSON_TEMPERATURE
            self.json_top_p = OLLAMA_JSON_TOP_P
            self.json_repeat_penalty = OLLAMA_JSON_REPEAT_PENALTY
        except ImportError:
            # Fallback values if config import fails
            self.reasoning_models = [
                "deepseek-r1", "deepseek-r1:1.5b", "deepseek-r1:7b", "deepseek-r1:14b", "deepseek-r1:32b", "deepseek-r1:70b",
                "qwen2.5-coder:32b-instruct", "marco-o1", "thinking-model"
            ]
            self.json_temperature = 0.1
            self.json_top_p = 0.9
            self.json_repeat_penalty = 1.1
        
        self.is_reasoning_model = any(reasoning_model in model_name.lower() for reasoning_model in self.reasoning_models)
    
    def is_available(self) -> bool:
        """
        Check if Ollama is available.
        
        Returns:
            bool: True if Ollama is available, False otherwise
        """
        if ollama is None:
            logger.warning("Ollama package is not installed. Install with: pip install ollama")
            return False
        
        try:
            # Try to list models to check if Ollama is running
            _ = ollama.list()
            return True
        except Exception as e:
            logger.warning(f"Ollama is not available: {str(e)}")
            return False
    
    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a response using Ollama.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            
        Returns:
            str: The response from Ollama
        """
        if not self.is_available():
            raise RuntimeError("Ollama is not available")
        
        try:
            # For reasoning models, add specific instructions to ensure clean JSON output
            if self.is_reasoning_model:
                # Add instruction to the last message for JSON-only output
                enhanced_messages = messages.copy()
                if enhanced_messages and enhanced_messages[-1]["role"] == "user":
                    original_content = enhanced_messages[-1]["content"]
                    enhanced_messages[-1]["content"] = f"""{original_content}

IMPORTANT: Respond with ONLY the requested JSON object. Do not include any explanations, reasoning, or additional text outside the JSON. Do not use thinking tags or any other markup. Do not prefix with "json" or any other text."""
                
                # logger.info(f"Ollama: Sending messages: {enhanced_messages}")

                response = ollama.chat(
                    model=self.model_name,
                    messages=enhanced_messages,
                    options={
                        "temperature": self.json_temperature,
                        "top_p": self.json_top_p,
                        "repeat_penalty": self.json_repeat_penalty
                    }
                )
            else:
                response = ollama.chat(
                    model=self.model_name,
                    messages=messages
                )
            
            content = response['message']['content']
            
            # Clean reasoning tags if this is a reasoning model
            if self.is_reasoning_model:
                # Apply both cleaning functions for reasoning models
                content = clean_reasoning_response(content)
                
                # Always try to extract JSON for reasoning models since they often add extra text
                content = extract_json_from_response(content)
                
                # Additional cleaning for common reasoning model artifacts
                content = content.strip()
                
                # Log the cleaning process for debugging
                logger.debug(f"Original response length: {len(response['message']['content'])}")
                logger.debug(f"Cleaned response length: {len(content)}")
                logger.debug(f"Cleaned response preview: {content[:100]}...")
            
            return content
            
        except Exception as e:
            logger.error(f"Error calling Ollama: {str(e)}")
            raise


class OpenAIProvider(LLMProvider):
    """
    Provider for OpenAI's models (GPT-3.5, GPT-4, etc.)
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize the OpenAI provider.
        
        Args:
            model_name (str): The name of the OpenAI model to use
            api_key (str, optional): The OpenAI API key. If None, will use OPENAI_API_KEY env var.
        """
        self.model_name = model_name
        self.api_key = api_key or OPENAI_API_KEY
    
    
    def is_available(self) -> bool:
        """
        Check if OpenAI is available.
        
        Returns:
            bool: True if OpenAI is available, False otherwise
        """
        if openai is None:
            logger.warning("OpenAI package is not installed. Install with: pip install openai")
            return False
        
        if not self.api_key:
            logger.warning("OpenAI API key is not set")
            return False
        
        return True
    
    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a response using OpenAI.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            
        Returns:
            str: The response from OpenAI
        """
        if not self.is_available():
            raise RuntimeError("OpenAI is not available")
        
        client = openai.OpenAI(api_key=self.api_key)
        
        try:
            # logger.info(f"OpenAI: Sending messages: {messages}")
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling OpenAI: {str(e)}")
            raise


class ClaudeProvider(LLMProvider):
    """
    Provider for Anthropic's Claude models
    """
    
    def __init__(
        self,
        model_name: str = "claude-3-7-sonnet-20250219",
        api_key: Optional[str] = None
    ):
        """
        Initialize the Claude provider.
        
        Args:
            model_name (str): The name of the Claude model to use
            api_key (str, optional): The Anthropic API key. If None, will use ANTHROPIC_API_KEY env var.
        """
        self.model_name = model_name
        self.api_key = api_key or ANTHROPIC_API_KEY
    
    def is_available(self) -> bool:
        """
        Check if Claude is available.
        
        Returns:
            bool: True if Claude is available, False otherwise
        """
        if anthropic is None:
            logger.warning("Anthropic package is not installed. Install with: pip install anthropic")
            return False
        
        if not self.api_key:
            logger.warning("Anthropic API key is not set")
            return False
        
        return True
    
    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a response using Claude.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            
        Returns:
            str: The response from Claude
        """
        if not self.is_available():
            raise RuntimeError("Claude is not available")
        
        client = anthropic.Anthropic(api_key=self.api_key)
        
        try:
            # Separate system messages from other messages
            system_messages = []
            user_assistant_messages = []
            
            for message in messages:
                if message.get("role") == "system":
                    system_messages.append(message["content"])
                else:
                    user_assistant_messages.append(message)
            
            # Combine system messages into a single system prompt
            system_prompt = "\n\n".join(system_messages) if system_messages else None
            
            # Create the API call parameters
            api_params = {
                "model": self.model_name,
                "max_tokens": 20000,
                "messages": user_assistant_messages
            }
            
            # Add system parameter if we have system messages
            if system_prompt:
                api_params["system"] = system_prompt
            
            # logger.info(f"Claude API params: {api_params}")
            response = client.messages.create(**api_params)
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error calling Claude: {str(e)}")
            raise


class GoogleGeminiProvider(LLMProvider):
    """
    Provider for Google's Gemini models
    """
    
    def __init__(
        self,
        model_name: str = "gemini-2.5-pro",
        api_key: Optional[str] = None
    ):
        """
        Initialize the Google Gemini provider.
        
        Args:
            model_name (str): The name of the Gemini model to use
            api_key (str, optional): The Google API key. If None, will use GOOGLE_API_KEY env var.
        """
        self.model_name = model_name
        self.api_key = api_key or GOOGLE_API_KEY
    
    def is_available(self) -> bool:
        """
        Check if Google Gemini is available.
        
        Returns:
            bool: True if Google Gemini is available, False otherwise
        """
        if genai is None:
            logger.warning("Google Generative AI package is not installed. Install with: pip install google-generativeai")
            return False
        
        if not self.api_key:
            logger.warning("Google API key is not set")
            return False
        
        return True
    
    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a response using Google Gemini.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            
        Returns:
            str: The response from Gemini
        """
        if not self.is_available():
            raise RuntimeError("Google Gemini is not available")
        
        # Configure the API
        genai.configure(api_key=self.api_key)
        
        try:
            # Set up the model
            model = genai.GenerativeModel(
                model_name=self.model_name
            )
            
            # Convert messages to Gemini format
            chat = model.start_chat()
            for msg in messages:
                if msg["role"] == "user":
                    # logger.info(f"Google Gemini: Sending user message: {msg['content']}")
                    chat.send_message(msg["content"])
                elif msg["role"] == "system":
                    # Store system messages for context
                    # logger.info(f"Google Gemini: Sending system message: {msg['content']}")
                    chat.history.append({"role": "model", "parts": [msg["content"]]})
            
            # Get the last response
            response = chat.last.text
            return response
        except Exception as e:
            logger.error(f"Error calling Google Gemini: {str(e)}")
            raise


class GrokProvider(LLMProvider):
    """
    Provider for xAI's Grok models
    """
    
    def __init__(
        self,
        model_name: str = "grok-3-mini-beta",
        api_key: Optional[str] = None
    ):
        """
        Initialize the Grok provider.
        
        Args:
            model_name (str): The name of the Grok model to use
            api_key (str, optional): The Grok API key. If None, will use GROK_API_KEY env var.
        """
        self.model_name = model_name
        self.api_key = api_key or XAI_API_KEY
    
    def is_available(self) -> bool:
        """
        Check if Grok is available.
        
        Returns:
            bool: True if Grok is available, False otherwise
        """
        
        if not self.api_key:
            logger.warning("Grok API key is not set")
            return False
        
        return True
    
    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a response using Grok.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            
        Returns:
            str: The response from Grok
        """
        if not self.is_available():
            raise RuntimeError("Grok is not available")
        
        try:
            client = openai.OpenAI(base_url="https://api.x.ai/v1", api_key=self.api_key)
            
            # logger.info(f"Grok: Sending messages: {messages}")

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling Grok: {str(e)}")
            raise


class LLMProviderFactory:
    """
    Factory for creating LLM providers.
    """
    
    @staticmethod
    def create_provider(
        provider_type: str,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> LLMProvider:
        """
        Create an LLM provider of the specified type.
        
        Args:
            provider_type (str): The type of provider to create 
                                ('ollama', 'openai', 'anthropic', 'google', 'grok')
            model_name (str, optional): The name of the model to use
            api_key (str, optional): The API key for the provider
            
        Returns:
            LLMProvider: An instance of the specified LLM provider
            
        Raises:
            ValueError: If the provider type is not recognized
        """
        provider_type = provider_type.lower()
        
        if provider_type == "ollama":
            default_model = "deepseek-r1"
            return OllamaProvider(
                model_name=model_name or default_model
            )
        
        elif provider_type == "openai":
            default_model = "gpt-5"
            return OpenAIProvider(
                model_name=model_name or default_model,
                api_key=api_key
            )
        
        elif provider_type in ["anthropic", "claude"]:
            default_model = "claude-sonnet-4-5-20250929"
            return ClaudeProvider(
                model_name=model_name or default_model,
                api_key=api_key
            )
        
        elif provider_type in ["google", "gemini"]:
            default_model = "gemini-2.5-pro"
            return GoogleGeminiProvider(
                model_name=model_name or default_model,
                api_key=api_key
            )
        
        elif provider_type == "grok":
            default_model = "grok-4"
            return GrokProvider(
                model_name=model_name or default_model,
                api_key=api_key
            )
        
        else:
            raise ValueError(f"Unknown LLM provider type: {provider_type}")
    
    @staticmethod
    def get_available_provider(
        preferred_providers: List[str] = ["ollama", "openai", "claude", "google", "grok"],
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Optional[LLMProvider]:
        """
        Get the first available LLM provider from the preferred list.
        
        Args:
            preferred_providers (List[str]): List of provider types in order of preference
            model_name (str, optional): The name of the model to use
            api_key (str, optional): The API key for the provider
            
        Returns:
            LLMProvider or None: An instance of the first available LLM provider, or None if none are available
        """
        for provider_type in preferred_providers:
            try:
                provider = LLMProviderFactory.create_provider(
                    provider_type=provider_type,
                    model_name=model_name,
                    api_key=api_key
                )
                if provider.is_available():
                    logger.info(f"Using LLM provider: {provider_type}")
                    return provider
            except Exception as e:
                logger.warning(f"Error creating provider {provider_type}: {str(e)}")
        
        logger.error("No available LLM providers found")
        return None 

    @staticmethod
    def get_langchain_model(
        provider_type: str = "openai",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Optional[BaseChatModel]:
        """
        Get a LangChain model using the specified provider.
        
        Args:
            provider_type: Type of provider to use
            model_name: Name of the model to use
            api_key: Optional API key for the provider
            
        Returns:
            BaseChatModel or None: A LangChain model if available, None otherwise
            
        Raises:
            RuntimeError: If no available LLM providers are found
        """
        if BaseChatModel is None:
            raise RuntimeError("LangChain is not installed. Install with: pip install langchain")
        
        try:
            # Try to get the requested provider
            provider = LLMProviderFactory.create_provider(provider_type, model_name, api_key)
            if provider.is_available():
                return LangChainWrapper(provider)
            
            # If requested provider is not available, try fallbacks
            fallback_providers = [
                ("openai", "gpt-4o"),
                ("openai", "gpt-3.5-turbo"),
                ("claude", "claude-3-7-sonnet-20250219"),
                ("claude", "claude-3-opus-20240229"),
                ("ollama", "deepseek-r1"),
                ("ollama", "llama3")
            ]
            
            for p_type, p_model in fallback_providers:
                if p_type == provider_type and p_model == model_name:
                    continue  # Skip the one we already tried
                    
                provider = LLMProviderFactory.create_provider(p_type, p_model, api_key)
                if provider.is_available():
                    logger.info(f"Using fallback provider: {p_type} with model {p_model}")
                    return LangChainWrapper(provider)
            
            raise RuntimeError("No available LLM providers found")
            
        except Exception as e:
            logger.error(f"Error initializing LLM provider: {e}")
            raise RuntimeError(f"Failed to initialize LLM provider: {e}")


class LangChainWrapper(BaseChatModel):
    """Wrapper class to make our LLM providers compatible with LangChain."""
    
    provider: LLMProvider = Field(description="The LLM provider to use")
    
    def __init__(self, provider: LLMProvider):
        """Initialize the wrapper with a provider."""
        super().__init__(provider=provider)
    
    @property
    def _llm_type(self) -> str:
        """Return the type of LLM."""
        return f"custom_{self.provider.__class__.__name__.lower()}"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatGeneration:
        """Generate a response from the LLM.
        
        Args:
            messages: List of messages to generate a response for
            stop: Optional list of stop sequences
            run_manager: Optional callback manager
            **kwargs: Additional arguments
            
        Returns:
            ChatGeneration: The generated response
        """
        # Convert LangChain messages to our format
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                formatted_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted_messages.append({"role": "assistant", "content": msg.content})
        
        # Generate response
        response_text = self.provider.generate_response(formatted_messages)
        
        # Create and return the generation
        return ChatGeneration(
            message=AIMessage(content=response_text),
            generation_info={"provider": self._llm_type}
        )
    
    def _call(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Convert LangChain messages to our format and call the provider."""
        if isinstance(messages, str):
            messages = [{"type": "human", "content": messages}]
            
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                if msg["type"] == "human":
                    formatted_messages.append({"role": "user", "content": msg["content"]})
                elif msg["type"] == "system":
                    formatted_messages.append({"role": "system", "content": msg["content"]})
                elif msg["type"] == "ai":
                    formatted_messages.append({"role": "assistant", "content": msg["content"]})
            elif hasattr(msg, "type") and hasattr(msg, "content"):
                if msg.type == "human":
                    formatted_messages.append({"role": "user", "content": msg.content})
                elif msg.type == "system":
                    formatted_messages.append({"role": "system", "content": msg.content})
                elif msg.type == "ai":
                    formatted_messages.append({"role": "assistant", "content": msg.content})
        
        # logger.info(f"Formatted messages: {formatted_messages}")
        response = self.provider.generate_response(formatted_messages)
        
        # Additional post-processing for reasoning models that might return JSON when we want plain text
        if hasattr(self.provider, 'is_reasoning_model') and self.provider.is_reasoning_model:
            # Check if the response looks like JSON but we expected plain text
            if response.strip().startswith('{') or response.strip().startswith('json'):
                # Check the context - if asking for SPARQL query, extract from JSON
                context_suggests_sparql = any(
                    keyword in str(messages).lower() 
                    for keyword in ['sparql', 'query', 'select', 'prefix', 'where']
                )
                
                if context_suggests_sparql:
                    logger.debug("Reasoning model returned JSON for SPARQL request, extracting content")
                    try:
                        import json
                        # Try to parse as JSON and extract relevant fields
                        cleaned = clean_reasoning_response(response)
                        json_extracted = extract_json_from_response(cleaned)
                        
                        if json_extracted.strip().startswith('{'):
                            parsed = json.loads(json_extracted)
                            if isinstance(parsed, dict):
                                # Look for common fields that might contain the actual content
                                for field in ['query', 'sparql', 'response', 'answer', 'result']:
                                    if field in parsed and isinstance(parsed[field], str):
                                        extracted_content = parsed[field].strip()
                                        if extracted_content:
                                            logger.debug(f"Extracted {field} from JSON response")
                                            response = extracted_content
                                            break
                    except json.JSONDecodeError:
                        logger.debug("Could not parse as JSON, using original response")
                        pass
            
            # Additional cleanup for reasoning models
            response = self._clean_reasoning_response(response)
        
        return response
    
    def _clean_reasoning_response(self, response: str) -> str:
        """Clean up responses from reasoning models."""
        # Remove markdown code blocks
        if response.startswith("```sparql"):
            response = response.replace("```sparql", "").replace("```", "").strip()
        elif response.startswith("```"):
            response = response.replace("```", "").strip()
        
        # Remove common prefixes that reasoning models might add
        prefixes_to_remove = ["sparql:", "query:", "result:", "answer:", "response:"]
        for prefix in prefixes_to_remove:
            if response.lower().startswith(prefix):
                response = response[len(prefix):].strip()
        
        return response 