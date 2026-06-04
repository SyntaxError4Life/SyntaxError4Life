ext_to_lang = {
    # Python
    '.py': 'Python',
    '.pyw': 'Python',
    '.pyi': 'Python',
    
    # Web
    '.html': 'HTML',
    '.htm': 'HTML',
    '.xhtml': 'HTML',
    '.css': 'CSS',
    '.scss': 'SCSS',
    '.sass': 'Sass',
    '.less': 'Less',
    '.js': 'JavaScript',
    '.jsx': 'JavaScript',
    '.ts': 'TypeScript',
    '.tsx': 'TypeScript',
    '.vue': 'Vue',
    '.svelte': 'Svelte',
    
    # Système
    '.rs': 'Rust',
    '.go': 'Go',
    '.c': 'C',
    '.h': 'C',
    '.cpp': 'C++',
    '.hpp': 'C++',
    '.cxx': 'C++',
    '.cc': 'C++',
    '.java': 'Java',
    '.cs': 'C#',
    '.swift': 'Swift',
    '.kt': 'Kotlin',
    '.scala': 'Scala',
    '.rb': 'Ruby',
    '.php': 'PHP',
    '.pl': 'Perl',
    '.sh': 'Shell',
    '.bash': 'Shell',
    '.zsh': 'Shell',
    '.ps1': 'PowerShell',
    '.lua': 'Lua',
    '.sql': 'SQL',
    '.r': 'R',
    '.m': 'Objective-C',
    '.mm': 'Objective-C',
    
    # Fonctionnel
    '.hs': 'Haskell',
    '.erl': 'Erlang',
    '.ex': 'Elixir',
    '.clj': 'Clojure',
    '.fs': 'F#',
    '.ml': 'OCaml',
    
    # Modernes
    '.dart': 'Dart',
    '.jl': 'Julia',
    '.nim': 'Nim',
    '.zig': 'Zig',
    '.cr': 'Crystal',
    
    # Data (gardés)
    '.md': 'Markdown',
    '.mdx': 'Markdown',
    '.rst': 'reStructuredText',
    '.yaml': 'YAML',
    '.yml': 'YAML',
    '.json': 'JSON',
    '.toml': 'TOML',
    '.xml': 'XML',
    '.ini': 'INI',
    '.cfg': 'Config',
    '.conf': 'Config',
    
    # Build
    '.cmake': 'CMake',
    '.gradle': 'Gradle',
    '.sbt': 'SBT',
    
    # Docs/Markup
    '.tex': 'LaTeX',
    '.adoc': 'AsciiDoc',
    
    # Images (à exclure mais mappés quand même)
    '.svg': 'SVG',
}

# Extensions à exclure du compte final
EXCLUDED_LANGS = {
    'JSON', 'YAML', 'YML', 'TOML', 'XML', 'INI', 'CONFIG', 'CFG', 'CONF',
    'TXT', 'TEXT',
    'SVG', 'GIF', 'PNG', 'JPG', 'JPEG', 'ICO', 'BMP', 'WEBP',
    'SAMPLE', 'IDX', 'PACK', 'REV',
    'PYC', 'PYO',
    '(NO EXTENSION)',
    'Other',
    '1', '2', '3', '4', '5', '6', '7', '8', '9',  # Man pages
}