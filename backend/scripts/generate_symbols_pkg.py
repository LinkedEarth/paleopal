#!/usr/bin/env python3
"""
Generate backend/all_symbols.txt by introspecting pylipd and pyleoclim.
Uses proper docstring parsing for better type extraction.
"""
import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
from typing import Any, get_origin, get_args, Union
from docstring_parser import parse as parse_docstring
from docstring_parser.common import DocstringStyle

PACKAGES = ["pyleoclim", "pylipd", "ammonyte"]

# ---------------------------------------------------------------------------
# Type mapping and resolution
# ---------------------------------------------------------------------------

def get_fully_qualified_name(obj) -> str:
    """Get the fully qualified name of a type/class."""
    if hasattr(obj, '__module__') and hasattr(obj, '__qualname__'):
        module = obj.__module__
        if module and module != 'builtins':
            return f"{module}.{obj.__qualname__}"
        return obj.__qualname__
    elif hasattr(obj, '__name__'):
        return obj.__name__
    else:
        return str(obj)

def resolve_type_from_string(type_str: str, obj_module=None) -> str:
    """Resolve a type string to a fully qualified name."""
    type_str = type_str.strip().rstrip(',')  # Remove trailing commas
    
    # Handle common patterns
    if not type_str or type_str.lower() in ['none', 'optional']:
        return 'None'
    
    # Handle enumeration/literal types like {'option1', 'option2', 'option3'}
    if type_str.startswith('{') and type_str.endswith('}'):
        inner = type_str[1:-1].strip()
        if inner:
            # Split by comma and clean up each option
            options = [opt.strip().strip('\'"') for opt in inner.split(',') if opt.strip()]
            if len(options) == 1:
                # Single option - treat as string literal
                return f"Literal['{options[0]}']"
            elif len(options) > 1:
                # Multiple options - create Literal type
                formatted_options = [f"'{opt}'" for opt in options]
                return f"Literal[{', '.join(formatted_options)}]"
        return 'str'  # fallback
    
    # Handle bracket-enclosed options like [True, False]
    if type_str.startswith('[') and type_str.endswith(']'):
        inner = type_str[1:-1].strip()
        if 'true' in inner.lower() and 'false' in inner.lower():
            return 'bool'
        elif ',' in inner:
            # Multiple options - treat as Union
            options = [opt.strip() for opt in inner.split(',') if opt.strip()]
            if len(options) <= 2 and all(opt.lower() in ['true', 'false'] for opt in options):
                return 'bool'
            else:
                return 'str'  # Likely string literals/enum values
        else:
            return resolve_type_from_string(inner, obj_module)
    
    # Handle Union types (including "or" syntax)
    if ' or ' in type_str.lower():
        # Split on "or" and resolve each part
        parts = [resolve_type_from_string(part.strip(), obj_module) for part in type_str.split(' or ')]
        if len(parts) == 2 and 'None' in parts:
            non_none = next(p for p in parts if p != 'None')
            return f"Optional[{non_none}]"
        return f"Union[{', '.join(parts)}]"
    
    if type_str.startswith('Union[') or type_str.startswith('Optional['):
        return type_str  # Already properly formatted
    
    # Handle List/Dict generics
    if type_str.startswith(('list[', 'List[')):
        inner = extract_generic_arg(type_str)
        inner_resolved = resolve_type_from_string(inner, obj_module)
        return f"list[{inner_resolved}]"
    elif type_str.startswith(('dict[', 'Dict[')):
        return f"dict"
    elif type_str.startswith(('tuple[', 'Tuple[')):
        return f"tuple"
    
    # Handle numpy types
    if 'numpy' in type_str.lower():
        if 'array' in type_str.lower():
            return 'numpy.ndarray'
        elif 'int' in type_str.lower():
            return 'numpy.integer'
        elif 'float' in type_str.lower():
            return 'numpy.floating'
        else:
            return 'numpy.ndarray'  # default for numpy types
    
    # Handle common aliases and variations
    type_aliases = {
        'string': 'str',
        'integer': 'int', 
        'number': 'float',
        'numeric': 'float',
        'boolean': 'bool',
        'boolean flag': 'bool',  # Handle "boolean flag" pattern
        'bool flag': 'bool',
        'array': 'list',
        'list or array': 'Union[list, numpy.ndarray]',
        'list of numpy.array': 'numpy.ndarray',  # Special case from docstrings
        'array_like': 'numpy.ndarray',
        'array-like': 'numpy.ndarray',
        'dict_like': 'dict',
        'dict-like': 'dict',
        'figure': 'matplotlib.figure.Figure',
        'axes': 'matplotlib.axes.Axes',
        'axis': 'matplotlib.axes.Axes',
        'datetime': 'datetime.datetime',
        'path': 'str',  # file paths
        'filepath': 'str',
        'filename': 'str',
    }
    
    type_lower = type_str.lower()
    if type_lower in type_aliases:
        return type_aliases[type_lower]
    
    # Basic types
    basic_types = {
        'str': 'str', 
        'int': 'int', 
        'float': 'float', 
        'bool': 'bool',
        'list': 'list', 
        'dict': 'dict', 
        'tuple': 'tuple',
        'object': 'object', 
        'any': 'Any'
    }
    
    if type_lower in basic_types:
        return basic_types[type_lower]
    
    # Try to resolve class names from our target packages
    for pkg in PACKAGES:
        try:
            # Try direct import
            if '.' not in type_str:
                # Try to find the class in the package
                pkg_module = importlib.import_module(pkg)
                if hasattr(pkg_module, type_str):
                    cls = getattr(pkg_module, type_str)
                    return get_fully_qualified_name(cls)
                
                # Try common submodules
                common_modules = ['core', 'utils', 'classes', 'core.series', 'core.dataset']
                for submod in common_modules:
                    try:
                        submodule = importlib.import_module(f"{pkg}.{submod}")
                        if hasattr(submodule, type_str):
                            cls = getattr(submodule, type_str)
                            return get_fully_qualified_name(cls)
                    except:
                        continue
            else:
                # Already qualified, try to import and verify
                try:
                    module_path, class_name = type_str.rsplit('.', 1)
                    if module_path.startswith(pkg):
                        mod = importlib.import_module(module_path)
                        if hasattr(mod, class_name):
                            cls = getattr(mod, class_name)
                            return get_fully_qualified_name(cls)
                except:
                    continue
        except:
            continue
    
    # If we can't resolve it, return as-is but clean it up
    return type_str.split()[0]  # Take first word, ignore description

