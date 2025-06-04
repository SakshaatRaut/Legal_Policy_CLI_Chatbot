import re
import sqlite3
from pathlib import Path
import PyPDF2
import spacy
from tqdm import tqdm
import logging
from datetime import datetime
from collections import defaultdict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("gdpr_parser.log"), logging.StreamHandler()]
)
logger = logging.getLogger("GDPRParser")

class GDPRParser:
    """
    Enhanced parser for extracting structured information from GDPR PDF document
    and storing it in a SQLite database with comprehensive relationship mapping
    """
    
    def __init__(self, pdf_path):
        """
        Initialize the parser with the path to the GDPR PDF
        
        Args:
            pdf_path (str): Path to the GDPR PDF file
        """
        self.pdf_path = Path(r"D:\GDPR_1st\gdpr.pdf")
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Initialize spaCy for NLP tasks (entity recognition, sentence segmentation)
        try:
            # Use larger model for better entity recognition
            self.nlp = spacy.load("en_core_web_lg")
        except OSError:
            logger.info("Downloading spaCy language model...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_lg"])
            self.nlp = spacy.load("en_core_web_lg")
        
        # Database connection
        self.db_path = "gdpr_knowledge_base.db"
        self.conn = None
        self.cursor = None
        
        # TOC extraction
        self.toc = []
        
        # Cache for chapter and section information
        self.chapters = []
        self.sections = []
        
        # Cache for definitions
        self.definitions = {}
        
        # Cache for time-based requirements
        self.time_requirements = []
        
        # Cache for cross-references
        self.cross_references = defaultdict(list)
    
    def extract_text_from_pdf(self):
        """
        Extract raw text from the GDPR PDF document with metadata
        
        Returns:
            dict: Document structure with text content and page mapping
        """
        logger.info(f"Extracting text from {self.pdf_path}...")
        
        reader = PyPDF2.PdfReader(self.pdf_path)
        document = {
            "full_text": "",
            "pages": [],
            "metadata": {}
        }
        
        # Extract metadata if available
        if reader.metadata:
            document["metadata"] = dict(reader.metadata)
        
        # Extract text from each page
        for i, page in enumerate(tqdm(reader.pages, desc="Extracting pages")):
            page_text = page.extract_text()
            document["full_text"] += page_text + "\n"
            document["pages"].append({
                "number": i + 1,
                "text": page_text
            })
        
        return document
    
    def extract_table_of_contents(self, document):
        """
        Attempt to extract table of contents structure from the document
        
        Args:
            document (dict): Document structure with text
            
        Returns:
            list: Table of contents structure
        """
        logger.info("Extracting table of contents...")
        
        full_text = document["full_text"]
        
        # Look for common TOC patterns
        toc_start_pattern = r"(?:TABLE OF CONTENTS|CONTENTS|INDEX)"
        toc_end_pattern = r"(?:CHAPTER|Article|HAVE ADOPTED THIS REGULATION)"
        
        # Find TOC section
        toc_match = re.search(f"{toc_start_pattern}(.*?){toc_end_pattern}", full_text, re.DOTALL)
        
        if toc_match:
            toc_text = toc_match.group(1)
            
            # Extract chapter patterns
            chapter_pattern = r"CHAPTER\s+([IVX]+)\s+([^\n]+)"
            for chapter_match in re.finditer(chapter_pattern, toc_text):
                chapter_num = chapter_match.group(1)
                chapter_title = chapter_match.group(2).strip()
                self.chapters.append({
                    "number": chapter_num,
                    "title": chapter_title,
                    "articles": []
                })
            
            # Extract section patterns
            section_pattern = r"Section\s+(\d+)[:\s]+([^\n]+)"
            for section_match in re.finditer(section_pattern, toc_text):
                section_num = section_match.group(1)
                section_title = section_match.group(2).strip()
                self.sections.append({
                    "number": section_num,
                    "title": section_title,
                    "articles": []
                })
        
        # If TOC extraction failed, create a basic structure
        if not self.chapters:
            logger.warning("Could not extract TOC. Using basic structure detection.")
            # Find chapters and sections in main text
            chapter_pattern = r"CHAPTER\s+([IVX]+)\s+([^\n]+)"
            for chapter_match in re.finditer(chapter_pattern, full_text):
                chapter_num = chapter_match.group(1)
                chapter_title = chapter_match.group(2).strip()
                self.chapters.append({
                    "number": chapter_num,
                    "title": chapter_title,
                    "articles": []
                })
            
            section_pattern = r"Section\s+(\d+)[:\s]+([^\n]+)"
            for section_match in re.finditer(section_pattern, full_text):
                section_num = section_match.group(1)
                section_title = section_match.group(2).strip()
                self.sections.append({
                    "number": section_num,
                    "title": section_title,
                    "articles": []
                })
        
        return {
            "chapters": self.chapters,
            "sections": self.sections
        }
    
    def preprocess_text(self, text):
        """
        Clean and preprocess the extracted text
        
        Args:
            text (str): Raw text from PDF
            
        Returns:
            str: Preprocessed text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common OCR issues
        text = text.replace('|', 'I')
        text = text.replace('l1', 'h')
        text = text.replace('—', '-')
        text = text.replace('–', '-')
        
        # Normalize article headers
        text = re.sub(r'Article\s+(\d+)\s*[—–-]\s*', r'Article \1 - ', text)
        
        return text
    
    def extract_recitals(self, text):
        """
        Extract recitals (preamble considerations) from the GDPR text
        
        Args:
            text (str): Preprocessed text
            
        Returns:
            list: List of dictionaries containing recital number and content
        """
        logger.info("Extracting recitals...")
        
        # Pattern to match recitals - numbered paragraphs before the actual regulation text
        recital_pattern = r'\((\d+)\)\s+([^(]+?)(?=\(\d+\)|HAVE ADOPTED THIS REGULATION)'
        
        recitals = []
        for match in re.finditer(recital_pattern, text, re.DOTALL):
            number = match.group(1)
            content = match.group(2).strip()
            
            recitals.append({
                'number': number,
                'content': content
            })
        
        logger.info(f"Found {len(recitals)} recitals")
        return recitals
    
    def extract_articles_with_structure(self, text):
        """
        Extract individual articles from the GDPR text with chapter/section structure
        
        Args:
            text (str): Preprocessed text
            
        Returns:
            list: List of dictionaries containing article details and hierarchical placement
        """
        logger.info("Extracting articles with structural hierarchy...")
        
        # First, identify chapter and section boundaries
        chapter_pattern = r'CHAPTER\s+([IVX]+)\s+([^\n]+)'
        section_pattern = r'Section\s+(\d+)[:\s]+([^\n]+)'
        article_pattern = r'Article\s+(\d+)\s*-\s*([^\n]+)'
        
        # Find chapter positions
        chapter_positions = []
        for match in re.finditer(chapter_pattern, text):
            chapter_positions.append({
                'number': match.group(1),
                'title': match.group(2).strip(),
                'start': match.start(),
                'end': None
            })
        
        # Set chapter end positions
        for i in range(len(chapter_positions) - 1):
            chapter_positions[i]['end'] = chapter_positions[i + 1]['start']
        if chapter_positions:
            chapter_positions[-1]['end'] = len(text)
        
        # Find section positions
        section_positions = []
        for match in re.finditer(section_pattern, text):
            section_positions.append({
                'number': match.group(1),
                'title': match.group(2).strip(),
                'start': match.start(),
                'end': None
            })
        
        # Set section end positions
        for i in range(len(section_positions) - 1):
            section_positions[i]['end'] = section_positions[i + 1]['start']
        if section_positions:
            section_positions[-1]['end'] = len(text)
        
        # Find all article headers
        articles = []
        prev_start = None
        prev_number = None
        prev_title = None
        
        for match in re.finditer(article_pattern, text):
            if prev_start is not None:
                # Extract content between previous article header and current one
                content = text[prev_start:match.start()].strip()
                
                # Find chapter and section for this article
                article_chapter = None
                article_section = None
                
                for chapter in chapter_positions:
                    if prev_start >= chapter['start'] and (chapter['end'] is None or prev_start < chapter['end']):
                        article_chapter = {'number': chapter['number'], 'title': chapter['title']}
                        break
                
                for section in section_positions:
                    if prev_start >= section['start'] and (section['end'] is None or prev_start < section['end']):
                        article_section = {'number': section['number'], 'title': section['title']}
                        break
                
                articles.append({
                    'number': prev_number,
                    'title': prev_title,
                    'content': content,
                    'chapter': article_chapter,
                    'section': article_section
                })
            
            prev_start = match.start()
            prev_number = match.group(1)
            prev_title = match.group(2).strip()
        
        # Handle the last article
        if prev_start is not None:
            content = text[prev_start:].strip()
            
            # Find chapter and section for this article
            article_chapter = None
            article_section = None
            
            for chapter in chapter_positions:
                if prev_start >= chapter['start'] and (chapter['end'] is None or prev_start < chapter['end']):
                    article_chapter = {'number': chapter['number'], 'title': chapter['title']}
                    break
            
            for section in section_positions:
                if prev_start >= section['start'] and (section['end'] is None or prev_start < section['end']):
                    article_section = {'number': section['number'], 'title': section['title']}
                    break
            
            articles.append({
                'number': prev_number,
                'title': prev_title,
                'content': content,
                'chapter': article_chapter,
                'section': article_section
            })
        
        logger.info(f"Found {len(articles)} articles")
        return articles
    
    def extract_paragraphs_and_subparagraphs(self, article):
        """
        Extract numbered paragraphs and sub-paragraphs from an article
        
        Args:
            article (dict): Article dictionary with number, title and content
            
        Returns:
            dict: Updated article with paragraphs and sub-paragraphs
        """
        content = article['content']
        
        # Remove the article header from content
        header_pattern = r'Article\s+(\d+)\s*-\s*([^\n]+)'
        content = re.sub(header_pattern, '', content).strip()
        
        # Pattern to match numbered paragraphs (accounting for multi-digit paragraph numbers)
        paragraph_pattern = r'(\d+)\.(\s+[^0-9]+?)(?=(?:\d+\.)|(?:\([a-z]\))|$)'
        
        paragraphs = []
        
        for match in re.finditer(paragraph_pattern, content, re.DOTALL):
            number = match.group(1)
            text = match.group(2).strip()
            
            # Look for sub-paragraphs (a), (b), etc.
            subparagraph_pattern = r'\(([a-z])\)([^()]+?)(?=\([a-z]\)|$)'
            subparagraphs = []
            
            for submatch in re.finditer(subparagraph_pattern, text, re.DOTALL):
                subparagraph_letter = submatch.group(1)
                subparagraph_text = submatch.group(2).strip()
                
                # Look for sub-sub-paragraphs (i), (ii), etc.
                subsubparagraph_pattern = r'\(([ivx]+)\)([^()]+?)(?=\([ivx]+\)|$)'
                subsubparagraphs = []
                
                for subsubmatch in re.finditer(subsubparagraph_pattern, subparagraph_text, re.DOTALL):
                    subsubparagraph_number = subsubmatch.group(1)
                    subsubparagraph_text = subsubmatch.group(2).strip()
                    
                    subsubparagraphs.append({
                        'number': subsubparagraph_number,
                        'text': subsubparagraph_text
                    })
                
                subparagraphs.append({
                    'letter': subparagraph_letter,
                    'text': subparagraph_text,
                    'subsubparagraphs': subsubparagraphs
                })
            
            # Clean up paragraph text if subparagraphs were found
            if subparagraphs:
                # Extract only the text before the first subparagraph
                main_text = re.split(r'\([a-z]\)', text)[0].strip()
                
                paragraphs.append({
                    'number': number,
                    'text': main_text,
                    'subparagraphs': subparagraphs
                })
            else:
                paragraphs.append({
                    'number': number,
                    'text': text,
                    'subparagraphs': []
                })
        
        # If no paragraphs were found using the pattern, try to use spaCy to segment by sentences
        if not paragraphs:
            doc = self.nlp(content)
            paragraphs = [{'number': '1', 'text': content, 'subparagraphs': []}]
        
        article['paragraphs'] = paragraphs
        return article
    
    def extract_definitions(self, articles):
        """
        Extract definitions from Article 4 or other definitional sections
        
        Args:
            articles (list): List of article dictionaries
            
        Returns:
            dict: Mapping of terms to their definitions
        """
        logger.info("Extracting definitions...")
        
        definitions = {}
        
        # Look for definition articles (typically Article 4, but others may have definitions too)
        definition_articles = [a for a in articles if "definition" in a['title'].lower() or a['number'] == '4']
        
        for article in definition_articles:
            for paragraph in article.get('paragraphs', []):
                # Check if paragraph contains a definition (often in format "X means Y")
                definition_patterns = [
                    r'[\'"]([^\'\"]+)[\'"] means (.+)',
                    r'[\'"]([^\'\"]+)[\'"] refers to (.+)',
                    r'[\'"]([^\'\"]+)[\'"] shall mean (.+)'
                ]
                
                for pattern in definition_patterns:
                    for match in re.finditer(pattern, paragraph['text'], re.IGNORECASE):
                        term = match.group(1).strip()
                        definition = match.group(2).strip()
                        definitions[term] = {
                            'term': term,
                            'definition': definition,
                            'article': article['number'],
                            'paragraph': paragraph['number']
                        }
                
                # Look in subparagraphs for definitions
                for subpara in paragraph.get('subparagraphs', []):
                    definition_patterns = [
                        r'[\'"]([^\'\"]+)[\'"] means (.+)',
                        r'[\'"]([^\'\"]+)[\'"] refers to (.+)',
                        r'[\'"]([^\'\"]+)[\'"] shall mean (.+)'
                    ]
                    
                    for pattern in definition_patterns:
                        for match in re.finditer(pattern, subpara['text'], re.IGNORECASE):
                            term = match.group(1).strip()
                            definition = match.group(2).strip()
                            definitions[term] = {
                                'term': term,
                                'definition': definition,
                                'article': article['number'],
                                'paragraph': paragraph['number'],
                                'subparagraph': subpara['letter']
                            }
        
        self.definitions = definitions
        logger.info(f"Found {len(definitions)} definitions")
        return definitions
    
    def extract_requirements(self, article):
        """
        Extract specific requirements and obligations from an article
        with enhanced entity recognition
        
        Args:
            article (dict): Article with paragraphs
            
        Returns:
            dict: Updated article with requirements field
        """
        requirements = []
        entities = []
        
        # Create a complete article text for entity analysis
        full_text = article['content']
        doc = self.nlp(full_text)
        
        # Extract entities from the full article text
        for ent in doc.ents:
            if ent.label_ in ["ORG", "PERSON", "GPE", "LOC", "NORP"]:
                entities.append({
                    'text': ent.text,
                    'label': ent.label_,
                    'start': ent.start_char,
                    'end': ent.end_char
                })
        
        # Look for obligations and rights in paragraphs
        for para in article['paragraphs']:
            text = para['text']
            para_doc = self.nlp(text)
            
            # Look for sentences containing obligation-related words
            obligation_keywords = ['shall', 'must', 'required', 'ensure', 'necessary', 'obligation', 'right', 
                                  'responsibility', 'liable', 'accountable', 'duty', 'comply']
            right_keywords = ['right to', 'entitled to', 'freedom of', 'liberty to']
            time_keywords = ['within', 'days', 'months', 'years', 'period', 'delay', 'without undue delay', 
                            'immediately', 'promptly', 'no later than']
            
            for sent in para_doc.sents:
                sent_text = sent.text.strip()
                
                # Check for obligations
                is_obligation = any(keyword in sent_text.lower() for keyword in obligation_keywords)
                
                # Check for rights
                is_right = any(keyword in sent_text.lower() for keyword in right_keywords)
                
                # Check for time requirements
                is_time_requirement = any(keyword in sent_text.lower() for keyword in time_keywords)
                
                # If this is a requirement, add it
                if is_obligation or is_right:
                    req = {
                        'paragraph': para['number'],
                        'text': sent_text,
                        'is_obligation': is_obligation,
                        'is_right': is_right,
                        'is_time_requirement': is_time_requirement
                    }
                    requirements.append(req)
                    
                    # If it's a time requirement, add to separate collection
                    if is_time_requirement:
                        self.time_requirements.append({
                            'article': article['number'],
                            'paragraph': para['number'],
                            'text': sent_text
                        })
            
            # Process subparagraphs for requirements
            for subpara in para.get('subparagraphs', []):
                subpara_text = subpara['text']
                subpara_doc = self.nlp(subpara_text)
                
                for sent in subpara_doc.sents:
                    sent_text = sent.text.strip()
                    
                    # Check for obligations
                    is_obligation = any(keyword in sent_text.lower() for keyword in obligation_keywords)
                    
                    # Check for rights
                    is_right = any(keyword in sent_text.lower() for keyword in right_keywords)
                    
                    # Check for time requirements
                    is_time_requirement = any(keyword in sent_text.lower() for keyword in time_keywords)
                    
                    # If this is a requirement, add it
                    if is_obligation or is_right:
                        req = {
                            'paragraph': para['number'],
                            'subparagraph': subpara['letter'],
                            'text': sent_text,
                            'is_obligation': is_obligation,
                            'is_right': is_right,
                            'is_time_requirement': is_time_requirement
                        }
                        requirements.append(req)
                        
                        # If it's a time requirement, add to separate collection
                        if is_time_requirement:
                            self.time_requirements.append({
                                'article': article['number'],
                                'paragraph': para['number'],
                                'subparagraph': subpara['letter'],
                                'text': sent_text
                            })
        
        article['requirements'] = requirements
        article['entities'] = entities
        return article
    
    def extract_cross_references(self, articles):
        """
        Extract cross-references between articles
        
        Args:
            articles (list): List of article dictionaries
            
        Returns:
            dict: Mapping of article numbers to referenced article numbers
        """
        logger.info("Extracting cross-references between articles...")
        
        cross_references = defaultdict(list)
        
        # Regular expression to find references to other articles
        article_ref_pattern = r'Article\s+(\d+)(?:\s*\(\s*(\d+)\s*\))?'
        
        for article in articles:
            article_num = article['number']
            content = article['content']
            
            # Find all references to other articles
            for match in re.finditer(article_ref_pattern, content):
                referenced_article = match.group(1)
                referenced_paragraph = match.group(2) if match.group(2) else None
                
                # Don't include self-references
                if referenced_article != article_num:
                    reference = {
                        'article': referenced_article,
                        'paragraph': referenced_paragraph
                    }
                    
                    if reference not in cross_references[article_num]:
                        cross_references[article_num].append(reference)
        
        self.cross_references = dict(cross_references)
        
        # Count total references
        total_refs = sum(len(refs) for refs in cross_references.values())
        logger.info(f"Found {total_refs} cross-references between articles")
        
        return self.cross_references
    
    def identify_key_actors(self, articles):
        """
        Identify key actors (data subjects, controllers, processors, authorities)
        mentioned in the regulation
        
        Args:
            articles (list): List of article dictionaries
            
        Returns:
            dict: Mapping of actor types to their mentions and responsibilities
        """
        logger.info("Identifying key actors in the regulation...")
        
        actors = {
            'data_subject': [],
            'controller': [],
            'processor': [],
            'authority': [],
            'third_party': [],
            'recipient': []
        }
        
        actor_keywords = {
            'data_subject': ['data subject', 'natural person', 'concerned person', 'individual'],
            'controller': ['controller', 'joint controller'],
            'processor': ['processor', 'sub-processor'],
            'authority': ['supervisory authority', 'competent authority', 'lead authority'],
            'third_party': ['third party', 'third-party', 'third country'],
            'recipient': ['recipient']
        }
        
        for article in articles:
            article_num = article['number']
            content = article['content'].lower()
            
            for actor_type, keywords in actor_keywords.items():
                for keyword in keywords:
                    if keyword in content:
                        # Find sentences containing the actor
                        doc = self.nlp(article['content'])
                        for sent in doc.sents:
                            if keyword in sent.text.lower():
                                actors[actor_type].append({
                                    'article': article_num,
                                    'text': sent.text.strip()
                                })
        
        return actors
    
    def init_database(self, db_path="gdpr.db"):
        """
        Initialize SQLite database with appropriate schema
        
        Args:
            db_path (str): Path to the SQLite database file
        """
    
        logger.info(f"Initializing database at {db_path}")
        
        # Create new database file if it doesn't exist
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Enable foreign keys
        self.cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create tables
        
        # Chapters table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY,
            number TEXT NOT NULL,
            title TEXT NOT NULL
        )
        """)
        
        # Sections table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY,
            chapter_id INTEGER,
            number TEXT NOT NULL,
            title TEXT NOT NULL,
            FOREIGN KEY (chapter_id) REFERENCES chapters (id)
        )
        """)
        
        # Articles table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY,
            number TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            chapter_id INTEGER,
            section_id INTEGER,
            FOREIGN KEY (chapter_id) REFERENCES chapters (id),
            FOREIGN KEY (section_id) REFERENCES sections (id)
        )
        """)
        
        # Recitals table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS recitals (
            id INTEGER PRIMARY KEY,
            number INTEGER NOT NULL,
            content TEXT NOT NULL
        )
        """)
        
        # Paragraphs table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS paragraphs (
            id INTEGER PRIMARY KEY,
            article_id INTEGER NOT NULL,
            number TEXT NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles (id)
        )
        """)
        
        # Subparagraphs table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS subparagraphs (
            id INTEGER PRIMARY KEY,
            paragraph_id INTEGER NOT NULL,
            letter TEXT NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY (paragraph_id) REFERENCES paragraphs (id)
        )
        """)
        
        # Subsubparagraphs table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS subsubparagraphs (
            id INTEGER PRIMARY KEY,
            subparagraph_id INTEGER NOT NULL,
            number TEXT NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY (subparagraph_id) REFERENCES subparagraphs (id)
        )
        """)
        
        # Requirements table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS requirements (
            id INTEGER PRIMARY KEY,
            article_id INTEGER NOT NULL,
            paragraph_id INTEGER,
            subparagraph_id INTEGER,
            text TEXT NOT NULL,
            is_obligation BOOLEAN NOT NULL DEFAULT 0,
            is_right BOOLEAN NOT NULL DEFAULT 0,
            is_time_requirement BOOLEAN NOT NULL DEFAULT 0,
            FOREIGN KEY (article_id) REFERENCES articles (id),
            FOREIGN KEY (paragraph_id) REFERENCES paragraphs (id),
            FOREIGN KEY (subparagraph_id) REFERENCES subparagraphs (id)
        )
        """)
        
        # Entities table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY,
            article_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            label TEXT NOT NULL,
            start_pos INTEGER,
            end_pos INTEGER,
            FOREIGN KEY (article_id) REFERENCES articles (id)
        )
        """)
        
        # Definitions table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS definitions (
            id INTEGER PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT NOT NULL,
            article_id INTEGER,
            paragraph_id INTEGER,
            subparagraph_id INTEGER,
            FOREIGN KEY (article_id) REFERENCES articles (id),
            FOREIGN KEY (paragraph_id) REFERENCES paragraphs (id),
            FOREIGN KEY (subparagraph_id) REFERENCES subparagraphs (id)
        )
        """)
        
        # Cross-references table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS cross_references (
            id INTEGER PRIMARY KEY,
            from_article_id INTEGER NOT NULL,
            to_article_id INTEGER NOT NULL,
            to_paragraph TEXT,
            FOREIGN KEY (from_article_id) REFERENCES articles (id),
            FOREIGN KEY (to_article_id) REFERENCES articles (id)
        )
        """)
        
        # Time requirements table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS time_requirements (
            id INTEGER PRIMARY KEY,
            article_id INTEGER NOT NULL,
            paragraph_id INTEGER,
            subparagraph_id INTEGER,
            text TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles (id),
            FOREIGN KEY (paragraph_id) REFERENCES paragraphs (id),
            FOREIGN KEY (subparagraph_id) REFERENCES subparagraphs (id)
        )
        """)
        
        # Key actors table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS key_actors (
            id INTEGER PRIMARY KEY,
            actor_type TEXT NOT NULL,
            article_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles (id)
        )
        """)
        
        # Privacy policy sections table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS privacy_policy_sections (
            id INTEGER PRIMARY KEY,
            section_name TEXT NOT NULL,
            description TEXT NOT NULL,
            related_articles TEXT NOT NULL,
            required_information TEXT NOT NULL
        )
        """)
        
        # Initialize instance variables to store extracted data
        self.chapters = []
        self.sections = []
        self.definitions = {}
        self.cross_references = {}
        self.time_requirements = []
        
        # Commit all changes
        self.conn.commit()
        logger.info("Database schema created successfully")
        
    def populate_database(self, document, recitals, articles, actors):
        """
        Populate the database with extracted GDPR data
        
        Args:
            document (dict): Document structure
            recitals (list): List of recitals dictionaries
            articles (list): List of article dictionaries with paragraphs and structure
            actors (dict): Key actors with their mentions
        """
        logger.info("Populating database with extracted GDPR data...")
        
        # Insert chapters
        chapter_id_map = {}
        for chapter in self.chapters:
            self.cursor.execute(
                "INSERT INTO chapters (number, title) VALUES (?, ?)",
                (chapter['number'], chapter['title'])
            )
            chapter_id = self.cursor.lastrowid
            chapter_id_map[chapter['number']] = chapter_id
        
        # Insert sections
        section_id_map = {}
        for section in self.sections:
            chapter_id = None
            # Try to find associated chapter for this section
            for article in articles:
                if article.get('section') and article.get('section').get('number') == section['number'] and article.get('chapter'):
                    chapter_id = chapter_id_map.get(article['chapter']['number'])
                    break
            
            self.cursor.execute(
                "INSERT INTO sections (chapter_id, number, title) VALUES (?, ?, ?)",
                (chapter_id, section['number'], section['title'])
            )
            section_id = self.cursor.lastrowid
            section_id_map[section['number']] = section_id
        
        # Insert recitals
        for recital in recitals:
            self.cursor.execute(
                "INSERT INTO recitals (number, content) VALUES (?, ?)",
                (recital['number'], recital['content'])
            )
        
        # Insert articles and related data
        article_id_map = {}
        paragraph_id_map = {}
        subparagraph_id_map = {}
        
        for article in articles:
            # Get chapter and section IDs
            chapter_id = None
            section_id = None
            
            if article.get('chapter'):
                chapter_id = chapter_id_map.get(article['chapter']['number'])
            
            if article.get('section'):
                section_id = section_id_map.get(article['section']['number'])
            
            # Insert article
            self.cursor.execute(
                "INSERT INTO articles (number, title, content, chapter_id, section_id) VALUES (?, ?, ?, ?, ?)",
                (article['number'], article['title'], article['content'], chapter_id, section_id)
            )
            article_id = self.cursor.lastrowid
            article_id_map[article['number']] = article_id
            
            # Insert paragraphs
            for paragraph in article.get('paragraphs', []):
                self.cursor.execute(
                    "INSERT INTO paragraphs (article_id, number, text) VALUES (?, ?, ?)",
                    (article_id, paragraph['number'], paragraph['text'])
                )
                paragraph_id = self.cursor.lastrowid
                paragraph_id_map[(article['number'], paragraph['number'])] = paragraph_id
                
                # Insert subparagraphs
                for subparagraph in paragraph.get('subparagraphs', []):
                    self.cursor.execute(
                        "INSERT INTO subparagraphs (paragraph_id, letter, text) VALUES (?, ?, ?)",
                        (paragraph_id, subparagraph['letter'], subparagraph['text'])
                    )
                    subparagraph_id = self.cursor.lastrowid
                    subparagraph_id_map[(article['number'], paragraph['number'], subparagraph['letter'])] = subparagraph_id
                    
                    # Insert subsubparagraphs
                    for subsubparagraph in subparagraph.get('subsubparagraphs', []):
                        self.cursor.execute(
                            "INSERT INTO subsubparagraphs (subparagraph_id, number, text) VALUES (?, ?, ?)",
                            (subparagraph_id, subsubparagraph['number'], subsubparagraph['text'])
                        )
            
            # Insert requirements
            for requirement in article.get('requirements', []):
                paragraph_id = paragraph_id_map.get((article['number'], requirement['paragraph']))
                
                subparagraph_id = None
                if requirement.get('subparagraph'):
                    subparagraph_id = subparagraph_id_map.get(
                        (article['number'], requirement['paragraph'], requirement['subparagraph'])
                    )
                
                self.cursor.execute(
                    """
                    INSERT INTO requirements 
                    (article_id, paragraph_id, subparagraph_id, text, is_obligation, is_right, is_time_requirement) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article_id, 
                        paragraph_id, 
                        subparagraph_id, 
                        requirement['text'], 
                        requirement.get('is_obligation', False), 
                        requirement.get('is_right', False), 
                        requirement.get('is_time_requirement', False)
                    )
                )
            
            # Insert entities
            for entity in article.get('entities', []):
                self.cursor.execute(
                    "INSERT INTO entities (article_id, text, label, start_pos, end_pos) VALUES (?, ?, ?, ?, ?)",
                    (article_id, entity['text'], entity['label'], entity['start'], entity['end'])
                )
        
        # Insert definitions
        for term, definition in self.definitions.items():
            article_id = article_id_map.get(definition['article'])
            paragraph_id = paragraph_id_map.get((definition['article'], definition['paragraph']))
            
            subparagraph_id = None
            if definition.get('subparagraph'):
                subparagraph_id = subparagraph_id_map.get(
                    (definition['article'], definition['paragraph'], definition['subparagraph'])
                )
            
            self.cursor.execute(
                "INSERT INTO definitions (term, definition, article_id, paragraph_id, subparagraph_id) VALUES (?, ?, ?, ?, ?)",
                (term, definition['definition'], article_id, paragraph_id, subparagraph_id)
            )
        
        # Insert cross-references
        for from_article, references in self.cross_references.items():
            from_article_id = article_id_map.get(from_article)
            if from_article_id:
                for reference in references:
                    to_article_id = article_id_map.get(reference['article'])
                    if to_article_id:
                        self.cursor.execute(
                            "INSERT INTO cross_references (from_article_id, to_article_id, to_paragraph) VALUES (?, ?, ?)",
                            (from_article_id, to_article_id, reference.get('paragraph'))
                        )
        
        # Insert time requirements
        for time_req in self.time_requirements:
            article_id = article_id_map.get(time_req['article'])
            paragraph_id = paragraph_id_map.get((time_req['article'], time_req['paragraph']))
            
            subparagraph_id = None
            if time_req.get('subparagraph'):
                subparagraph_id = subparagraph_id_map.get(
                    (time_req['article'], time_req['paragraph'], time_req['subparagraph'])
                )
            
            self.cursor.execute(
                "INSERT INTO time_requirements (article_id, paragraph_id, subparagraph_id, text) VALUES (?, ?, ?, ?)",
                (article_id, paragraph_id, subparagraph_id, time_req['text'])
            )
        
        # Insert key actors
        for actor_type, mentions in actors.items():
            for mention in mentions:
                article_id = article_id_map.get(mention['article'])
                if article_id:
                    self.cursor.execute(
                        "INSERT INTO key_actors (actor_type, article_id, text) VALUES (?, ?, ?)",
                        (actor_type, article_id, mention['text'])
                    )
        
        # Insert privacy policy sections (mapping of GDPR requirements to policy sections)
        privacy_policy_sections = [
            {
                'section_name': 'Identity and Contact Details',
                'description': 'Information about the data controller and their contact details',
                'related_articles': '13(1)(a), 14(1)(a)',
                'required_information': 'Controller identity, contact details, DPO contact if applicable'
            },
            {
                'section_name': 'Types of Data Collected',
                'description': 'Categories of personal data being processed',
                'related_articles': '13(1)(c), 14(1)(d)',
                'required_information': 'Description of all categories of personal data processed'
            },
            {
                'section_name': 'Purposes of Processing',
                'description': 'Purposes for which personal data is processed',
                'related_articles': '13(1)(c), 14(1)(c)',
                'required_information': 'All purposes for which data is collected and processed'
            },
            {
                'section_name': 'Legal Basis',
                'description': 'Legal basis for processing personal data',
                'related_articles': '13(1)(c), 14(1)(c)',
                'required_information': 'Legal basis under Article 6 (and Article 9 if applicable)'
            },
            {
                'section_name': 'Recipients of Data',
                'description': 'Third parties who receive the data',
                'related_articles': '13(1)(e), 14(1)(e)',
                'required_information': 'Recipients or categories of recipients of personal data'
            },
            {
                'section_name': 'Data Transfers',
                'description': 'Information about international data transfers',
                'related_articles': '13(1)(f), 14(1)(f)',
                'required_information': 'Details of transfers to third countries, safeguards, means to obtain copy'
            },
            {
                'section_name': 'Retention Period',
                'description': 'How long data will be stored',
                'related_articles': '13(2)(a), 14(2)(a)',
                'required_information': 'Period data will be stored or criteria to determine period'
            },
            {
                'section_name': 'Data Subject Rights',
                'description': 'Rights available to individuals',
                'related_articles': '13(2)(b), 14(2)(c)',
                'required_information': 'Access, rectification, erasure, restriction, objection, portability rights'
            },
            {
                'section_name': 'Withdrawal of Consent',
                'description': 'Right to withdraw consent at any time',
                'related_articles': '13(2)(c), 14(2)(d)',
                'required_information': 'Information about right to withdraw consent and how to do so'
            },
            {
                'section_name': 'Complaint Rights',
                'description': 'Right to lodge a complaint with supervisory authority',
                'related_articles': '13(2)(d), 14(2)(e)',
                'required_information': 'Right to lodge complaint and contact details of supervisory authority'
            },
            {
                'section_name': 'Automated Decision Making',
                'description': 'Information about automated decision-making, including profiling',
                'related_articles': '13(2)(f), 14(2)(g)',
                'required_information': 'Existence, logic involved, significance and consequences of such processing'
            }
        ]
        
        for section in privacy_policy_sections:
            self.cursor.execute(
                """
                INSERT INTO privacy_policy_sections 
                (section_name, description, related_articles, required_information) 
                VALUES (?, ?, ?, ?)
                """,
                (
                    section['section_name'], 
                    section['description'], 
                    section['related_articles'], 
                    section['required_information']
                )
            )
        
        # Commit all changes
        self.conn.commit()
        logger.info("Database population completed successfully")
    
    def parse_and_load(self):
        """
        Main method to parse GDPR document and load into database
        
        This method orchestrates the entire extraction and database population process
        """
        logger.info("Starting GDPR document parsing and database loading...")
        
        try:
            # Extract raw text from PDF
            document = self.extract_text_from_pdf()
            
            # Extract table of contents structure
            toc = self.extract_table_of_contents(document)
            
            # Preprocess text
            preprocessed_text = self.preprocess_text(document["full_text"])
            
            # Extract recitals
            recitals = self.extract_recitals(preprocessed_text)
            
            # Extract articles with hierarchical structure
            articles = self.extract_articles_with_structure(preprocessed_text)
            
            # Process each article to extract paragraphs and subparagraphs
            for i in range(len(articles)):
                articles[i] = self.extract_paragraphs_and_subparagraphs(articles[i])
                articles[i] = self.extract_requirements(articles[i])
            
            # Extract cross references
            cross_references = self.extract_cross_references(articles)
            
            # Extract definitions
            definitions = self.extract_definitions(articles)
            
            # Extract key actors
            actors = self.identify_key_actors(articles)
            
            # Initialize database
            self.init_database(self.db_path)
            
            # Populate database
            self.populate_database(document, recitals, articles, actors)
            
            logger.info("GDPR parsing and database loading completed successfully")
            return True
        except Exception as e:
            logger.error(f"Error during parsing and loading: {str(e)}", exc_info=True)
            return False

    def get_article_by_number(self, article_number):
        """
        Retrieve complete information about a specific article by its number
        
        Args:
            article_number (str): Article number to retrieve
            
        Returns:
            dict: Complete article information with all relationships
        """
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
        
        # Get basic article info
        self.cursor.execute("""
            SELECT a.id, a.number, a.title, a.content, c.number, c.title, s.number, s.title
            FROM articles a
            LEFT JOIN chapters c ON a.chapter_id = c.id
            LEFT JOIN sections s ON a.section_id = s.id
            WHERE a.number = ?
        """, (article_number,))
        
        article_row = self.cursor.fetchone()
        if not article_row:
            return None
        
        article_id, article_num, article_title, article_content, chapter_num, chapter_title, section_num, section_title = article_row
        
        article = {
            'id': article_id,
            'number': article_num,
            'title': article_title,
            'content': article_content,
            'chapter': {'number': chapter_num, 'title': chapter_title} if chapter_num else None,
            'section': {'number': section_num, 'title': section_title} if section_num else None,
            'paragraphs': [],
            'requirements': [],
            'entities': []
        }
        
        # Get paragraphs
        self.cursor.execute("""
            SELECT id, number, text
            FROM paragraphs
            WHERE article_id = ?
            ORDER BY number
        """, (article_id,))
        
        for para_row in self.cursor.fetchall():
            para_id, para_num, para_text = para_row
            
            paragraph = {
                'id': para_id,
                'number': para_num,
                'text': para_text,
                'subparagraphs': []
            }
            
            # Get subparagraphs
            self.cursor.execute("""
                SELECT id, letter, text
                FROM subparagraphs
                WHERE paragraph_id = ?
                ORDER BY letter
            """, (para_id,))
            
            for subpara_row in self.cursor.fetchall():
                subpara_id, subpara_letter, subpara_text = subpara_row
                
                subparagraph = {
                    'id': subpara_id,
                    'letter': subpara_letter,
                    'text': subpara_text,
                    'subsubparagraphs': []
                }
                
                # Get subsubparagraphs
                self.cursor.execute("""
                    SELECT id, number, text
                    FROM subsubparagraphs
                    WHERE subparagraph_id = ?
                    ORDER BY number
                """, (subpara_id,))
                
                for subsubpara_row in self.cursor.fetchall():
                    subsubpara_id, subsubpara_num, subsubpara_text = subsubpara_row
                    
                    subsubparagraph = {
                        'id': subsubpara_id,
                        'number': subsubpara_num,
                        'text': subsubpara_text
                    }
                    
                    subparagraph['subsubparagraphs'].append(subsubparagraph)
                
                paragraph['subparagraphs'].append(subparagraph)
            
            article['paragraphs'].append(paragraph)
        
        # Get requirements
        self.cursor.execute("""
            SELECT id, text, is_obligation, is_right, is_time_requirement
            FROM requirements
            WHERE article_id = ?
        """, (article_id,))
        
        for req_row in self.cursor.fetchall():
            req_id, req_text, is_obligation, is_right, is_time_requirement = req_row
            
            requirement = {
                'id': req_id,
                'text': req_text,
                'is_obligation': bool(is_obligation),
                'is_right': bool(is_right),
                'is_time_requirement': bool(is_time_requirement)
            }
            
            article['requirements'].append(requirement)
        
        # Get entities
        self.cursor.execute("""
            SELECT id, text, label, start_pos, end_pos
            FROM entities
            WHERE article_id = ?
        """, (article_id,))
        
        for ent_row in self.cursor.fetchall():
            ent_id, ent_text, ent_label, ent_start, ent_end = ent_row
            
            entity = {
                'id': ent_id,
                'text': ent_text,
                'label': ent_label,
                'start': ent_start,
                'end': ent_end
            }
            
            article['entities'].append(entity)
        
        # Get cross-references
        self.cursor.execute("""
            SELECT a.number, cr.to_paragraph
            FROM cross_references cr
            JOIN articles a ON cr.to_article_id = a.id
            WHERE cr.from_article_id = ?
        """, (article_id,))
        
        article['cross_references'] = []
        for ref_row in self.cursor.fetchall():
            ref_article, ref_paragraph = ref_row
            
            reference = {
                'article': ref_article,
                'paragraph': ref_paragraph
            }
            
            article['cross_references'].append(reference)
        
        return article

    def search_by_keyword(self, keyword):
        """
        Search for articles containing the specified keyword
        
        Args:
            keyword (str): Keyword to search for
            
        Returns:
            list: List of matching articles with relevant context
        """
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
        
        # Search in article content
        self.cursor.execute("""
            SELECT id, number, title
            FROM articles
            WHERE content LIKE ?
            ORDER BY number
        """, (f'%{keyword}%',))
        
        results = []
        for article_row in self.cursor.fetchall():
            article_id, article_num, article_title = article_row
            
            # Find paragraphs containing the keyword
            self.cursor.execute("""
                SELECT number, text
                FROM paragraphs
                WHERE article_id = ? AND text LIKE ?
                ORDER BY number
            """, (article_id, f'%{keyword}%'))
            
            matching_paragraphs = []
            for para_row in self.cursor.fetchall():
                para_num, para_text = para_row
                
                # Create a snippet around the keyword
                keyword_position = para_text.lower().find(keyword.lower())
                start_pos = max(0, keyword_position - 50)
                end_pos = min(len(para_text), keyword_position + len(keyword) + 50)
                
                snippet = "..." if start_pos > 0 else ""
                snippet += para_text[start_pos:end_pos]
                snippet += "..." if end_pos < len(para_text) else ""
                
                matching_paragraphs.append({
                    'paragraph': para_num,
                    'snippet': snippet
                })
            
            results.append({
                'article': article_num,
                'title': article_title,
                'matches': matching_paragraphs
            })
        
        return results

    def get_requirements_for_role(self, role):
        """
        Get all requirements (obligations and rights) for a specific role
        
        Args:
            role (str): Role to search for (e.g., 'controller', 'processor', 'data_subject')
            
        Returns:
            list: List of requirements related to the role
        """
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
        
        # First get all mentions of the role
        self.cursor.execute("""
            SELECT article_id, text
            FROM key_actors
            WHERE actor_type = ?
        """, (role,))
        
        article_ids = set()
        for row in self.cursor.fetchall():
            article_ids.add(row[0])
        
        # Get requirements from those articles
        requirements = []
        for article_id in article_ids:
            self.cursor.execute("""
                SELECT a.number, a.title, r.text, r.is_obligation, r.is_right, r.is_time_requirement
                FROM requirements r
                JOIN articles a ON r.article_id = a.id
                WHERE r.article_id = ?
            """, (article_id,))
            
            for row in self.cursor.fetchall():
                article_num, article_title, req_text, is_obligation, is_right, is_time_requirement = row
                
                # Check if the requirement actually mentions this role
                if role.replace('_', ' ') in req_text.lower():
                    requirements.append({
                        'article': article_num,
                        'article_title': article_title,
                        'text': req_text,
                        'is_obligation': bool(is_obligation),
                        'is_right': bool(is_right),
                        'is_time_requirement': bool(is_time_requirement)
                    })
        
        return requirements

    def generate_privacy_policy_template(self):
        """
        Generate a template for a GDPR-compliant privacy policy
        
        Returns:
            str: Markdown-formatted privacy policy template
        """
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
        
        # Get policy sections
        self.cursor.execute("""
            SELECT section_name, description, related_articles, required_information
            FROM privacy_policy_sections
            ORDER BY id
        """)
        
        sections = self.cursor.fetchall()
        
        # Generate template
        template = "# Privacy Policy\n\n"
        template += "_Last updated: [DATE]_\n\n"
        template += "## Introduction\n\n"
        template += "[Company Name] is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you [describe service/product/website].\n\n"
        template += "Please read this Privacy Policy carefully. If you do not agree with the terms of this Privacy Policy, please do not access our services.\n\n"
        
        # Add each required section
        for section_name, description, related_articles, required_information in sections:
            template += f"## {section_name}\n\n"
            template += f"_{description}_\n\n"
            template += f"[Explain {section_name.lower()} - Required by GDPR Articles {related_articles}]\n\n"
            template += f"This section should include: {required_information}\n\n"
        
        template += "## Changes to This Privacy Policy\n\n"
        template += "We may update our Privacy Policy from time to time. We will notify you of any changes by posting the new Privacy Policy on this page and updating the 'Last updated' date.\n\n"
        
        return template

    def export_to_json(self, output_path="gdpr_structured.json"):
        """
        Export the entire structured GDPR content to a JSON file
        
        Args:
            output_path (str): Path to save the JSON file
            
        Returns:
            bool: Success status
        """
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
        
        export_data = {
            "metadata": {
                "title": "General Data Protection Regulation (GDPR)",
                "exported_date": datetime.now().isoformat()
            },
            "chapters": [],
            "articles": [],
            "recitals": [],
            "definitions": [],
            "key_actors": {},
            "time_requirements": []
        }
        
        # Export chapters
        self.cursor.execute("SELECT number, title FROM chapters ORDER BY id")
        for row in self.cursor.fetchall():
            number, title = row
            export_data["chapters"].append({
                "number": number,
                "title": title
            })
        
        # Export recitals
        self.cursor.execute("SELECT number, content FROM recitals ORDER BY number")
        for row in self.cursor.fetchall():
            number, content = row
            export_data["recitals"].append({
                "number": number,
                "content": content
            })
        
        # Export articles
        self.cursor.execute("""
            SELECT a.id, a.number, a.title, a.content, c.number, c.title, s.number, s.title
            FROM articles a
            LEFT JOIN chapters c ON a.chapter_id = c.id
            LEFT JOIN sections s ON a.section_id = s.id
            ORDER BY a.number
        """)
        
        article_rows = self.cursor.fetchall()
        for row in article_rows:
            article_id, article_num, article_title, article_content, chapter_num, chapter_title, section_num, section_title = row
            
            article = {
                "number": article_num,
                "title": article_title,
                "content": article_content,
                "chapter": {"number": chapter_num, "title": chapter_title} if chapter_num else None,
                "section": {"number": section_num, "title": section_title} if section_num else None,
                "paragraphs": [],
                "requirements": []
            }
            
            # Get paragraphs
            self.cursor.execute("""
                SELECT id, number, text
                FROM paragraphs
                WHERE article_id = ?
                ORDER BY number
            """, (article_id,))
            
            for para_row in self.cursor.fetchall():
                para_id, para_num, para_text = para_row
                
                paragraph = {
                    "number": para_num,
                    "text": para_text,
                    "subparagraphs": []
                }
                
                # Get subparagraphs
                self.cursor.execute("""
                    SELECT id, letter, text
                    FROM subparagraphs
                    WHERE paragraph_id = ?
                    ORDER BY letter
                """, (para_id,))
                
                for subpara_row in self.cursor.fetchall():
                    subpara_id, subpara_letter, subpara_text = subpara_row
                    
                    subparagraph = {
                        "letter": subpara_letter,
                        "text": subpara_text,
                        "subsubparagraphs": []
                    }
                    
                    # Get subsubparagraphs
                    self.cursor.execute("""
                        SELECT number, text
                        FROM subsubparagraphs
                        WHERE subparagraph_id = ?
                        ORDER BY number
                    """, (subpara_id,))
                    
                    for subsubpara_row in self.cursor.fetchall():
                        subsubpara_num, subsubpara_text = subsubpara_row
                        
                        subsubparagraph = {
                            "number": subsubpara_num,
                            "text": subsubpara_text
                        }
                        
                        subparagraph["subsubparagraphs"].append(subsubparagraph)
                    
                    paragraph["subparagraphs"].append(subparagraph)
                
                article["paragraphs"].append(paragraph)
            
            # Get requirements
            self.cursor.execute("""
                SELECT text, is_obligation, is_right, is_time_requirement
                FROM requirements
                WHERE article_id = ?
            """, (article_id,))
            
            for req_row in self.cursor.fetchall():
                req_text, is_obligation, is_right, is_time_requirement = req_row
                
                requirement = {
                    "text": req_text,
                    "is_obligation": bool(is_obligation),
                    "is_right": bool(is_right),
                    "is_time_requirement": bool(is_time_requirement)
                }
                
                article["requirements"].append(requirement)
            
            export_data["articles"].append(article)
        
        # Export definitions
        self.cursor.execute("""
            SELECT d.term, d.definition, a.number
            FROM definitions d
            JOIN articles a ON d.article_id = a.id
            ORDER BY d.term
        """)
        
        for row in self.cursor.fetchall():
            term, definition, article_num = row
            
            export_data["definitions"].append({
                "term": term,
                "definition": definition,
                "article": article_num
            })
        
        # Export key actors
        self.cursor.execute("""
            SELECT DISTINCT actor_type
            FROM key_actors
        """)
        
        actor_types = [row[0] for row in self.cursor.fetchall()]
        
        for actor_type in actor_types:
            self.cursor.execute("""
                SELECT a.number, k.text
                FROM key_actors k
                JOIN articles a ON k.article_id = a.id
                WHERE k.actor_type = ?
                ORDER BY a.number
            """, (actor_type,))
            
            export_data["key_actors"][actor_type] = []
            
            for row in self.cursor.fetchall():
                article_num, text = row
                
                export_data["key_actors"][actor_type].append({
                    "article": article_num,
                    "text": text
                })
        
        # Export time requirements
        self.cursor.execute("""
            SELECT a.number, t.text
            FROM time_requirements t
            JOIN articles a ON t.article_id = a.id
            ORDER BY a.number
        """)
        
        for row in self.cursor.fetchall():
            article_num, text = row
            
            export_data["time_requirements"].append({
                "article": article_num,
                "text": text
            })
        
        # Write to file
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully exported GDPR structured data to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting to JSON: {str(e)}")
            return False

    def close(self):
        """
        Close database connection and clean up resources
        """
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

def main():
    """
    Main function to execute the GDPR parser
    """
    try:
        # Path to the GDPR PDF file
        pdf_path = "gdpr.pdf"
        
        # Initialize parser
        parser = GDPRParser(pdf_path)
        
        # Parse document and load into database
        success = parser.parse_and_load()
        
        if success:
            # Export to JSON
            parser.export_to_json()
            
            # Generate privacy policy template
            policy_template = parser.generate_privacy_policy_template()
            
            with open("privacy_policy_template.md", "w", encoding="utf-8") as f:
                f.write(policy_template)
            
            print("GDPR parsing completed successfully")
            print("Generated files:")
            print("- gdpr_knowledge_base.db: SQLite database with structured GDPR content")
            print("- gdpr_structured.json: JSON export of the structured content")
            print("- privacy_policy_template.md: Template for GDPR-compliant privacy policy")
        else:
            print("GDPR parsing failed. See logs for details.")
        
        # Close resources
        parser.close()
        
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}", exc_info=True)
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()