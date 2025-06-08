"""
ReadTheDocs extractor for documentation sites.
Extracts documentation pages and code examples that can be indexed.
"""

import re
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup, Comment

from .base_extractor import BaseExtractor

class ReadTheDocsExtractor(BaseExtractor):
    """
    Extractor for ReadTheDocs documentation sites.
    Produces documentation and code example JSONs ready for indexing.
    """
    
    def _get_file_suffix(self) -> str:
        return ".html"
    
    async def extract_from_file(
        self, 
        file_path: Path, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract documentation from a single HTML file.
        
        Args:
            file_path: Path to .html file
            params: Extraction parameters
        
        Returns:
            List of extracted documentation objects
        """
        self.logger.info(f"Extracting documentation from file: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self._extract_from_html(content, str(file_path), params)
    
    async def extract_from_url(
        self, 
        url: str, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract documentation from ReadTheDocs URL(s).
        
        Args:
            url: Base URL to start crawling from
            params: Extraction parameters:
                - base_url: Base URL for the documentation site (required)
                - max_pages: Maximum pages to crawl (default: 50)
                - include_patterns: URL patterns to include (optional)
                - exclude_patterns: URL patterns to exclude (optional)
                - depth_limit: Maximum crawl depth (default: 3)
        
        Returns:
            List of extracted documentation objects
        """
        self.logger.info(f"Extracting documentation from URL: {url}")
        
        # Validate required parameters
        self._validate_params(params, ['base_url'])
        
        base_url = params['base_url']
        max_pages = params.get('max_pages', 50)
        include_patterns = params.get('include_patterns', [])
        exclude_patterns = params.get('exclude_patterns', [
            r'.*/_.*',  # Skip underscore paths
            r'.*/search.*',  # Skip search pages
            r'.*/genindex.*',  # Skip index pages
            r'.*/py-modindex.*',  # Skip module index
        ])
        depth_limit = params.get('depth_limit', 3)
        
        extracted_data = []
        visited_urls = set()
        to_visit = [(url, 0)]  # (url, depth)
        
        async with aiohttp.ClientSession() as session:
            while to_visit and len(visited_urls) < max_pages:
                current_url, depth = to_visit.pop(0)
                
                if current_url in visited_urls or depth > depth_limit:
                    continue
                
                if not self._should_include_url(current_url, include_patterns, exclude_patterns):
                    continue
                
                try:
                    self.logger.info(f"Crawling: {current_url} (depth: {depth})")
                    
                    async with session.get(current_url) as response:
                        if response.status != 200:
                            continue
                        
                        content = await response.text()
                        visited_urls.add(current_url)
                        
                        # Extract documentation from this page
                        page_data = self._extract_from_html(content, current_url, params)
                        extracted_data.extend(page_data)
                        
                        # Find links to follow
                        if depth < depth_limit:
                            soup = BeautifulSoup(content, 'html.parser')
                            links = self._extract_links(soup, current_url, base_url)
                            
                            for link in links:
                                if link not in visited_urls:
                                    to_visit.append((link, depth + 1))
                
                except Exception as e:
                    self.logger.warning(f"Failed to process {current_url}: {e}")
                    continue
        
        self.logger.info(f"Crawled {len(visited_urls)} pages, extracted {len(extracted_data)} items")
        return self._clean_extracted_data(extracted_data)
    
    def _extract_from_html(self, content: str, source_url: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract structured data from HTML content."""
        soup = BeautifulSoup(content, 'html.parser')
        extracted_data = []
        
        # Remove comments and script tags
        for element in soup(["script", "style"]):
            element.decompose()
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # Extract main documentation content
        main_content = self._extract_main_content(soup)
        if main_content:
            doc_data = {
                'content_type': 'documentation',
                'source_url': source_url,
                'title': self._extract_title(soup),
                'content': main_content['text'],
                'html_content': str(main_content['element']),
                'section_type': main_content.get('section_type', 'general'),
                'extraction_type': 'documentation'
            }
            
            # Add navigation context
            breadcrumbs = self._extract_breadcrumbs(soup)
            if breadcrumbs:
                doc_data['breadcrumbs'] = breadcrumbs
            
            extracted_data.append(doc_data)
        
        # Extract code examples
        code_examples = self._extract_code_examples(soup, source_url)
        extracted_data.extend(code_examples)
        
        # Extract API references
        api_refs = self._extract_api_references(soup, source_url)
        extracted_data.extend(api_refs)
        
        return extracted_data
    
    def _extract_main_content(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract the main documentation content."""
        # Try common ReadTheDocs content selectors
        content_selectors = [
            'div.document div.body',
            'div.rst-content',
            'main.main',
            'div.content',
            'article',
            'div#main-content'
        ]
        
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(separator='\n', strip=True)
                if len(text) > 100:  # Ensure meaningful content
                    section_type = self._determine_section_type(text, element)
                    return {
                        'element': element,
                        'text': text,
                        'section_type': section_type
                    }
        
        return None
    
    def _determine_section_type(self, text: str, element) -> str:
        """Determine the type of documentation section."""
        text_lower = text.lower()
        
        # Check for API documentation
        if any(keyword in text_lower for keyword in ['api', 'reference', 'function', 'class', 'method']):
            return 'api_reference'
        
        # Check for tutorial/guide
        if any(keyword in text_lower for keyword in ['tutorial', 'guide', 'example', 'getting started']):
            return 'tutorial'
        
        # Check for installation/setup
        if any(keyword in text_lower for keyword in ['install', 'setup', 'configuration', 'requirements']):
            return 'setup'
        
        return 'general'
    
    def _extract_code_examples(self, soup: BeautifulSoup, source_url: str) -> List[Dict[str, Any]]:
        """Extract code examples from the page."""
        code_examples = []
        
        # Find code blocks
        code_blocks = soup.find_all(['pre', 'code'])
        
        for idx, block in enumerate(code_blocks):
            code_text = block.get_text(strip=True)
            
            # Skip very short code snippets
            if len(code_text) < 20:
                continue
            
            # Determine language
            language = self._detect_code_language(block, code_text)
            
            # Get surrounding context
            context = self._get_code_context(block)
            
            code_data = {
                'content_type': 'code_example',
                'source_url': source_url,
                'code': code_text,
                'language': language,
                'context': context,
                'extraction_type': 'code_example',
                'example_id': f"code_{idx}"
            }
            
            code_examples.append(code_data)
        
        return code_examples
    
    def _extract_api_references(self, soup: BeautifulSoup, source_url: str) -> List[Dict[str, Any]]:
        """Extract API reference information."""
        api_refs = []
        
        # Look for function/class definitions
        api_elements = soup.find_all(['dl', 'div'], class_=re.compile(r'(function|class|method|attribute)'))
        
        for element in api_elements:
            api_data = self._parse_api_element(element, source_url)
            if api_data:
                api_refs.append(api_data)
        
        return api_refs
    
    def _parse_api_element(self, element, source_url: str) -> Optional[Dict[str, Any]]:
        """Parse a single API documentation element."""
        try:
            # Extract name
            name_elem = element.find(['dt', 'h1', 'h2', 'h3', 'h4'])
            if not name_elem:
                return None
            
            name = name_elem.get_text(strip=True)
            
            # Extract description
            desc_elem = element.find(['dd', 'div', 'p'])
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Determine API type
            api_type = 'function'  # default
            if 'class' in element.get('class', []):
                api_type = 'class'
            elif 'method' in element.get('class', []):
                api_type = 'method'
            elif 'attribute' in element.get('class', []):
                api_type = 'attribute'
            
            return {
                'content_type': 'api_reference',
                'source_url': source_url,
                'name': name,
                'description': description,
                'api_type': api_type,
                'html_content': str(element),
                'extraction_type': 'api_reference'
            }
        
        except Exception as e:
            self.logger.warning(f"Failed to parse API element: {e}")
            return None
    
    def _detect_code_language(self, element, code_text: str) -> str:
        """Detect the programming language of a code block."""
        # Check class attributes
        classes = element.get('class', [])
        for cls in classes:
            if cls.startswith('language-'):
                return cls.replace('language-', '')
            elif cls in ['python', 'javascript', 'bash', 'shell', 'yaml', 'json']:
                return cls
        
        # Simple heuristics based on content
        if 'import ' in code_text or 'def ' in code_text or 'print(' in code_text:
            return 'python'
        elif 'function ' in code_text or 'const ' in code_text or 'console.log' in code_text:
            return 'javascript'
        elif code_text.startswith('$') or 'sudo ' in code_text:
            return 'bash'
        elif code_text.strip().startswith('{') and code_text.strip().endswith('}'):
            return 'json'
        
        return 'text'
    
    def _get_code_context(self, element) -> str:
        """Get contextual information around a code block."""
        context_parts = []
        
        # Look for preceding heading or paragraph
        for sibling in element.previous_siblings:
            if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                context_parts.append(sibling.get_text(strip=True))
                break
            elif sibling.name == 'p':
                text = sibling.get_text(strip=True)
                if len(text) > 10:
                    context_parts.append(text)
                    break
        
        return ' '.join(context_parts) if context_parts else ""
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        # Try different title sources
        title_elem = soup.find('title')
        if title_elem:
            return title_elem.get_text(strip=True)
        
        h1_elem = soup.find('h1')
        if h1_elem:
            return h1_elem.get_text(strip=True)
        
        return "Unknown Title"
    
    def _extract_breadcrumbs(self, soup: BeautifulSoup) -> List[str]:
        """Extract breadcrumb navigation."""
        breadcrumbs = []
        
        # Common breadcrumb selectors
        breadcrumb_selectors = [
            'nav.breadcrumb',
            'ol.breadcrumb',
            'ul.breadcrumb',
            '.breadcrumbs'
        ]
        
        for selector in breadcrumb_selectors:
            breadcrumb_elem = soup.select_one(selector)
            if breadcrumb_elem:
                links = breadcrumb_elem.find_all(['a', 'span'])
                breadcrumbs = [link.get_text(strip=True) for link in links if link.get_text(strip=True)]
                break
        
        return breadcrumbs
    
    def _extract_links(self, soup: BeautifulSoup, current_url: str, base_url: str) -> List[str]:
        """Extract links to follow for crawling."""
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Convert relative to absolute
            absolute_url = urljoin(current_url, href)
            
            # Only include links within the base domain
            if not absolute_url.startswith(base_url):
                continue
            
            # Remove fragments
            clean_url = absolute_url.split('#')[0]
            
            if clean_url and clean_url not in links:
                links.append(clean_url)
        
        return links
    
    def _should_include_url(self, url: str, include_patterns: List[str], exclude_patterns: List[str]) -> bool:
        """Check if URL should be included based on patterns."""
        # Check exclude patterns first
        for pattern in exclude_patterns:
            if re.search(pattern, url):
                return False
        
        # If include patterns specified, URL must match at least one
        if include_patterns:
            return any(re.search(pattern, url) for pattern in include_patterns)
        
        return True 