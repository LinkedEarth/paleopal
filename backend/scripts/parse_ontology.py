#!/usr/bin/env python
"""
Script to parse the LinkedEarth ontology and generate a context for the SPARQL agent.
This script extracts classes, properties, and prefixes from the ontology.ttl file.
"""

import os
import sys
from rdflib import Graph
from rdflib.namespace import RDF, RDFS, OWL
from pathlib import Path

# Add the parent directory to the path to import from backend if needed
script_dir = Path(__file__).parent
backend_dir = script_dir.parent
sys.path.append(str(backend_dir))

def extract_prefixes(graph):
    """Extract all prefixes from the graph."""
    prefixes = {}
    for prefix, namespace in graph.namespaces():
        if prefix:  # Skip empty prefix
            prefixes[prefix] = str(namespace)
    
    # Add some common prefixes if not already present
    common_prefixes = {
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
        'owl': 'http://www.w3.org/2002/07/owl#',
        'xsd': 'http://www.w3.org/2001/XMLSchema#',
        'geo': 'http://www.w3.org/2003/01/geo/wgs84_pos#',
        'dct': 'http://purl.org/dc/terms/',
    }
    
    for prefix, uri in common_prefixes.items():
        if prefix not in prefixes:
            prefixes[prefix] = uri
    
    # Ensure we have LinkedEarth-specific prefixes
    le_prefixes = {
        'le': 'http://linked.earth/ontology#',
        'pvar': 'http://linked.earth/ontology/paleo_variables#',
        'pproxy': 'http://linked.earth/ontology/paleo_proxy#',
        'arch': 'http://linked.earth/ontology/archive#',
        'punits': 'http://linked.earth/ontology/paleo_units#',
        'interp': 'http://linked.earth/ontology/interpretation#'
    }
    
    for prefix, uri in le_prefixes.items():
        prefixes[prefix] = uri
    
    return prefixes

def get_label(graph, uri):
    """Get the rdfs:label for a URI, or the local name if no label exists."""
    for label in graph.objects(uri, RDFS.label):
        return str(label)
    
    # If no label, extract the local name
    if '#' in str(uri):
        return str(uri).split('#')[-1]
    return str(uri).split('/')[-1]

def get_comment(graph, uri):
    """Get the rdfs:comment for a URI, or an empty string if none exists."""
    for comment in graph.objects(uri, RDFS.comment):
        return str(comment)
    return ""

def get_prefixed_uri(uri, prefixes):
    """Convert a full URI to prefixed form (e.g., 'le:Dataset')."""
    uri_str = str(uri)
    for prefix, namespace in prefixes.items():
        if uri_str.startswith(namespace):
            local_name = uri_str[len(namespace):]
            return f"{prefix}:{local_name}"
    return uri_str

def extract_classes(graph, prefixes):
    """Extract all classes from the graph with their labels and comments."""
    classes = []
    
    # Get all instances of owl:Class
    for class_uri in graph.subjects(RDF.type, OWL.Class):
        label = get_label(graph, class_uri)
        comment = get_comment(graph, class_uri)
        prefixed_uri = get_prefixed_uri(class_uri, prefixes)
        
        # Skip if the class has no label or is not in our namespace
        if not label or not any(str(class_uri).startswith(ns) for ns in prefixes.values()):
            continue
        
        # Only include a comment if it exists
        description = f"({comment})" if comment else ""
        classes.append((prefixed_uri, label, description))
    
    # Get all instances of rdfs:Class (some ontologies use this instead of owl:Class)
    for class_uri in graph.subjects(RDF.type, RDFS.Class):
        if (class_uri, RDF.type, OWL.Class) not in graph:  # Avoid duplicates
            label = get_label(graph, class_uri)
            comment = get_comment(graph, class_uri)
            prefixed_uri = get_prefixed_uri(class_uri, prefixes)
            
            # Skip if the class has no label or is not in our namespace
            if not label or not any(str(class_uri).startswith(ns) for ns in prefixes.values()):
                continue
            
            # Only include a comment if it exists
            description = f"({comment})" if comment else ""
            classes.append((prefixed_uri, label, description))
    
    return classes

