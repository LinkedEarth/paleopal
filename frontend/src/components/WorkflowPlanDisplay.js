import React, { useState } from 'react';

// Component to display workflow examples in a modal
const ExamplesModal = ({ isOpen, onClose, examples, type, title }) => {
    if (!isOpen) return null;
  
    const copyExample = (example) => {
      const text = type === 'workflows' 
        ? `Workflow: ${example.title || 'Unknown'}\nSteps: ${example.step_count || 'Unknown'}\nDescription: ${example.description || 'N/A'}`
        : `Method: ${example.method_name || 'Unknown'}\nPaper: ${example.paper_title || 'Unknown'}\nSummary: ${example.searchable_summary || 'N/A'}`;
      
      navigator.clipboard.writeText(text).then(() => {
        console.log('Example copied to clipboard');
      }).catch(err => {
        console.error('Failed to copy example:', err);
      });
    };
  
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
        <div className="bg-white rounded-lg max-w-4xl max-h-[80vh] w-full flex flex-col" onClick={e => e.stopPropagation()}>
          <div className="flex justify-between items-center p-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-800 m-0">{title}</h3>
            <button 
              className="w-8 h-8 flex items-center justify-center text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded text-xl"
              onClick={onClose}
            >
              ×
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4">
            {examples.length === 0 ? (
              <p className="text-gray-600">No examples found.</p>
            ) : (
              examples.map((example, index) => (
                <div key={index} className="border border-gray-200 rounded-lg p-4 mb-4 hover:bg-gray-50 transition-colors">
                  <div className="flex items-center justify-between mb-3">
                    <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm font-medium">#{index + 1}</span>
                    {type === 'workflows' ? (
                      <h4 className="flex-1 mx-3 text-gray-800 font-medium m-0">{example.title || 'Unknown Workflow'}</h4>
                    ) : (
                      <h4 className="flex-1 mx-3 text-gray-800 font-medium m-0">{example.method_name || 'Unknown Method'}</h4>
                    )}
                    <button 
                      className="px-2 py-1 bg-gray-500 text-white rounded text-sm hover:bg-gray-600 transition-colors"
                      onClick={() => copyExample(example)}
                      title="Copy example details"
                    >
                      📋
                    </button>
                  </div>
                  
                  <div className="space-y-3">
                    {type === 'workflows' ? (
                      <>
                        <div className="flex flex-wrap gap-4 text-sm">
                          <span className="text-gray-600">
                            <strong>Similarity:</strong> {(example.similarity_score || 0).toFixed(3)}
                          </span>
                          <span className="text-gray-600">
                            <strong>Steps:</strong> {example.step_count || 'Unknown'}
                          </span>
                        </div>
                        
                        {example.workflow_steps && example.workflow_steps.length > 0 && (
                          <div className="text-sm">
                            <strong className="text-gray-700">Steps:</strong>
                            <ul className="list-disc list-inside mt-1 space-y-1 text-gray-600">
                              {example.workflow_steps.map((step, stepIndex) => (
                                <li key={stepIndex}>
                                  {typeof step === 'string' ? step : step.step_description || step}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        
                        {example.description && (
                          <div className="text-sm">
                            <strong className="text-gray-700">Description:</strong> 
                            <span className="text-gray-600 ml-1">{example.description}</span>
                          </div>
                        )}
                      </>
                    ) : (
                      <>
                        <div className="flex flex-wrap gap-4 text-sm">
                          <span className="text-gray-600">
                            <strong>Similarity:</strong> {(example.similarity_score || 0).toFixed(3)}
                          </span>
                          {example.paper_title && (
                            <span className="text-gray-600">
                              <strong>From Paper:</strong> {example.paper_title}
                            </span>
                          )}
                        </div>
                        
                        {example.searchable_summary && (
                          <div className="text-sm">
                            <strong className="text-gray-700">Summary:</strong> 
                            <span className="text-gray-600 ml-1">{example.searchable_summary}</span>
                          </div>
                        )}
                        
                        {example.category && (
                          <div className="text-sm">
                            <strong className="text-gray-700">Category:</strong> 
                            <span className="text-gray-600 ml-1">{example.category}</span>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    );
};

// Component to display workflow plans
const WorkflowPlanDisplay = ({ workflowPlan, workflowId, onExecuteWorkflow }) => {
    const [showExamplesModal, setShowExamplesModal] = useState(false);
    const [modalExamples, setModalExamples] = useState([]);
    const [modalType, setModalType] = useState('');
    const [modalTitle, setModalTitle] = useState('');
  
    const copyToClipboard = (text) => {
      navigator.clipboard.writeText(text).then(() => {
        console.log('Workflow plan copied to clipboard');
      }).catch(err => {
        console.error('Failed to copy workflow plan:', err);
      });
    };
  
    const handleShowWorkflowExamples = () => {
      const examples = workflowPlan.context_used?.workflow_examples || [];
      setModalExamples(examples);
      setModalType('workflows');
      setModalTitle(`Workflow Examples (${examples.length})`);
      setShowExamplesModal(true);
    };
  
    const handleShowMethodExamples = () => {
      const examples = workflowPlan.context_used?.method_examples || [];
      setModalExamples(examples);
      setModalType('methods');
      setModalTitle(`Method Examples (${examples.length})`);
      setShowExamplesModal(true);
    };
  
    const formatWorkflowPlan = (plan) => {
      let output = `Workflow Plan (ID: ${workflowId})\n`;
      output += `===========================================\n\n`;
      
      if (plan.context_used) {
        output += `Context Used:\n`;
        output += `- Workflows found: ${plan.context_used.workflows_found}\n`;
        output += `- Methods found: ${plan.context_used.methods_found}\n\n`;
      }
      
      output += `Steps:\n`;
      plan.steps.forEach((step, index) => {
        output += `${index + 1}. [${step.agent_type.toUpperCase()}] ${step.user_input}\n`;
        if (step.dependencies && step.dependencies.length > 0) {
          output += `   Dependencies: ${step.dependencies.join(', ')}\n`;
        }
        if (step.rationale) {
          output += `   Rationale: ${step.rationale}\n`;
        }
        output += `\n`;
      });
      
      return output;
    };
    
    return (
      <div className="border border-purple-300 rounded-lg p-4 bg-purple-50">
        <div className="flex justify-between items-center mb-4">
          <h4 className="text-purple-800 font-medium m-0">📋 Workflow Plan</h4>
          <div className="flex gap-2">
            <button 
              className="px-3 py-1 bg-purple-500 text-white rounded text-sm hover:bg-purple-600 transition-colors"
              onClick={() => copyToClipboard(formatWorkflowPlan(workflowPlan))}
              title="Copy workflow plan to clipboard"
            >
              📋 Copy
            </button>
            <button 
              className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600 transition-colors"
              onClick={() => onExecuteWorkflow(workflowId)}
              title="Execute this workflow"
            >
              ▶️ Instantiate
            </button>
          </div>
        </div>
        
        <div className="space-y-4">
          {workflowPlan.context_used && (
            <div className="bg-white rounded border border-purple-200 p-3">
              <h5 className="text-sm font-medium text-purple-700 mb-3 m-0">Context Used:</h5>
              <div className="flex flex-wrap gap-2">
                <button 
                  className="px-3 py-1 bg-blue-100 text-blue-800 rounded text-sm hover:bg-blue-200 transition-colors cursor-pointer"
                  onClick={handleShowWorkflowExamples}
                  disabled={!workflowPlan.context_used.workflows_found}
                  title={workflowPlan.context_used.workflows_found ? "Click to view workflow examples" : "No workflow examples available"}
                >
                  📊 Workflows: {workflowPlan.context_used.workflows_found}
                </button>
                <button 
                  className="px-3 py-1 bg-green-100 text-green-800 rounded text-sm hover:bg-green-200 transition-colors cursor-pointer"
                  onClick={handleShowMethodExamples}
                  disabled={!workflowPlan.context_used.methods_found}
                  title={workflowPlan.context_used.methods_found ? "Click to view method examples" : "No method examples available"}
                >
                  🔬 Methods: {workflowPlan.context_used.methods_found}
                </button>
              </div>
            </div>
          )}
          
          <div className="bg-white rounded border border-purple-200 p-3">
            <h5 className="text-sm font-medium text-purple-700 mb-3 m-0">Workflow Steps:</h5>
            <div className="space-y-3">
              {workflowPlan.steps.map((step, index) => (
                <div key={index} className="border border-gray-200 rounded p-3 bg-gray-50">
                  <div className="flex items-start gap-3">
                    <span className="bg-purple-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium flex-shrink-0">
                      {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          step.agent_type === 'sparql' ? 'bg-blue-100 text-blue-800' :
                          step.agent_type === 'code' ? 'bg-green-100 text-green-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {step.agent_type.toUpperCase()}
                        </span>
                        <span className="text-xs text-gray-500">{step.step_id}</span>
                      </div>
                      <div className="text-sm text-gray-800 mb-2">{step.user_input}</div>
                      {step.dependencies && step.dependencies.length > 0 && (
                        <div className="text-xs text-gray-600">
                          <strong>Dependencies:</strong> {step.dependencies.join(', ')}
                        </div>
                      )}
                      {step.rationale && (
                        <div className="text-xs text-gray-600 mt-1">
                          <strong>Rationale:</strong> {step.rationale}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        <ExamplesModal
          isOpen={showExamplesModal}
          onClose={() => setShowExamplesModal(false)}
          examples={modalExamples}
          type={modalType}
          title={modalTitle}
        />
      </div>
    );
};

export default WorkflowPlanDisplay; 