"""
Code Generation Agent

This package provides a LangGraph-based agent for generating Python code
for paleoclimate data analysis using PyLiPD and Pyleoclim.
"""

from .agent import create_agent
from .code_generation_agent import CodeGenerationAgent
from .state import CodeAgentState, CodeAgentConfig