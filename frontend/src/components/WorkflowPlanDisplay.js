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
      <div className="examples-modal-overlay" onClick={onClose}>
        <div className="examples-modal-content" onClick={e => e.stopPropagation()}>
          <div className="examples-modal-header">
            <h3>{title}</h3>
            <button className="examples-modal-close" onClick={onClose}>×</button>
          </div>
          
          <div className="examples-modal-body">
            {examples.length === 0 ? (
              <p>No examples found.</p>
            ) : (
              examples.map((example, index) => (
                <div key={index} className="example-item">
                  <div className="example-header">
                    <span className="example-number">#{index + 1}</span>
                    {type === 'workflows' ? (
                      <h4 className="example-title">{example.title || 'Unknown Workflow'}</h4>
                    ) : (
                      <h4 className="example-title">{example.method_name || 'Unknown Method'}</h4>
                    )}
                    <button 
                      className="example-copy-button"
                      onClick={() => copyExample(example)}
                      title="Copy example details"
                    >
                      📋
                    </button>
                  </div>
                  
                  <div className="example-content">
                    {type === 'workflows' ? (
                      <>
                        <div className="example-meta">
                          <span className="meta-item">
                            <strong>Similarity:</strong> {(example.similarity_score || 0).toFixed(3)}
                          </span>
                          <span className="meta-item">
                            <strong>Steps:</strong> {example.step_count || 'Unknown'}
                          </span>
                        </div>
                        
                        {example.workflow_steps && example.workflow_steps.length > 0 && (
                          <div className="workflow-steps">
                            <strong>Steps:</strong>
                            <ul>
                              {example.workflow_steps.map((step, stepIndex) => (
                                <li key={stepIndex}>
                                  {typeof step === 'string' ? step : step.step_description || step}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        
                        {example.description && (
                          <div className="example-description">
                            <strong>Description:</strong> {example.description}
                          </div>
                        )}
                      </>
                    ) : (
                      <>
                        <div className="example-meta">
                          <span className="meta-item">
                            <strong>Similarity:</strong> {(example.similarity_score || 0).toFixed(3)}
                          </span>
                          {example.paper_title && (
                            <span className="meta-item">
                              <strong>From Paper:</strong> {example.paper_title}
                            </span>
                          )}
                        </div>
                        
                        {example.searchable_summary && (
                          <div className="example-description">
                            <strong>Summary:</strong> {example.searchable_summary}
                          </div>
                        )}
                        
                        {example.category && (
                          <div className="example-category">
                            <strong>Category:</strong> {example.category}
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
      <div className="workflow-plan-display">
        <div className="workflow-header">
          <h4>Workflow Plan</h4>
          <div className="workflow-actions">
            <button 
              className="copy-workflow-button"
              onClick={() => copyToClipboard(formatWorkflowPlan(workflowPlan))}
              title="Copy workflow plan to clipboard"
            >
              📋 Copy
            </button>
            <button 
              className="execute-workflow-button"
              onClick={() => onExecuteWorkflow(workflowId)}
              title="Execute this workflow"
            >
              ▶️ Instantiate
            </button>
          </div>
        </div>
        
        <div className="workflow-content">
          {workflowPlan.context_used && (
            <div className="workflow-context">
              <h5>Context Used:</h5>
              <div className="context-stats">
                <button 
                  className="context-stat clickable"
                  onClick={handleShowWorkflowExamples}
                  title="Click to view workflow examples"
                  disabled={!workflowPlan.context_used.workflow_examples || workflowPlan.context_used.workflow_examples.length === 0}
                >
                  📊 {workflowPlan.context_used.workflows_found} workflow examples
                </button>
                <button 
                  className="context-stat clickable"
                  onClick={handleShowMethodExamples}
                  title="Click to view method examples"
                  disabled={!workflowPlan.context_used.method_examples || workflowPlan.context_used.method_examples.length === 0}
                >
                  📄 {workflowPlan.context_used.methods_found} method examples
                </button>
              </div>
            </div>
          )}
          
          <div className="workflow-steps">
            <h5>Planned Steps:</h5>
            {workflowPlan.steps.map((step, index) => (
              <div key={step.step_id || index} className="workflow-step">
                <div className="step-header">
                  <span className="step-number">{index + 1}</span>
                  <span className={`step-agent-type ${step.agent_type}`}>
                    {step.agent_type === 'sparql' ? '🔍 SPARQL' : '🐍 CODE'}
                  </span>
                  <span className="step-id">{step.step_id}</span>
                </div>
                <div className="step-content">
                  <div className="step-description">{step.user_input}</div>
                  {step.dependencies && step.dependencies.length > 0 && (
                    <div className="step-dependencies">
                      <strong>Dependencies:</strong> {step.dependencies.join(', ')}
                    </div>
                  )}
                  {step.rationale && (
                    <div className="step-rationale">
                      <strong>Rationale:</strong> {step.rationale}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
  
        {/* Examples Modal */}
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