/**
 * PaleoPal Professional Theme System
 * A clean, modern, and professional color palette for corporate environments
 */

// Component-specific theme classes
export const THEME = {
  // Chat messages - Clean and professional with subtle shadows
  messages: {
    user: {
      bg: 'bg-blue-50 dark:bg-blue-950/20',
      border: 'border border-blue-200/60 dark:border-blue-800/40',
      text: 'text-gray-900 dark:text-gray-100',
      accent: 'border-l-4 border-blue-500 dark:border-blue-400',
      shadow: 'shadow-sm'
    },
    assistant: {
      bg: 'bg-white dark:bg-gray-800/60',
      border: 'border border-gray-200/60 dark:border-gray-700/40',
      text: 'text-gray-900 dark:text-gray-100',
      shadow: 'shadow-sm'
    }
  },

  // Agent badges - Professional with refined colors
  agentBadges: {
    sparql: `bg-teal-50 dark:bg-teal-950/30 border border-teal-200/60 dark:border-teal-800/40 text-teal-700 dark:text-teal-300 shadow-sm`,
    code: `bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200/60 dark:border-indigo-800/40 text-indigo-700 dark:text-indigo-300 shadow-sm`,
    workflow_generation: `bg-orange-50 dark:bg-orange-950/30 border border-orange-200/60 dark:border-orange-800/40 text-orange-700 dark:text-orange-300 shadow-sm`
  },

  // Agent accent borders - Subtle but distinctive
  agentAccents: {
    sparql: 'border-l-4 border-l-teal-500 dark:border-l-teal-400',
    code: 'border-l-4 border-l-indigo-500 dark:border-l-indigo-400', 
    workflow_generation: 'border-l-4 border-l-orange-500 dark:border-l-orange-400'
  },

  // Buttons - Professional and accessible
  buttons: {
    primary: 'bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-500 text-white border border-blue-600 dark:border-blue-600 shadow-sm hover:shadow-md transition-all duration-200',
    secondary: 'bg-white hover:bg-gray-50 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 shadow-sm hover:shadow-md transition-all duration-200',
    success: 'bg-emerald-600 hover:bg-emerald-700 dark:bg-emerald-600 dark:hover:bg-emerald-500 text-white border border-emerald-600 dark:border-emerald-600 shadow-sm hover:shadow-md transition-all duration-200',
    danger: 'bg-red-600 hover:bg-red-700 dark:bg-red-600 dark:hover:bg-red-500 text-white border border-red-600 dark:border-red-600 shadow-sm hover:shadow-md transition-all duration-200',
    ghost: 'bg-transparent hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 transition-all duration-200'
  },

  // Form elements - Clean and modern
  forms: {
    input: 'bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:focus:border-blue-400 dark:focus:ring-blue-400/20 shadow-sm transition-all duration-200',
    select: 'bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:focus:border-blue-400 dark:focus:ring-blue-400/20 shadow-sm transition-all duration-200',
    textarea: 'bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:focus:border-blue-400 dark:focus:ring-blue-400/20 shadow-sm transition-all duration-200'
  },

  // Containers - Professional layout with subtle depth
  containers: {
    main: 'bg-gray-50 dark:bg-gray-900',
    background: 'bg-gray-50 dark:bg-gray-900',
    panel: 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm',
    card: 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm',
    secondary: 'bg-gray-50 dark:bg-gray-700/50',
    header: 'bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm',
    footer: 'bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 shadow-sm',
    code: 'bg-gray-50 dark:bg-gray-900/60 border border-gray-200/60 dark:border-gray-700/40',
    syntax: 'bg-transparent'
  },

  // Text - Professional typography hierarchy
  text: {
    primary: 'text-gray-900 dark:text-gray-100',
    secondary: 'text-gray-700 dark:text-gray-300', 
    tertiary: 'text-gray-600 dark:text-gray-400',
    muted: 'text-gray-500 dark:text-gray-500',
    inverse: 'text-white dark:text-gray-900'
  },

  // Interactive elements - Smooth and professional
  interactive: {
    hover: 'hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors duration-200'
  },

  // Borders - Clean and subtle
  borders: {
    default: 'border-gray-200 dark:border-gray-700',
    light: 'border-gray-100 dark:border-gray-800',
    subtle: 'border-gray-200/60 dark:border-gray-700/40',
    table: 'border-gray-200/80 dark:border-gray-700/60'
  },

  // Status indicators - Professional and clear
  status: {
    success: {
      text: 'text-emerald-700 dark:text-emerald-300',
      background: 'bg-emerald-50 dark:bg-emerald-950/30',
      border: 'border-emerald-200/60 dark:border-emerald-800/40'
    },
    error: {
      text: 'text-red-700 dark:text-red-300',
      background: 'bg-red-50 dark:bg-red-950/30',
      border: 'border-red-200/60 dark:border-red-800/40'
    },
    warning: {
      text: 'text-amber-700 dark:text-amber-300',
      background: 'bg-amber-50 dark:bg-amber-950/30',
      border: 'border-amber-200/60 dark:border-amber-800/40'
    },
    info: {
      text: 'text-blue-700 dark:text-blue-300',
      background: 'bg-blue-50 dark:bg-blue-950/30',
      border: 'border-blue-200/60 dark:border-blue-800/40'
    }
  },

  // Agent-specific themes - Professional and distinctive
  agents: {
    sparql: {
      text: 'text-teal-700 dark:text-teal-300',
      background: 'bg-teal-50 dark:bg-teal-950/30',
      border: 'border-teal-200/60 dark:border-teal-800/40',
      icon: 'text-teal-600 dark:text-teal-400'
    },
    code: {
      text: 'text-indigo-700 dark:text-indigo-300',
      background: 'bg-indigo-50 dark:bg-indigo-950/30',
      border: 'border-indigo-200/60 dark:border-indigo-800/40',
      icon: 'text-indigo-600 dark:text-indigo-400'
    },
    workflow: {
      text: 'text-orange-700 dark:text-orange-300',
      background: 'bg-orange-50 dark:bg-orange-950/30',
      border: 'border-orange-200/60 dark:border-orange-800/40',
      icon: 'text-orange-600 dark:text-orange-400'
    }
  }
};

// Agent-specific form focus states - Professional blue-based focus
export const AGENT_FORM_FOCUS = {
  sparql: 'focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 dark:focus:border-teal-400 dark:focus:ring-teal-400/20',
  code: 'focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:focus:border-indigo-400 dark:focus:ring-indigo-400/20',
  workflow_generation: 'focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20 dark:focus:border-orange-400 dark:focus:ring-orange-400/20'
};

// Utility function to get agent theme
export const getAgentTheme = (agentType) => {
  const agentKey = agentType === 'workflow_generation' ? 'workflow' : agentType;
  return {
    badge: THEME.agentBadges[agentType] || THEME.agentBadges.sparql,
    accent: THEME.agentAccents[agentType] || THEME.agentAccents.sparql,
    focus: AGENT_FORM_FOCUS[agentType] || AGENT_FORM_FOCUS.sparql,
    icon: THEME.agents[agentKey]?.icon || THEME.agents.sparql.icon
  };
};

export default THEME; 