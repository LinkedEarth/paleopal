import React from 'react';

/**
 * Better outline icons using Heroicons for each agent type.
 */
const ICONS = {
  sparql: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      {/* Database icon from Heroicons */}
      <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
      <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"></path>
      <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"></path>
    </svg>
  ),
  code: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      {/* Code bracket icon from Heroicons */}
      <path d="m7 8-4 4 4 4"></path>
      <path d="m17 8 4 4-4 4"></path>
      <path d="m14 4-4 16"></path>
    </svg>
  ),
  workflow_generation: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
      {/* Workflow/diagram icon from Heroicons */}
      <rect width="8" height="8" x="3" y="3" rx="2"></rect>
      <path d="M7 11v4a2 2 0 0 0 2 2h4"></path>
      <rect width="8" height="8" x="13" y="13" rx="2"></rect>
    </svg>
  ),
};

/**
 * Returns a better outline icon for a given agent type.
 * @param {string} agentType - The agent id (sparql, code, workflow_generation)
 * @param {string} className - Additional class names for sizing/color
 */
const AgentIcon = ({ agentType = 'sparql', className = 'w-4 h-4' }) => {
  const icon = ICONS[agentType] || ICONS['sparql'];
  return <span className={className}>{icon}</span>;
};

export default AgentIcon; 