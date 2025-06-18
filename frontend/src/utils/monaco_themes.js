// Custom Monaco themes that match PaleoPal's professional UI design system

export const createPrismLightTheme = (monaco) => {
  monaco.editor.defineTheme('prism-light', {
    base: 'vs',
    inherit: true,
    rules: [
      // Comments - gray-500 - subtle and professional
      { token: 'comment', foreground: '6b7280', fontStyle: 'italic' },
      
      // Keywords - blue-600 - matching primary theme
      { token: 'keyword', foreground: '2563eb' },
      
      // Import keywords - purple-600 - distinct for imports
      { token: 'keyword.import', foreground: '9333ea' },
      { token: 'keyword.from', foreground: '9333ea' },
      { token: 'keyword.as', foreground: '9333ea' },
      
      // Strings - emerald-600 - professional green
      { token: 'string', foreground: '059669' },
      { token: 'string.uri', foreground: '059669' },
      
      // Numbers - orange-600 - warm accent
      { token: 'number', foreground: 'ea580c' },
      
      // Functions - indigo-600 - matching code agent theme
      { token: 'keyword.function', foreground: '4f46e5' },
      { token: 'function', foreground: '4f46e5' },
      { token: 'entity.name.function', foreground: '4f46e5' },
      { token: 'support.function', foreground: '4f46e5' },
      
      // Variables - slate-600 - distinct from functions
      { token: 'variable', foreground: '475569' },
      { token: 'variable.name', foreground: '475569' },
      { token: 'variable.other', foreground: '475569' },
      { token: 'variable.parameter', foreground: '64748b' }, // slightly lighter for parameters
      
      // Package/Module names - rose-600 - distinct for imports
      { token: 'entity.name.namespace', foreground: 'e11d48' },
      { token: 'entity.name.module', foreground: 'e11d48' },
      { token: 'support.module', foreground: 'e11d48' },
      { token: 'meta.import', foreground: 'e11d48' },
      
      // Operators - gray-600 - subtle
      { token: 'operator', foreground: '4b5563' },
      
      // Properties/Tags - red-600 - clean accent
      { token: 'property', foreground: 'dc2626' },
      { token: 'tag', foreground: 'dc2626' },
      
      // Types/Classes - teal-600 - matching SPARQL agent theme
      { token: 'type', foreground: '0d9488' },
      { token: 'type.identifier', foreground: '0d9488' },
      { token: 'class-name', foreground: '0d9488' },
      { token: 'entity.name.type', foreground: '0d9488' },
      { token: 'entity.name.class', foreground: '0d9488' },
      
      // Punctuation - gray-600 - professional
      { token: 'punctuation', foreground: '4b5563' },
      { token: 'delimiter', foreground: '4b5563' },
      
      // Built-ins - emerald-700 - slightly darker green
      { token: 'builtin', foreground: '047857' },
      { token: 'support.type', foreground: '047857' },
      
      // Constants - amber-600 - warm accent
      { token: 'constant', foreground: 'd97706' },
      { token: 'constant.language', foreground: 'd97706' },
      { token: 'constant.numeric', foreground: 'ea580c' }, // same as numbers
      
      // Regex - emerald-600 - consistent with strings
      { token: 'regexp', foreground: '059669' },
      
      // URLs - blue-500 - consistent with links
      { token: 'url', foreground: '3b82f6' },
      
      // SPARQL specific tokens
      { token: 'namespace', foreground: '7c3aed' }, // violet-600 for prefixed names
      { token: 'string.uri', foreground: '3b82f6' }, // blue for IRIs
    ],
    colors: {
      'editor.background': '#ffffff', // Pure white - matching UI cards
      'editor.foreground': '#111827', // gray-900 - primary text
      'editor.selectionBackground': '#dbeafe', // blue-100 - professional selection
      'editor.lineHighlightBackground': '#f8fafc', // slate-50 - very subtle
      'editorLineNumber.foreground': '#9ca3af', // gray-400 - subtle line numbers
      'editorLineNumber.activeForeground': '#6b7280', // gray-500 - active line number
      'editor.selectionHighlightBackground': '#dbeafe40', // blue-100 with opacity
      'editor.wordHighlightBackground': '#f3f4f620', // gray-100 with opacity
      'editor.wordHighlightStrongBackground': '#e5e7eb40', // gray-200 with opacity
      'editorBracketMatch.background': '#e5e7eb40', // gray-200 with opacity
      'editorBracketMatch.border': '#9ca3af', // gray-400 - subtle bracket match
      'editorCursor.foreground': '#2563eb', // blue-600 - matching primary
      'editor.findMatchBackground': '#fbbf2440', // amber highlight
      'editor.findMatchHighlightBackground': '#fbbf2420', // amber highlight subtle
    }
  });
};

