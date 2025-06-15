// Custom Monaco themes that match Prism's oneLight and oneDark themes exactly

export const createPrismLightTheme = (monaco) => {
  monaco.editor.defineTheme('prism-light', {
    base: 'vs',
    inherit: true,
    rules: [
      // Comments - hsl(230, 4%, 64%) - italic
      { token: 'comment', foreground: '9ca3af', fontStyle: 'italic' },
      
      // Keywords - hsl(301, 63%, 40%) - purple
      { token: 'keyword', foreground: '9333ea' },
      
      // Strings - hsl(119, 34%, 47%) - green
      { token: 'string', foreground: '059669' },
      { token: 'string.uri', foreground: '059669' },
      
      // Numbers - hsl(35, 99%, 36%) - orange
      { token: 'number', foreground: 'ea580c' },
      
      // Functions - hsl(221, 87%, 60%) - blue
      { token: 'keyword.function', foreground: '3b82f6' },
      { token: 'function', foreground: '3b82f6' },
      
      // Variables - hsl(221, 87%, 60%) - blue
      { token: 'variable', foreground: '3b82f6' },
      
      // Operators - hsl(221, 87%, 60%) - blue
      { token: 'operator', foreground: '3b82f6' },
      
      // Properties/Tags - hsl(5, 74%, 59%) - red
      { token: 'property', foreground: 'dc2626' },
      { token: 'tag', foreground: 'dc2626' },
      
      // Types/Classes - hsl(35, 99%, 36%) - orange
      { token: 'type', foreground: 'ea580c' },
      { token: 'type.identifier', foreground: 'ea580c' },
      { token: 'class-name', foreground: 'ea580c' },
      
      // Punctuation - hsl(230, 8%, 24%) - dark gray
      { token: 'punctuation', foreground: '374151' },
      { token: 'delimiter', foreground: '374151' },
      
      // Built-ins - hsl(119, 34%, 47%) - green
      { token: 'builtin', foreground: '059669' },
      
      // Constants - hsl(35, 99%, 36%) - orange
      { token: 'constant', foreground: 'ea580c' },
      
      // Regex - hsl(119, 34%, 47%) - green
      { token: 'regexp', foreground: '059669' },
      
      // URLs - hsl(198, 99%, 37%) - cyan
      { token: 'url', foreground: '0891b2' },
    ],
    colors: {
      'editor.background': '#fafafa', // hsl(230, 1%, 98%)
      'editor.foreground': '#383a42', // hsl(230, 8%, 24%)
      'editor.selectionBackground': '#e5e5e6', // hsl(230, 1%, 90%)
      'editor.lineHighlightBackground': '#fafafa',
      'editorLineNumber.foreground': '#9ca3af',
      'editorLineNumber.activeForeground': '#374151',
      'editor.selectionHighlightBackground': '#e5e5e620',
      'editor.wordHighlightBackground': '#e5e5e620',
      'editor.wordHighlightStrongBackground': '#e5e5e640',
      'editorBracketMatch.background': '#e5e5e640',
      'editorBracketMatch.border': '#9ca3af',
    }
  });
};

export const createPrismDarkTheme = (monaco) => {
  monaco.editor.defineTheme('prism-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      // Comments - hsl(220, 10%, 40%) - gray, italic
      { token: 'comment', foreground: '6b7280', fontStyle: 'italic' },
      
      // Keywords - hsl(286, 60%, 67%) - purple
      { token: 'keyword', foreground: 'c084fc' },
      
      // Strings - hsl(95, 38%, 62%) - green
      { token: 'string', foreground: '84cc16' },
      { token: 'string.uri', foreground: '84cc16' },
      
      // Numbers - hsl(29, 54%, 61%) - orange
      { token: 'number', foreground: 'f59e0b' },
      
      // Functions - hsl(207, 82%, 66%) - blue
      { token: 'keyword.function', foreground: '60a5fa' },
      { token: 'function', foreground: '60a5fa' },
      
      // Variables - hsl(207, 82%, 66%) - blue
      { token: 'variable', foreground: '60a5fa' },
      
      // Operators - hsl(207, 82%, 66%) - blue
      { token: 'operator', foreground: '60a5fa' },
      
      // Properties/Tags - hsl(355, 65%, 65%) - red/pink
      { token: 'property', foreground: 'f87171' },
      { token: 'tag', foreground: 'f87171' },
      
      // Types/Classes - hsl(29, 54%, 61%) - orange
      { token: 'type', foreground: 'f59e0b' },
      { token: 'type.identifier', foreground: 'f59e0b' },
      { token: 'class-name', foreground: 'f59e0b' },
      
      // Punctuation - hsl(220, 14%, 71%) - light gray
      { token: 'punctuation', foreground: 'a1a1aa' },
      { token: 'delimiter', foreground: 'a1a1aa' },
      
      // Built-ins - hsl(95, 38%, 62%) - green
      { token: 'builtin', foreground: '84cc16' },
      
      // Constants - hsl(29, 54%, 61%) - orange
      { token: 'constant', foreground: 'f59e0b' },
      
      // Regex - hsl(95, 38%, 62%) - green
      { token: 'regexp', foreground: '84cc16' },
      
      // URLs - hsl(187, 47%, 55%) - cyan
      { token: 'url', foreground: '06b6d4' },
    ],
    colors: {
      'editor.background': '#282c34', // hsl(220, 13%, 18%)
      'editor.foreground': '#abb2bf', // hsl(220, 14%, 71%)
      'editor.selectionBackground': '#3e4451', // hsl(220, 13%, 28%)
      'editor.lineHighlightBackground': '#2c313c',
      'editorLineNumber.foreground': '#6b7280',
      'editorLineNumber.activeForeground': '#abb2bf',
      'editor.selectionHighlightBackground': '#3e445120',
      'editor.wordHighlightBackground': '#3e445120',
      'editor.wordHighlightStrongBackground': '#3e445140',
      'editorBracketMatch.background': '#3e445140',
      'editorBracketMatch.border': '#6b7280',
    }
  });
}; 