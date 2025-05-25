"""
Code Generation Agent

This package provides a LangGraph-based agent for generating Python code
for paleoclimate data analysis using PyLiPD and Pyleoclim.
"""

from .agent import create_agent
from .code_generation_agent import CodeGenerationAgent
from .state import CodeAgentState, CodeAgentConfig
from .handlers import (
    extract_analysis_request_node,
    search_code_examples_node,
    generate_code_node,
    finalize_code_response_node
)

__all__ = [
    'create_agent',
    'CodeGenerationAgent',
    'CodeAgentState',
    'CodeAgentConfig',
    'extract_analysis_request_node',
    'search_code_examples_node',
    'generate_code_node',
    'finalize_code_response_node'
] 