def extract_properties(graph, prefixes):
    """Extract all properties from the graph with their domains and ranges."""
    properties = []
    
    # Get all owl:ObjectProperty instances
    for prop_uri in graph.subjects(RDF.type, OWL.ObjectProperty):
        # Get the domain and range of the property
        domains = list(graph.objects(prop_uri, RDFS.domain))
        ranges = list(graph.objects(prop_uri, RDFS.range))
        
        # Skip if the property doesn't have both domain and range
        if not domains or not ranges:
            continue
        
        # Get the label and comment for the property
        label = get_label(graph, prop_uri)
        prefixed_uri = get_prefixed_uri(prop_uri, prefixes)
        
        # Process each domain-range pair
        for domain in domains:
            domain_prefix = get_prefixed_uri(domain, prefixes)
            
            for range_uri in ranges:
                range_prefix = get_prefixed_uri(range_uri, prefixes)
                
                # Add the property to our list
                properties.append((domain_prefix, prefixed_uri, range_prefix, label))
    
    # Get all owl:DatatypeProperty instances
    for prop_uri in graph.subjects(RDF.type, OWL.DatatypeProperty):
        # Get the domain and range of the property
        domains = list(graph.objects(prop_uri, RDFS.domain))
        ranges = list(graph.objects(prop_uri, RDFS.range))
        
        # Skip if the property doesn't have both domain and range
        if not domains or not ranges:
            continue
        
        # Get the label and comment for the property
        label = get_label(graph, prop_uri)
        prefixed_uri = get_prefixed_uri(prop_uri, prefixes)
        
        # Process each domain-range pair
        for domain in domains:
            domain_prefix = get_prefixed_uri(domain, prefixes)
            
            for range_uri in ranges:
                range_prefix = get_prefixed_uri(range_uri, prefixes)
                
                # Add the property to our list
                properties.append((domain_prefix, prefixed_uri, range_prefix, label))
    
    # Get all rdf:Property instances (some ontologies use this instead of owl:ObjectProperty)
    for prop_uri in graph.subjects(RDF.type, RDF.Property):
        if ((prop_uri, RDF.type, OWL.ObjectProperty) not in graph and 
            (prop_uri, RDF.type, OWL.DatatypeProperty) not in graph):  # Avoid duplicates
            
            # Get the domain and range of the property
            domains = list(graph.objects(prop_uri, RDFS.domain))
            ranges = list(graph.objects(prop_uri, RDFS.range))
            
            # Skip if the property doesn't have both domain and range
            if not domains or not ranges:
                continue
            
            # Get the label and comment for the property
            label = get_label(graph, prop_uri)
            prefixed_uri = get_prefixed_uri(prop_uri, prefixes)
            
            # Process each domain-range pair
            for domain in domains:
                domain_prefix = get_prefixed_uri(domain, prefixes)
                
                for range_uri in ranges:
                    range_prefix = get_prefixed_uri(range_uri, prefixes)
                    
                    # Add the property to our list
                    properties.append((domain_prefix, prefixed_uri, range_prefix, label))
    
    return properties