def extract_generic_arg(generic_str: str) -> str:
    """Extract the inner type from a generic like 'list[ChronData]'."""
    start = generic_str.find('[')
    end = generic_str.rfind(']')
    if start != -1 and end != -1:
        return generic_str[start+1:end].strip()
    return 'Any'

def format_type_annotation(annotation) -> str:
    """Format a type annotation into a readable string."""
    if annotation is inspect.Parameter.empty:
        return 'Any'
    
    # Handle typing generics
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        if origin is Union:
            if len(args) == 2 and type(None) in args:
                # Optional type
                non_none = next(arg for arg in args if arg is not type(None))
                return f"Optional[{format_type_annotation(non_none)}]"
            else:
                return f"Union[{', '.join(format_type_annotation(arg) for arg in args)}]"
        elif origin in (list, tuple, dict):
            origin_name = get_fully_qualified_name(origin)
            if args:
                args_str = ', '.join(format_type_annotation(arg) for arg in args)
                return f"{origin_name}[{args_str}]"
            return origin_name
    
    return get_fully_qualified_name(annotation)

def parse_docstring_types(obj):
    """Parse docstring to extract parameter and return types using docstring_parser."""
    doc = inspect.getdoc(obj)
    
    # For __init__ methods, also try the class docstring if the method docstring is empty/generic
    if (not doc or "Initialize self" in doc or len(doc) < 50) and hasattr(obj, '__qualname__') and obj.__name__ == '__init__':
        # Try to get the class and its docstring
        try:
            # Get the class that owns this __init__ method
            cls = obj.__self_class__ if hasattr(obj, '__self_class__') else None
            if not cls:
                # Try to get from qualname
                module_name = getattr(obj, '__module__', '')
                if module_name:
                    module = sys.modules.get(module_name)
                    if module:
                        class_name = obj.__qualname__.split('.')[0]
                        cls = getattr(module, class_name, None)
            
            if cls:
                class_doc = inspect.getdoc(cls)
                if class_doc and len(class_doc) > len(doc or ""):
                    doc = class_doc
        except:
            pass
    
    if not doc:
        return {}, None
    
    try:
        # Try different docstring styles
        for style in [DocstringStyle.NUMPYDOC, DocstringStyle.GOOGLE, DocstringStyle.REST]:
            try:
                parsed = parse_docstring(doc, style=style)
                if parsed and (parsed.params or parsed.returns):
                    break
            except:
                continue
        else:
            # Fallback to auto-detection
            parsed = parse_docstring(doc)
        
        if not parsed:
            return {}, None
        
        # Extract parameter types
        param_types = {}
        for param in parsed.params:
            if param.type_name:
                resolved_type = resolve_type_from_string(param.type_name, getattr(obj, '__module__', None))
                param_types[param.arg_name] = resolved_type
        
        # Extract return type
        return_type = None
        if parsed.returns and parsed.returns.type_name:
            return_type = resolve_type_from_string(parsed.returns.type_name, getattr(obj, '__module__', None))
        
        return param_types, return_type
    
    except Exception as e:
        # Fallback to empty if parsing fails
        return {}, None

