import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

# Add the parent directory to the path to import from backend
sys.path.append(str(Path(__file__).parent.parent))
from config import OPENAI_API_KEY, GOOGLE_API_KEY, CHROMA_DB_PATH, EMBEDDING_MODEL, EMBEDDING_PROVIDER, SPARQL_ENDPOINT_URL
from services.sparql_service import SPARQLService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import langchain components conditionally
try:
    from langchain_core.embeddings import Embeddings
    from langchain_openai import OpenAIEmbeddings
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_chroma import Chroma
    from langchain.schema.document import Document
except ImportError as e:
    logger.error(f"Error importing required packages: {e}")
    logger.error("Please install required packages: pip install langchain_chroma langchain_openai langchain_google_genai")
    raise

# Import local embeddings
try:
    from services.local_embeddings import create_local_embeddings, get_available_local_providers
    LOCAL_EMBEDDINGS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Local embeddings not available: {e}")
    LOCAL_EMBEDDINGS_AVAILABLE = False

class GraphDBEmbeddingService:
    """Service for managing entity embeddings and retrieval."""
    
    def __init__(self, db_path: Optional[str] = None, provider: str = EMBEDDING_PROVIDER):
        """
        Initialize the entity embedding service.
        
        Args:
            db_path: Path to the vector database (defaults to CHROMA_DB_PATH/graphdb)
            provider: Embedding provider to use ('openai', 'google', 'sentence-transformers', 'ollama', 'huggingface')
        """
        self.provider = provider
        self.embeddings = self._initialize_embeddings(provider)
        if db_path is None:
            # Use a subdirectory for entity embeddings to avoid conflicts
            db_path = os.path.join(CHROMA_DB_PATH, "graphdb")
        self.db_path = db_path
        self.vectorstore = None
        self.sparql_service = SPARQLService(endpoint_url=SPARQL_ENDPOINT_URL)
        
        # Classes to embed - using correct URI namespaces
        self.target_classes = [
            "http://linked.earth/ontology/archive#ArchiveType",
            "http://linked.earth/ontology/paleo_variables#PaleoVariable",
            "http://linked.earth/ontology/paleo_units#PaleoUnit",
            "http://linked.earth/ontology/paleo_proxy#PaleoProxy",
            "http://linked.earth/ontology/paleo_proxy#PaleoProxyGeneral",
            "http://linked.earth/ontology/interpretation#InterpretationVariable",
            "http://linked.earth/ontology/interpretation#InterpretationSeasonality"
        ]
        
        # Mapping from class URI to properties to include in the embedding
        self.class_properties = {
            "http://linked.earth/ontology/archive#ArchiveType": [
                "http://www.w3.org/2000/01/rdf-schema#label",
                "http://www.w3.org/2000/01/rdf-schema#comment"
            ],
            "http://linked.earth/ontology/paleo_variables#PaleoVariable": [
                "http://www.w3.org/2000/01/rdf-schema#label",
                "http://www.w3.org/2000/01/rdf-schema#comment"
            ],
            "http://linked.earth/ontology/paleo_units#PaleoUnit": [
                "http://www.w3.org/2000/01/rdf-schema#label",
                "http://www.w3.org/2000/01/rdf-schema#comment"
            ],
            "http://linked.earth/ontology/paleo_proxy#PaleoProxy": [
                "http://www.w3.org/2000/01/rdf-schema#label",
                "http://www.w3.org/2000/01/rdf-schema#comment"
            ],
            "http://linked.earth/ontology/paleo_proxy#PaleoProxyGeneral": [
                "http://www.w3.org/2000/01/rdf-schema#label",
                "http://www.w3.org/2000/01/rdf-schema#comment"
            ],
            "http://linked.earth/ontology/interpretation#InterpretationVariable": [
                "http://www.w3.org/2000/01/rdf-schema#label",
                "http://www.w3.org/2000/01/rdf-schema#comment"
            ],
            "http://linked.earth/ontology/interpretation#InterpretationSeasonality": [
                "http://www.w3.org/2000/01/rdf-schema#label",
                "http://www.w3.org/2000/01/rdf-schema#comment"
            ]
        }
    
    def _initialize_embeddings(self, provider: str) -> Embeddings:
        """
        Initialize the embedding model based on provider.
        
        Args:
            provider: Embedding provider to use ('openai', 'google', 'sentence-transformers', 'ollama', 'huggingface')
            
        Returns:
            Embeddings: A configured embedding model
            
        Raises:
            ValueError: If the provider is not supported or API key is missing
        """
        if provider == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in environment.")
            logger.info("Using OpenAI for entity embeddings")
            return OpenAIEmbeddings(model=EMBEDDING_MODEL)
            
        elif provider == "google":
            if not GOOGLE_API_KEY:
                raise ValueError("Google API key is required. Set GOOGLE_API_KEY in environment.")
            logger.info("Using Google for entity embeddings")
            return GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
        
        elif provider in ["sentence-transformers", "ollama", "huggingface"]:
            if not LOCAL_EMBEDDINGS_AVAILABLE:
                raise ValueError(f"Local embeddings not available. Please install required dependencies for {provider}")
            
            # Check if the specific provider is available
            available_providers = get_available_local_providers()
            if not available_providers.get(provider, False):
                raise ValueError(f"Local embedding provider '{provider}' is not available. Please install required dependencies.")
            
            logger.info(f"Using {provider} for local entity embeddings")
            return create_local_embeddings(provider)
            
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}. Supported: openai, google, sentence-transformers, ollama, huggingface")
    
    def _connect_to_vector_db(self) -> Chroma:
        """
        Connect to the vector database (create if it doesn't exist).
        
        Returns:
            Vector database connection
        """
        if not self.vectorstore:
            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            try:
                self.vectorstore = Chroma(
                    persist_directory=self.db_path,
                    embedding_function=self.embeddings
                )
                
                # Log the number of documents in the database
                collection_count = self.vectorstore._collection.count() if hasattr(self.vectorstore, "_collection") else 0
                logger.info(f"Connected to entity vector database with {collection_count} documents")
                
            except Exception as e:
                logger.error(f"Error connecting to entity vector database: {str(e)}")
                raise
        
        return self.vectorstore
    
    def _fetch_class_instances(self, class_uri: str) -> List[Dict[str, Any]]:
        """
        Fetch all instances of a specific class with their properties.
        
        Args:
            class_uri: URI of the class to fetch instances of
            
        Returns:
            List of instances with their properties
        """
        properties = self.class_properties.get(class_uri, ["http://www.w3.org/2000/01/rdf-schema#label"])
        properties_str = " ".join([f"OPTIONAL {{ ?instance <{prop}> ?{prop.split('#')[-1]} . }}" for prop in properties])
        
        query = f"""
        SELECT ?instance {" ".join([f"?{prop.split('#')[-1]}" for prop in properties])}
        WHERE {{
            ?instance a <{class_uri}> .
            {properties_str}
        }}
        """
        
        try:
            result = self.sparql_service.execute_query(query)
            return self.sparql_service.format_results(result)
        except Exception as e:
            logger.error(f"Error fetching instances of {class_uri}: {str(e)}")
            return []
    
    def _create_documents_from_instances(self, instances: List[Dict[str, Any]], class_uri: str) -> List[Document]:
        """
        Convert instances to Document objects for the vector database.
        
        Args:
            instances: List of class instances with properties
            class_uri: URI of the class these instances belong to
            
        Returns:
            List of Document objects
        """
        documents = []
        class_name = class_uri.split('#')[-1]
        
        for instance in instances:
            if "instance" not in instance:
                continue
            
            instance_uri = instance["instance"]["value"]
            
            # Collect text from all available properties
            instance_text = f"Class: {class_name}\nURI: {instance_uri}\n"
            
            for prop_uri in self.class_properties.get(class_uri, []):
                prop_name = prop_uri.split('#')[-1]
                if prop_name in instance and instance[prop_name]:
                    prop_value = instance[prop_name]["value"]
                    instance_text += f"{prop_name}: {prop_value}\n"
            
            doc = Document(
                page_content=instance_text,
                metadata={
                    "uri": instance_uri,
                    "class": class_uri,
                    "class_name": class_name,
                    "type": "entity"
                }
            )
            documents.append(doc)
        
        return documents
    
    def initialize(self) -> int:
        """
        Initialize the vector database with embeddings for all target classes.
        
        Returns:
            Number of embedded entities
        """
        logger.info(f"Initializing graphdb embeddings using {self.provider}")
        
        total_embedded = 0
        all_documents = []
        
        # Fetch and process entities for each class
        for class_uri in self.target_classes:
            class_name = class_uri.split('#')[-1]
            logger.info(f"Processing {class_name} entities")
            
            instances = self._fetch_class_instances(class_uri)
            logger.info(f"Found {len(instances)} instances of {class_name}")
            
            documents = self._create_documents_from_instances(instances, class_uri)
            all_documents.extend(documents)
            
            total_embedded += len(documents)
        
        # Connect to the vector database
        vectorstore = self._connect_to_vector_db()
        
        # Clear existing data if any
        if vectorstore._collection.count() > 0:
            logger.info("Clearing existing entity embeddings before adding new ones")
            vectorstore._collection.delete(where={"type": "entity"})
        
        # Add documents to the database in batches if there are many
        batch_size = 100
        for i in range(0, len(all_documents), batch_size):
            batch = all_documents[i:i+batch_size]
            vectorstore.add_documents(batch)
            logger.info(f"Added batch of {len(batch)} documents to vector database")
        
        logger.info(f"Successfully embedded {total_embedded} entities into the vector database")
        return total_embedded
    
    def get_matches(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find entities that match the query text.
        
        Args:
            query: The query text to match
            limit: Number of results to return
            
        Returns:
            List of matching entities with similarity scores
        """
        vectorstore = self._connect_to_vector_db()
        
        # Ensure the database has documents
        if vectorstore._collection.count() == 0:
            logger.warning("Entity vector database is empty. Please initialize it first.")
            return []
        
        
        # Retrieve similar documents
        results = vectorstore.similarity_search_with_relevance_scores(
            query,
            k=limit
        )
        
        # Format results
        matching_entities = []
        for doc, score in results:
            # Extract the properties from the document content
            properties = {}
            content_lines = doc.page_content.strip().split('\n')
            for line in content_lines:
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    properties[key] = value
            
            matching_entities.append({
                "uri": doc.metadata.get("uri"),
                "class": doc.metadata.get("class"),
                "class_name": doc.metadata.get("class_name"),
                "similarity": score,
                "properties": properties
            })
        
        return matching_entities
    
    def get_closest_entity(self, query: str, class_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the single closest matching entity of a specific class.
        
        Args:
            query: The query text to match
            class_name: Class name to filter results (without namespace)
            
        Returns:
            The closest matching entity or None if no match found
        """
        matches = self.find_matching_entities(query, class_name, top_k=1)
        if matches:
            return matches[0]
        return None 