def generate_context(ontology_path):
    """Generate a context from the ontology file."""
    # Parse the ontology file
    g = Graph()
    g.parse(ontology_path, format="turtle")
    
    # Extract prefixes, classes, and properties
    prefixes = extract_prefixes(g)
    classes = extract_classes(g, prefixes)
    properties = extract_properties(g, prefixes)
    
    # Format the prefixes for output
    prefixes_str = "\n".join([f"{prefix}: <{uri}>" for prefix, uri in prefixes.items()])
    
    # Format the classes for output - sorted by prefix for easier reading
    sorted_classes = sorted(classes, key=lambda x: x[0])
    classes_str = "\n".join([f"{uri} ({label} {desc})" for uri, label, desc in sorted_classes])
    
    # Group properties by domain for better organization
    domain_properties = {}
    for domain, prop, range_val, label in properties:
        if domain not in domain_properties:
            domain_properties[domain] = []
        domain_properties[domain].append((prop, range_val, label))
    
    # Format the properties for output - organized by domain
    properties_lines = []
    for domain in sorted(domain_properties.keys()):
        properties_lines.append(f"# Properties for {domain}")
        # Sort properties within each domain
        sorted_props = sorted(domain_properties[domain], key=lambda x: x[0])
        for prop, range_val, label in sorted_props:
            properties_lines.append(f"{domain} -> {prop} -> {range_val}  # {label}")
        properties_lines.append("")  # Add an empty line between domains
    
    properties_str = "\n".join(properties_lines)
    
    return {
        "prefixes": prefixes_str,
        "classes": classes_str,
        "properties": properties_str
    }

def save_context_to_file(context, output_path):
    """Save the context to a Python file."""
    with open(output_path, 'w') as f:
        f.write('"""\nAutomatically generated context from the LinkedEarth ontology.\n"""\n\n')
        
        f.write('# Prefixes\n')
        f.write('ONTOLOGY_PREFIXES = """\n')
        f.write(context["prefixes"])
        f.write('\n"""\n\n')
        
        f.write('# Classes\n')
        f.write('ONTOLOGY_CLASSES = """\n')
        f.write(context["classes"])
        f.write('\n"""\n\n')
        
        f.write('# Properties\n')
        f.write('ONTOLOGY_PROPERTIES = """\n')
        f.write(context["properties"])
        f.write('\n"""\n\n')
        
        # Add formatted property validation examples
        f.write('# Property validation examples\n')
        f.write('PROPERTY_VALIDATION = """\n')
        f.write("""# Property validation examples for specific domains:

## Dataset properties:
?dataset a le:Dataset .
?dataset le:hasChronData ?chronData . # ?chronData should be le:ChronData
?dataset le:hasPaleoData ?paleoData . # ?paleoData should be le:PaleoData
?dataset le:hasArchiveType ?archiveType . # ?archiveType should be arch:ArchiveType

## Variable properties:
?variable a le:Variable .
?variable le:hasStandardVariable ?stdVar . # ?stdVar should be pvar:PaleoVariable
?variable le:hasProxy ?proxy . # ?proxy should be pproxy:PaleoProxy
?variable le:hasUnits ?units . # ?units should be punits:PaleoUnit

## Location properties:
?location a le:Location .
?location geo:lat ?lat . # ?lat should be xsd:decimal
?location geo:long ?long . # ?long should be xsd:decimal

## Table hierarchy:
?dataset le:hasPaleoData ?paleoData .
?paleoData le:hasMeasurementTable ?table .
?table le:hasVariable ?variable .

## Resolution handling:
?variable le:hasResolution ?resolution .
?resolution le:hasMaxValue ?maxValue . # ?maxValue should be xsd:float
?resolution le:hasUnits ?resUnits . # ?resUnits should be punits:PaleoUnit
""")
        f.write('\n"""\n')

def main():
    # Path to the ontology file
    ontology_path = os.path.join(backend_dir, "ontology", "ontology.ttl")
    
    # Output path for the context file
    output_path = os.path.join(backend_dir, "agents", "sparql", "ontology_context.py")
    
    # Generate the context
    context = generate_context(ontology_path)
    
    # Save the context to a file
    save_context_to_file(context, output_path)
    
    print(f"Context successfully generated and saved to {output_path}")
    
    # Print some stats - fixed to avoid backslash in f-string
    prefix_count = context['prefixes'].count('\n') + 1
    class_count = context['classes'].count('\n') + 1
    property_count = context['properties'].count('\n') + 1
    
    print(f"Extracted {prefix_count} prefixes")
    print(f"Extracted {class_count} classes")
    print(f"Extracted {property_count} properties")

if __name__ == "__main__":
    main() 