export const createPrismDarkTheme = (monaco) => {
  monaco.editor.defineTheme('prism-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      // Comments - gray-400 - readable but subtle
      { token: 'comment', foreground: '9ca3af', fontStyle: 'italic' },
      
      // Keywords - blue-400 - bright primary in dark mode
      { token: 'keyword', foreground: '60a5fa' },
      
      // Import keywords - purple-400 - distinct for imports in dark
      { token: 'keyword.import', foreground: 'c084fc' },
      { token: 'keyword.from', foreground: 'c084fc' },
      { token: 'keyword.as', foreground: 'c084fc' },
      
      // Strings - emerald-400 - bright green for dark mode
      { token: 'string', foreground: '34d399' },
      { token: 'string.uri', foreground: '34d399' },
      
      // Numbers - orange-400 - warm accent for dark mode
      { token: 'number', foreground: 'fb923c' },
      
      // Functions - indigo-400 - matching code agent theme in dark
      { token: 'keyword.function', foreground: '818cf8' },
      { token: 'function', foreground: '818cf8' },
      { token: 'entity.name.function', foreground: '818cf8' },
      { token: 'support.function', foreground: '818cf8' },
      
      // Variables - slate-300 - distinct from functions in dark mode
      { token: 'variable', foreground: 'cbd5e1' },
      { token: 'variable.name', foreground: 'cbd5e1' },
      { token: 'variable.other', foreground: 'cbd5e1' },
      { token: 'variable.parameter', foreground: 'e2e8f0' }, // slightly lighter for parameters
      
      // Package/Module names - rose-400 - distinct for imports in dark
      { token: 'entity.name.namespace', foreground: 'fb7185' },
      { token: 'entity.name.module', foreground: 'fb7185' },
      { token: 'support.module', foreground: 'fb7185' },
      { token: 'meta.import', foreground: 'fb7185' },
      
      // Operators - gray-300 - visible but not prominent
      { token: 'operator', foreground: 'd1d5db' },
      
      // Properties/Tags - red-400 - bright accent for dark
      { token: 'property', foreground: 'f87171' },
      { token: 'tag', foreground: 'f87171' },
      
      // Types/Classes - teal-400 - matching SPARQL agent in dark
      { token: 'type', foreground: '2dd4bf' },
      { token: 'type.identifier', foreground: '2dd4bf' },
      { token: 'class-name', foreground: '2dd4bf' },
      { token: 'entity.name.type', foreground: '2dd4bf' },
      { token: 'entity.name.class', foreground: '2dd4bf' },
      
      // Punctuation - gray-300 - professional visibility
      { token: 'punctuation', foreground: 'd1d5db' },
      { token: 'delimiter', foreground: 'd1d5db' },
      
      // Built-ins - emerald-300 - bright green for dark
      { token: 'builtin', foreground: '6ee7b7' },
      { token: 'support.type', foreground: '6ee7b7' },
      
      // Constants - amber-400 - warm accent for dark
      { token: 'constant', foreground: 'fbbf24' },
      { token: 'constant.language', foreground: 'fbbf24' },
      { token: 'constant.numeric', foreground: 'fb923c' }, // same as numbers
      
      // Regex - emerald-400 - consistent with strings
      { token: 'regexp', foreground: '34d399' },
      
      // URLs - blue-400 - consistent with links in dark
      { token: 'url', foreground: '60a5fa' },
      
      // SPARQL specific tokens
      { token: 'namespace', foreground: 'a78bfa' }, // violet-400 for prefixed names in dark
      { token: 'string.uri', foreground: '60a5fa' }, // blue for IRIs in dark
    ],
    colors: {
      'editor.background': '#1f2937', // gray-800 - matching UI panels
      'editor.foreground': '#f9fafb', // gray-50 - primary text in dark
      'editor.selectionBackground': '#1e3a8a', // blue-800 - professional selection
      'editor.lineHighlightBackground': '#111827', // gray-900 - subtle highlight
      'editorLineNumber.foreground': '#6b7280', // gray-500 - subtle line numbers
      'editorLineNumber.activeForeground': '#9ca3af', // gray-400 - active line number
      'editor.selectionHighlightBackground': '#1e3a8a40', // blue-800 with opacity
      'editor.wordHighlightBackground': '#37415120', // gray-700 with opacity
      'editor.wordHighlightStrongBackground': '#4b556340', // gray-600 with opacity
      'editorBracketMatch.background': '#4b556340', // gray-600 with opacity
      'editorBracketMatch.border': '#6b7280', // gray-500 - visible bracket match
      'editorCursor.foreground': '#60a5fa', // blue-400 - bright cursor
      'editor.findMatchBackground': '#f59e0b40', // amber highlight for dark
      'editor.findMatchHighlightBackground': '#f59e0b20', // amber highlight subtle
    }
  });
}; 