def format_signature(obj) -> str:
    """Format a function/method signature with proper type information."""
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return "()"
    
    # Get docstring-derived types
    doc_param_types, doc_return_type = parse_docstring_types(obj)
    
    params = []
    for param in sig.parameters.values():
        if param.name == 'self':
            params.append('self')
            continue
        
        # Use annotation if available, otherwise docstring type, otherwise Any
        if param.annotation != inspect.Parameter.empty:
            param_type = format_type_annotation(param.annotation)
        elif param.name in doc_param_types:
            param_type = doc_param_types[param.name]
        else:
            param_type = 'Any'
        
        # Handle default values
        if param.default != inspect.Parameter.empty:
            if param.default is None:
                param_type = f"Optional[{param_type}]" if not param_type.startswith(('Optional', 'Union')) else param_type
        
        params.append(f"{param.name}: {param_type}")
    
    # Determine return type
    if sig.return_annotation != inspect.Signature.empty:
        return_type = format_type_annotation(sig.return_annotation)
    elif doc_return_type:
        return_type = doc_return_type
    else:
        return_type = 'None'
    
    param_str = ', '.join(params)
    if return_type == 'None':
        return f"({param_str})"
    else:
        return f"({param_str}) -> {return_type}"

def walk_package(pkg_name: str):
    """Yield (qualified_name, obj) for every symbol in pkg_name."""
    try:
        pkg = importlib.import_module(pkg_name)
    except Exception as e:
        print(f"❌ Could not import {pkg_name}: {e}", file=sys.stderr)
        return

    # Recursively import sub-modules
    for mod_info in pkgutil.walk_packages(pkg.__path__, prefix=f"{pkg.__name__}."):
        if mod_info.name == "pylipd.usage" or "test" in mod_info.name:
            continue
        try:
            importlib.import_module(mod_info.name)
        except Exception:
            continue

    # Walk all loaded modules that belong to the package
    for name, module in list(sys.modules.items()):
        if name == pkg.__name__ or name.startswith(pkg.__name__ + "."):
            for attr_name, obj in inspect.getmembers(module):
                if attr_name.startswith("_"):
                    continue

                obj_mod = getattr(obj, "__module__", "")
                if not obj_mod.startswith(pkg.__name__):
                    continue

                # Only include objects defined in this specific module
                if obj_mod != name:
                    continue

                yield f"{name}.{attr_name}", obj

def main():
    """Generate symbols file with improved type information."""
    lines = []
    
    for pkg in PACKAGES:
        for qualified_name, obj in walk_package(pkg):
            if inspect.isclass(obj):
                # Class with constructor signature
                constructor_sig = format_signature(obj.__init__)
                lines.append(f"class {qualified_name}{constructor_sig}")
                
                # Public methods
                for method_name, method_obj in inspect.getmembers(obj, inspect.isfunction):
                    if method_name.startswith("_"):
                        continue
                    method_sig = format_signature(method_obj)
                    lines.append(f"  {method_name}{method_sig}")
            
            elif inspect.isfunction(obj):
                # Standalone function
                func_sig = format_signature(obj)
                lines.append(f"function {qualified_name}{func_sig}")
    
    # Remove duplicates while preserving order
    seen = set()
    deduped = []
    for line in lines:
        if line not in seen:
            deduped.append(line)
            seen.add(line)
    
    # Output header and symbols
    header = [
        "# Auto-generated symbols file for PyLiPD, PyLeoClim, and Ammonyte",
        "# Format: class/function name(params) -> return_type",
        "# Indented lines are methods of the preceding class",
        ""
    ]
    
    output_lines = header + deduped
    print("\n".join(output_lines))

if __name__ == "__main__":
    main()