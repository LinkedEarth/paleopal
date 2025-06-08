"""
Ontology extractor for TTL/RDF/OWL files.
Extracts entities and relationships that can be indexed.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import tempfile

from .base_extractor import BaseExtractor

class OntologyExtractor(BaseExtractor):
    """
    Extractor for ontology files (TTL, RDF, OWL, N3).
    Produces entity and relationship JSONs ready for indexing.
    """
    
    def _get_file_suffix(self) -> str:
        return ".ttl"
    
    async def extract_from_file(
        self, 
        file_path: Path, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract entities and relationships from an ontology file.
        
        Args:
            file_path: Path to ontology file (.ttl, .rdf, .owl, .n3)
            params: Extraction parameters:
                - target_classes: List of class URIs to focus on (required)
                - include_properties: Whether to include properties (default: True)
                - max_depth: Maximum relationship depth to explore (default: 2)
                - include_individuals: Whether to include individuals/instances (default: True)
                - namespace_filter: Only include entities from these namespaces (optional)
        
        Returns:
            List of extracted entity/relationship objects
        """
        self.logger.info(f"Extracting ontology data from: {file_path}")
        
        # Validate required parameters
        self._validate_params(params, ['target_classes'])
        
        try:
            # Import RDFLib (ontology parsing library)
            import rdflib
            from rdflib import Graph, Namespace, RDF, RDFS, OWL
        except ImportError:
            raise ImportError("RDFLib is required for ontology extraction. Install with: pip install rdflib")
        
        # Get parameters
        target_classes = params['target_classes']
        include_properties = params.get('include_properties', True)
        max_depth = params.get('max_depth', 2)
        include_individuals = params.get('include_individuals', True)
        namespace_filter = params.get('namespace_filter', [])
        
        # Load the ontology
        graph = Graph()
        
        # Determine format based on file extension
        file_format = self._get_rdf_format(file_path)
        
        try:
            graph.parse(file_path, format=file_format)
            self.logger.info(f"Loaded ontology with {len(graph)} triples")
        except Exception as e:
            raise ValueError(f"Failed to parse ontology file: {e}")
        
        extracted_data = []
        processed_entities = set()
        
        # Extract target classes and their related entities
        for class_uri in target_classes:
            class_data = self._extract_class_hierarchy(
                graph, class_uri, max_depth, processed_entities, namespace_filter
            )
            extracted_data.extend(class_data)
        
        # Extract properties if requested
        if include_properties:
            property_data = self._extract_properties(graph, namespace_filter)
            extracted_data.extend(property_data)
        
        # Extract individuals if requested
        if include_individuals:
            individual_data = self._extract_individuals(
                graph, target_classes, namespace_filter
            )
            extracted_data.extend(individual_data)
        
        # Extract relationships
        relationship_data = self._extract_relationships(
            graph, [item['uri'] for item in extracted_data if 'uri' in item]
        )
        extracted_data.extend(relationship_data)
        
        self.logger.info(f"Extracted {len(extracted_data)} ontology items")
        return self._clean_extracted_data(extracted_data)
    
    def _get_rdf_format(self, file_path: Path) -> str:
        """Determine RDF format from file extension."""
        suffix = file_path.suffix.lower()
        
        format_map = {
            '.ttl': 'turtle',
            '.rdf': 'xml',
            '.owl': 'xml',
            '.n3': 'n3',
            '.nt': 'nt',
            '.jsonld': 'json-ld'
        }
        
        return format_map.get(suffix, 'turtle')  # Default to turtle
    
    def _extract_class_hierarchy(
        self, 
        graph, 
        class_uri: str, 
        max_depth: int, 
        processed: Set[str],
        namespace_filter: List[str],
        current_depth: int = 0
    ) -> List[Dict[str, Any]]:
        """Extract a class and its hierarchy."""
        import rdflib
        from rdflib import RDF, RDFS, OWL
        
        if current_depth > max_depth or class_uri in processed:
            return []
        
        processed.add(class_uri)
        entities = []
        
        try:
            class_node = rdflib.URIRef(class_uri)
            
            # Skip if namespace filtering is active and class doesn't match
            if namespace_filter and not any(class_uri.startswith(ns) for ns in namespace_filter):
                return []
            
            # Extract class information
            class_data = {
                'content_type': 'ontology_entity',
                'entity_type': 'class',
                'uri': class_uri,
                'name': self._extract_label(graph, class_node),
                'description': self._extract_comment(graph, class_node),
                'extraction_type': 'ontology_class'
            }
            
            # Add additional properties
            properties = self._extract_entity_properties(graph, class_node)
            class_data.update(properties)
            
            entities.append(class_data)
            
            # Extract subclasses
            for subclass in graph.subjects(RDFS.subClassOf, class_node):
                if isinstance(subclass, rdflib.URIRef):
                    subclass_data = self._extract_class_hierarchy(
                        graph, str(subclass), max_depth, processed, 
                        namespace_filter, current_depth + 1
                    )
                    entities.extend(subclass_data)
            
            # Extract superclasses
            for superclass in graph.objects(class_node, RDFS.subClassOf):
                if isinstance(superclass, rdflib.URIRef):
                    superclass_data = self._extract_class_hierarchy(
                        graph, str(superclass), max_depth, processed,
                        namespace_filter, current_depth + 1
                    )
                    entities.extend(superclass_data)
        
        except Exception as e:
            self.logger.warning(f"Failed to extract class {class_uri}: {e}")
        
        return entities
    
    def _extract_properties(self, graph, namespace_filter: List[str]) -> List[Dict[str, Any]]:
        """Extract property definitions."""
        import rdflib
        from rdflib import RDF, RDFS, OWL
        
        properties = []
        
        # Find all properties
        property_types = [RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty]
        
        for prop_type in property_types:
            for prop in graph.subjects(RDF.type, prop_type):
                if isinstance(prop, rdflib.URIRef):
                    prop_uri = str(prop)
                    
                    # Apply namespace filter
                    if namespace_filter and not any(prop_uri.startswith(ns) for ns in namespace_filter):
                        continue
                    
                    prop_data = {
                        'content_type': 'ontology_entity',
                        'entity_type': 'property',
                        'property_type': self._get_property_type_name(prop_type),
                        'uri': prop_uri,
                        'name': self._extract_label(graph, prop),
                        'description': self._extract_comment(graph, prop),
                        'extraction_type': 'ontology_property'
                    }
                    
                    # Add domain and range information
                    domains = [str(d) for d in graph.objects(prop, RDFS.domain) if isinstance(d, rdflib.URIRef)]
                    ranges = [str(r) for r in graph.objects(prop, RDFS.range) if isinstance(r, rdflib.URIRef)]
                    
                    if domains:
                        prop_data['domain'] = domains
                    if ranges:
                        prop_data['range'] = ranges
                    
                    # Add additional properties
                    additional_props = self._extract_entity_properties(graph, prop)
                    prop_data.update(additional_props)
                    
                    properties.append(prop_data)
        
        return properties
    
    def _extract_individuals(self, graph, target_classes: List[str], namespace_filter: List[str]) -> List[Dict[str, Any]]:
        """Extract individuals/instances of target classes."""
        import rdflib
        from rdflib import RDF
        
        individuals = []
        
        for class_uri in target_classes:
            class_node = rdflib.URIRef(class_uri)
            
            # Find instances of this class
            for individual in graph.subjects(RDF.type, class_node):
                if isinstance(individual, rdflib.URIRef):
                    ind_uri = str(individual)
                    
                    # Apply namespace filter
                    if namespace_filter and not any(ind_uri.startswith(ns) for ns in namespace_filter):
                        continue
                    
                    ind_data = {
                        'content_type': 'ontology_entity',
                        'entity_type': 'individual',
                        'uri': ind_uri,
                        'name': self._extract_label(graph, individual),
                        'description': self._extract_comment(graph, individual),
                        'class_uri': class_uri,
                        'extraction_type': 'ontology_individual'
                    }
                    
                    # Add additional properties
                    properties = self._extract_entity_properties(graph, individual)
                    ind_data.update(properties)
                    
                    individuals.append(ind_data)
        
        return individuals
    
    def _extract_relationships(self, graph, entity_uris: List[str]) -> List[Dict[str, Any]]:
        """Extract relationships between entities."""
        import rdflib
        
        relationships = []
        processed_triples = set()
        
        for entity_uri in entity_uris:
            entity_node = rdflib.URIRef(entity_uri)
            
            # Extract outgoing relationships
            for predicate, obj in graph.predicate_objects(entity_node):
                if isinstance(predicate, rdflib.URIRef) and isinstance(obj, rdflib.URIRef):
                    triple = (str(entity_node), str(predicate), str(obj))
                    
                    if triple not in processed_triples:
                        processed_triples.add(triple)
                        
                        rel_data = {
                            'content_type': 'relationship',
                            'subject_uri': str(entity_node),
                            'predicate_uri': str(predicate),
                            'object_uri': str(obj),
                            'predicate_name': self._extract_label(graph, predicate) or self._get_local_name(str(predicate)),
                            'extraction_type': 'ontology_relationship'
                        }
                        
                        relationships.append(rel_data)
        
        return relationships
    
    def _extract_label(self, graph, node) -> str:
        """Extract label/name for a node."""
        import rdflib
        from rdflib import RDFS
        
        # Try rdfs:label first
        for label in graph.objects(node, RDFS.label):
            if isinstance(label, rdflib.Literal):
                return str(label)
        
        # Fall back to local name
        return self._get_local_name(str(node))
    
    def _extract_comment(self, graph, node) -> str:
        """Extract comment/description for a node."""
        import rdflib
        from rdflib import RDFS
        
        for comment in graph.objects(node, RDFS.comment):
            if isinstance(comment, rdflib.Literal):
                return str(comment)
        
        return ""
    
    def _extract_entity_properties(self, graph, node) -> Dict[str, Any]:
        """Extract additional properties for an entity."""
        import rdflib
        from rdflib import RDF, RDFS, OWL
        
        properties = {}
        
        # Skip standard RDF/RDFS/OWL properties we handle separately
        skip_predicates = {RDF.type, RDFS.label, RDFS.comment, RDFS.subClassOf, RDFS.domain, RDFS.range}
        
        for predicate, obj in graph.predicate_objects(node):
            if predicate not in skip_predicates:
                pred_name = self._get_local_name(str(predicate))
                
                if isinstance(obj, rdflib.Literal):
                    properties[pred_name] = str(obj)
                elif isinstance(obj, rdflib.URIRef):
                    properties[pred_name] = str(obj)
        
        return properties
    
    def _get_local_name(self, uri: str) -> str:
        """Extract local name from URI."""
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]
        return uri
    
    def _get_property_type_name(self, prop_type) -> str:
        """Convert property type URI to readable name."""
        import rdflib
        from rdflib import RDF, OWL
        
        type_names = {
            RDF.Property: 'property',
            OWL.ObjectProperty: 'object_property',
            OWL.DatatypeProperty: 'datatype_property',
            OWL.AnnotationProperty: 'annotation_property'
        }
        
        return type_names.get(prop_type, 'property')
    
    async def extract_from_url(
        self, 
        url: str, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract from an ontology URL.
        """
        self.logger.info(f"Extracting ontology from URL: {url}")
        
        # Download and delegate to file extraction
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Save to temp file with appropriate extension
                    file_extension = '.ttl'  # Default
                    if url.endswith('.rdf') or url.endswith('.owl'):
                        file_extension = '.rdf'
                    elif url.endswith('.n3'):
                        file_extension = '.n3'
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                        temp_file.write(content)
                        temp_path = Path(temp_file.name)
                    
                    try:
                        # Add URL to params for metadata
                        params_with_url = params.copy()
                        params_with_url['source_url'] = url
                        
                        result = await self.extract_from_file(temp_path, params_with_url)
                        
                        # Update source info for URL extraction
                        for item in result:
                            item['source_url'] = url
                        
                        return result
                    finally:
                        temp_path.unlink()
                else:
                    raise Exception(f"Failed to download ontology from {url}: {response.status}")
    
    def get_extraction_preview(self, file_path: Path) -> Dict[str, Any]:
        """
        Get a preview of what would be extracted without full processing.
        """
        try:
            import rdflib
            from rdflib import Graph, RDF, RDFS, OWL
            
            graph = Graph()
            file_format = self._get_rdf_format(file_path)
            graph.parse(file_path, format=file_format)
            
            # Count different entity types
            classes = set(graph.subjects(RDF.type, RDFS.Class)) | set(graph.subjects(RDF.type, OWL.Class))
            properties = set(graph.subjects(RDF.type, RDF.Property)) | \
                        set(graph.subjects(RDF.type, OWL.ObjectProperty)) | \
                        set(graph.subjects(RDF.type, OWL.DatatypeProperty))
            
            # Find namespaces
            namespaces = set()
            for subj, pred, obj in graph:
                for node in [subj, pred, obj]:
                    if isinstance(node, rdflib.URIRef):
                        uri = str(node)
                        if '#' in uri:
                            namespaces.add(uri.split('#')[0] + '#')
                        elif '/' in uri:
                            parts = uri.split('/')
                            if len(parts) > 3:
                                namespaces.add('/'.join(parts[:-1]) + '/')
            
            # Sample classes for targeting
            sample_classes = [str(c) for c in list(classes)[:10]]
            
            return {
                "total_triples": len(graph),
                "total_classes": len(classes),
                "total_properties": len(properties),
                "namespaces": list(namespaces)[:10],
                "sample_classes": sample_classes,
                "estimated_entities": len(classes) + len(properties),
                "extraction_feasible": len(graph) > 0 and len(classes) > 0
            }
        
        except Exception as e:
            return {"error": str(e)} 