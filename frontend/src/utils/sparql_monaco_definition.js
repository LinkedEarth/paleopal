/** Register SPARQL support in Monaco Editor */
/** SPARQL language support for Monaco -- Prism-compatible */
export function registerSparqlLanguage(monaco) {
    /* 1 — register language */
    monaco.languages.register({
      id: 'sparql',
      extensions: ['.rq', '.sparql'],
      aliases: ['SPARQL', 'rq']
    });
  
    /* 2 — Monarch grammar (case-insensitive, Prism keywords/functions) */
    monaco.languages.setMonarchTokensProvider('sparql', {
      ignoreCase: true,
      defaultToken: '',
      tokenPostfix: '.sparql',
  
      /* ─── Prism keyword groups ──────────────────────────────── */
      keywords: [
        // query/update keywords
        'a','add','all','as','asc','ask','by','clear','construct','copy','create',
        'data','default','delete','desc','describe','distinct','drop','exists',
        'filter','from','group','having','insert','into','limit','load','minus',
        'move','named','not','now','offset','optional','order','rand','reduced',
        'select','separator','service','silent','union','using','values','where',
        // miscellaneous
        'base','graph','prefix'
      ],
  
      /* functions (must be followed by “(” – Prism style) */
      functions: [
        'abs','avg','bnode','bound','ceil','coalesce','concat','contains','count',
        'datatype','day','encode_for_uri','floor','group_concat','hours','if',
        'iri','isblank','isiri','isliteral','isnumeric','isuri','lang','langmatches',
        'lcase','max','md5','min','minutes','month','regex','replace','round',
        'sameterm','sample','seconds','sha1','sha256','sha384','sha512','str',
        'strafter','strbefore','strdt','strends','strlang','strlen','strstarts',
        'substr','sum','timezone','tz','ucase','uri','year','rand','struuid',
        'uuid'
      ],
  
      brackets: [
        ['{', '}', 'delimiter.curly'],
        ['[', ']', 'delimiter.square'],
        ['(', ')', 'delimiter.parenthesis']
      ],
  
      tokenizer: {
        root: [
          /* comments */
          [/#[^\n]*/, 'comment'],
  
          /* booleans */
          [/\b(?:true|false)\b/, 'constant.language.boolean'],
  
          /* variables ?x / $x */
          [/[?$]\w+/, 'variable'],
  
          /* prefixed names   le:Dataset  */
          [/[A-Za-z_][\w-]*:[A-Za-z_][\w-]*/, 'namespace'],
  
          /* IRIs  <http://…> */
          [/<[^>]*>/, 'string.uri'],
  
          /* functions (must be followed by “(”) */
          [/[A-Za-z_][\w-]*(?=\s*\()/, {
            cases: {
              '@functions': 'support.function',
              '@keywords':  'keyword',
              '@default':   'identifier'
            }
          }],
  
          /* identifiers & keywords */
          [/[A-Za-z_][\w-]*/, {
            cases: {
              '@keywords': 'keyword',
              '@default':  'identifier'
            }
          }],
  
          /* literals */
          [/"{3}/,  { token: 'string.quote', next: '@tstring' }],
          [/"/,     { token: 'string.quote', next: '@string'   }],
  
          /* operators, numbers, punctuation */
          [/\^\^/,                 'operator'],
          [/[<>!=]=|&&|\|\||[-+*/%]/, 'operator'],
          [/[{}()[\];.,]/,         'delimiter'],
          [/\d+\.\d*([eE][+-]?\d+)?/, 'number.float'],
          [/\d+[eE][+-]?\d+/,         'number.float'],
          [/\d+/,                     'number']
        ],
  
        /* single-line string */
        string: [
          [/[^\\"]+/,  'string'],
          [/\\./,      'string.escape'],
          [/"/,        { token: 'string.quote', next: '@pop' }]
        ],
  
        /* triple-quoted string */
        tstring: [
          [/[^\\"]+/,  'string'],
          [/\\./,      'string.escape'],
          [/"""/,      { token: 'string.quote', next: '@pop' }]
        ]
      }
    });
  
    /* 3 — language configuration */
    monaco.languages.setLanguageConfiguration('sparql', {
      comments: { lineComment: '#' },
      brackets: [['{','}'], ['[',']'], ['(',')']],
      autoClosingPairs: [
        { open: '{', close: '}' }, { open: '[', close: ']' }, { open: '(', close: ')' },
        { open: '"', close: '"', notIn: ['string'] },
        { open: '"""', close: '"""', notIn: ['string'] }
      ],
      surroundingPairs: [
        { open: '{', close: '}' }, { open: '[', close: ']' },
        { open: '(', close: ')' }, { open: '"', close: '"' }
      ],
      folding: {
        markers: { start: /^\s*#\s*region\b/i, end: /^\s*#\s*endregion\b/i }
      }
    });
  }
  
  