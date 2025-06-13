"""
Notebook Export Service

Converts conversations to Jupyter notebook format (.ipynb) with proper cell structure,
metadata, and execution results.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from services.conversation_service import conversation_service
from services.message_service import message_service

logger = logging.getLogger(__name__)

class NotebookExportService:
    """Service for exporting conversations as Jupyter notebooks."""
    
    def __init__(self):
        self.notebook_version = "4.5"
        self.kernel_spec = {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        }
    
    def export_conversation_to_notebook(self, conversation_id: str) -> Dict[str, Any]:
        """
        Export a conversation to Jupyter notebook format.
        
        Args:
            conversation_id: ID of the conversation to export
            
        Returns:
            Dict containing the notebook JSON structure
        """
        try:
            # Get conversation with messages
            conversation = conversation_service.get_conversation(conversation_id, include_messages=True)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
            
            # Create notebook structure
            notebook = {
                "cells": [],
                "metadata": {
                    "kernelspec": self.kernel_spec,
                    "language_info": {
                        "name": "python",
                        "version": "3.8.0",
                        "mimetype": "text/x-python",
                        "codemirror_mode": {
                            "name": "ipython",
                            "version": 3
                        },
                        "pygments_lexer": "ipython3",
                        "nbconvert_exporter": "python",
                        "file_extension": ".py"
                    },
                    "paleopal": {
                        "conversation_id": conversation_id,
                        "conversation_title": conversation.title,
                        "exported_at": datetime.utcnow().isoformat(),
                        "agent_types": list(set([msg.agent_type for msg in conversation.messages if msg.agent_type])),
                        "total_messages": len(conversation.messages)
                    }
                },
                "nbformat": 4,
                "nbformat_minor": 5
            }
            
            # Add title cell
            title_cell = self._create_markdown_cell(
                f"# {conversation.title}\n\n"
                f"**Exported from PaleoPal on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}**\n\n"
                f"This notebook contains the conversation history and generated code from your PaleoPal session.\n"
                f"- Conversation ID: `{conversation_id}`\n"
                f"- Total Messages: {len(conversation.messages)}\n"
                f"- Agent Types: {', '.join(set([msg.agent_type for msg in conversation.messages if msg.agent_type]))}\n"
            )
            notebook["cells"].append(title_cell)
            
            # Process messages and convert to cells
            for i, message in enumerate(conversation.messages):
                cells = self._convert_message_to_cells(message, i)
                notebook["cells"].extend(cells)
            
            # Add footer cell
            footer_cell = self._create_markdown_cell(
                "---\n\n"
                "**End of PaleoPal Conversation Export**\n\n"
                "This notebook was automatically generated from your PaleoPal conversation. "
                "You can run the code cells to reproduce the analysis or modify them as needed.\n\n"
                "For more information about PaleoPal, visit: [PaleoPal Documentation](https://github.com/your-repo/paleopal)"
            )
            notebook["cells"].append(footer_cell)
            
            logger.info(f"Successfully exported conversation {conversation_id} to notebook with {len(notebook['cells'])} cells")
            return notebook
            
        except Exception as e:
            logger.error(f"Error exporting conversation {conversation_id} to notebook: {e}")
            raise
    
    def _convert_message_to_cells(self, message, message_index: int) -> List[Dict[str, Any]]:
        """Convert a single message to one or more notebook cells."""
        cells = []
        
        # Skip progress messages
        if message.is_node_progress:
            return cells
        
        if message.role == "user":
            # User message as markdown
            cell = self._create_markdown_cell(
                f"## User Request {message_index + 1}\n\n{message.content}"
            )
            cells.append(cell)
            
        elif message.role == "assistant":
            # Agent response - simplified, no headers
            agent_type = message.agent_type or "assistant"
            
            # Determine generated content (code/SPARQL/workflow)
            generated_content = message.generated_code or None

            # Add generated code/content if available
            if generated_content:
                if agent_type == "code" or agent_type == "sparql":
                    # Python code - just the code, no headers
                    code_cell = self._create_code_cell(
                        generated_content,
                        message_id=message.id,
                        agent_type=agent_type
                    )
                    # Add execution results if available
                    if message.execution_results:
                        outputs = self._convert_execution_results_to_outputs(message.execution_results)
                        if outputs:
                            code_cell["outputs"] = outputs
                            code_cell["execution_count"] = message_index + 1
                    
                    cells.append(code_cell)
                    
                elif agent_type == "workflow":
                    # Workflow plan as markdown
                    try:
                        workflow_json = json.loads(generated_content) if isinstance(generated_content, str) else generated_content
                        formatted_workflow = json.dumps(workflow_json, indent=2)
                        workflow_content = f"```json\n{formatted_workflow}\n```"
                    except:
                        workflow_content = f"```\n{str(generated_content)}\n```"
                    
                    workflow_cell = self._create_markdown_cell(workflow_content)
                    cells.append(workflow_cell)
        
        return cells
    
    def _create_markdown_cell(self, content: str) -> Dict[str, Any]:
        """Create a markdown cell."""
        return {
            "cell_type": "markdown",
            "metadata": {},
            "source": [content]
        }
    
    def _create_code_cell(self, code: str, message_id: str = None, agent_type: str = None) -> Dict[str, Any]:
        """Create a code cell."""
        cell = {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [code]
        }
        
        if message_id or agent_type:
            cell["metadata"]["paleopal"] = {}
            if message_id:
                cell["metadata"]["paleopal"]["message_id"] = message_id
            if agent_type:
                cell["metadata"]["paleopal"]["agent_type"] = agent_type
        
        return cell
    
    
    def _convert_execution_results_to_outputs(self, execution_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert execution results to Jupyter notebook output format."""
        outputs = []
        
        for result in execution_results:
            if not isinstance(result, dict):
                continue
                
            result_type = result.get("type")
            
            if result_type == "execution_success":
                # Add stdout output if available
                if result.get("output"):
                    output = {
                        "output_type": "stream",
                        "name": "stdout",
                        "text": [result["output"]]
                    }
                    outputs.append(output)
                
                # Add execution result as display data
                if result.get("variable_summary"):
                    var_summary = result["variable_summary"]
                    summary_text = "Variables created:\n"
                    for var_name, var_info in var_summary.items():
                        summary_text += f"- {var_name} ({var_info.get('type', 'unknown')}): {var_info.get('value', 'N/A')}\n"
                    
                    output = {
                        "output_type": "display_data",
                        "data": {
                            "text/plain": [summary_text]
                        },
                        "metadata": {}
                    }
                    outputs.append(output)
                    
            elif result_type == "execution_error":
                # Add error output
                error_output = {
                    "output_type": "error",
                    "ename": "ExecutionError",
                    "evalue": result.get("error", "Unknown error"),
                    "traceback": [result.get("error", "Unknown error")]
                }
                outputs.append(error_output)
        
        return outputs
    

    
    def get_notebook_filename(self, conversation_id: str) -> str:
        """Generate a filename for the exported notebook."""
        try:
            conversation = conversation_service.get_conversation(conversation_id, include_messages=False)
            if conversation:
                # Clean title for filename
                clean_title = "".join(c for c in conversation.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                clean_title = clean_title.replace(' ', '_')
                if len(clean_title) > 50:
                    clean_title = clean_title[:50]
                
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                return f"paleopal_{clean_title}_{timestamp}.ipynb"
            else:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                return f"paleopal_conversation_{conversation_id}_{timestamp}.ipynb"
        except:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            return f"paleopal_export_{timestamp}.ipynb"

# Global service instance
notebook_export_service = NotebookExportService() 