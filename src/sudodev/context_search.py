import ast
import re
from typing import List, Dict, Tuple, Optional
from sudodev.utils.logger import setup_logger

logger = setup_logger(__name__)

class ContextSearch:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def extract_keywords_from_issue(self, issue_text: str) -> Dict[str, List[str]]:
        prompt = f"""Analyze this GitHub issue and extract relevant search keywords.

Issue:
{issue_text[:2000]}

Extract and categorize:
1. Function names mentioned or related to the issue
2. Class names mentioned or related to the issue
3. Variable names or attributes mentioned
4. Error types or exception names
5. Key concepts or technical terms

Respond in this exact format:
FUNCTIONS: func1, func2, func3
CLASSES: Class1, Class2
VARIABLES: var1, var2
ERRORS: ErrorType1, ErrorType2
CONCEPTS: concept1, concept2
"""
        response = self.llm.get_completion(
            system_prompt="You are a code analysis expert.",
            user_prompt=prompt,
            temperature=0.2,
            max_tokens=500
        )

        keywords = {
            'functions': [],
            'classes': [],
            'variables': [],
            'errors': [],
            'concepts': []
        }

        for line in response.split('\n'):
            line = line.strip()
            if line.startswith('FUNCTIONS:'):
                keywords['functions'] = [k.strip() for k in line.replace('FUNCTIONS:', '').split(',') if k.strip()]
            elif line.startswith('CLASSES:'):
                keywords['classes'] = [k.strip() for k in line.replace('CLASSES:', '').split(',') if k.strip()]
            elif line.startswith('VARIABLES:'):
                keywords['variables'] = [k.strip() for k in line.replace('VARIABLES:', '').split(',') if k.strip()]
            elif line.startswith('ERRORS:'):
                keywords['errors'] = [k.strip() for k in line.replace('ERRORS:', '').split(',') if k.strip()]
            elif line.startswith('CONCEPTS:'):
                keywords['concepts'] = [k.strip() for k in line.replace('CONCEPTS:', '').split(',') if k.strip()]
        
        logger.info(f"Extracted keywords: {keywords}")
        return keywords
    
    def parse_python_file(self, file_content: str) -> Dict[str, any]:
        try:
            tree = ast.parse(file_content)

            structure = {
                'classes': [],
                'functions': [],
                'imports': []
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                    structure['classes'].append({
                        'name': node.name,
                        'lineno': node.lineno,
                        'methods': methods,
                        'docstring': ast.get_docstring(node)
                    })
                elif isinstance(node, ast.FunctionDef):
                    if node.col_offset == 0:
                        structure['functions'].append({
                            'name': node.name,
                            'lineno': node.lineno,
                            'docstring': ast.get_docstring(node)
                        })
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    structure['imports'].append(node.lineno)
            
            return structure
        except SyntaxError as e:
            logger.warning(f"Could not parse file: {e}")
            return None
        
    def extract_relevant_sections(
        self, 
        file_content: str, 
        keywords: Dict[str, List[str]],
        max_chars: int = 20000
    ) -> Tuple[str, List[str]]:
        structure = self.parse_python_file(file_content)
        logger.info(f"Parsed structure: {len(structure.get('classes', []) if structure else [])} classes, {len(structure.get('functions', []) if structure else [])} functions")
        if not structure:
            logger.warning("AST parsing failed, using fallback")
        
        lines = file_content.split('\n')
        relevant_sections = []
        included_lines = set()
        sections_info = []

        scored_items = []

        for cls in structure['classes']:
            score = self._score_relevance(
                cls['name'], 
                cls['methods'], 
                cls.get('docstring', ''),
                keywords
            )
            if score > 0:
                scored_items.append({
                    'type': 'class',
                    'name': cls['name'],
                    'lineno': cls['lineno'],
                    'score': score
                })
        
        for func in structure['functions']:
            score = self._score_relevance(
                func['name'], 
                [], 
                func.get('docstring', ''),
                keywords
            )
            if score > 0:
                scored_items.append({
                    'type': 'function',
                    'name': func['name'],
                    'lineno': func['lineno'],
                    'score': score
                })

        scored_items.sort(key=lambda x: x['score'], reverse=True)
        logger.info(f"Scored {len(scored_items)} items, top scores: {[item['score'] for item in scored_items[:5]]}")
        

        current_chars = 0

        for item in scored_items:
            if current_chars >= max_chars:
                break
            
            section, section_lines = self._extract_code_block(lines, item['lineno'])
            section_chars = len(section)

            if current_chars + section_chars <= max_chars:
                relevant_sections.append(section)
                included_lines.update(section_lines)
                sections_info.append(f"{item['type']} {item['name']} (score: {item['score']})")
                current_chars += section_chars
            
            if not relevant_sections:
                relevant_sections.append('\n'.join(lines[:200]))
                sections_info.append("File header (no specific matches)")

            result = "\n\n# ===== RELEVANT SECTIONS =====\n\n".join(relevant_sections)
        
            logger.info(f"Extracted {len(relevant_sections)} sections ({current_chars} chars)")
            return result, sections_info
    
    def _score_relevance(
        self,
        name: str, 
        methods: List[str], 
        docstring: str,
        keywords: Dict[str, List[str]]
    ) -> int:
        score = 0
        name_lower = name.lower()
        docstring_lower = (docstring or'').lower()

        for keyword in keywords.get('functions', []) + keywords.get('classes', []):
            if keyword.lower() in name_lower:
                score += 10

        for method in methods:
            for keyword in keywords.get('functions', []):
                if keyword.lower() in method.lower():
                    score += 5
        
        for keyword_list in keywords.values():
            for keyword in keyword_list:
                if keyword.lower() in docstring_lower:
                    score += 2
        
        for error in keywords.get('errors', []):
            if error.lower() in name_lower or error.lower() in docstring_lower:
                score += 8
        
        return score
    
    def _extract_code_block(self, lines: List[str], start_lineno: int) -> Tuple[str, set]:
        if start_lineno > len(lines):
            return "", set()
        
        start_idx = start_lineno - 1
        base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())

        end_idx = start_idx + 1
        while end_idx < len(lines):
            line = lines[end_idx]
            if line.strip(): 
                indent = len(line) - len(line.lstrip())
                if indent <= base_indent:
                    break
            end_idx += 1
        
        section_lines = set(range(start_idx, end_idx))
        section_text = '\n'.join(lines[start_idx:end_idx])
        
        return section_text, section_lines
    
    def search_files_by_relevance(
        self,
        issue_text: str,
        file_tree: str,
        max_files: int = 5
    ) -> List[str]:
        """Use LLM to rank files by relevance"""
        
        prompt = f"""Given this GitHub issue, identify which files are most likely to need modification.

Issue:
{issue_text[:1500]}

Available files:
{file_tree[:3000]}

Rank the TOP {max_files} files most likely to contain the bug.
Consider:
1. Files explicitly mentioned in the issue
2. Files related to the error type/component
3. Common patterns (e.g., compiler issues → compiler.py)

Respond with ONLY the file paths, one per line, ranked from most to least relevant.
"""
        
        response = self.llm.get_completion(
            system_prompt="You are a software debugging expert.",
            user_prompt=prompt,
            temperature=0.2,
            max_tokens=500
        )
    
        files = []
        for line in response.split('\n'):
            line = line.strip()
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            line = re.sub(r'^[-\*]\s*', '', line)
            line = line.strip('`"\'')
            
            if line and '.py' in line and not line.startswith('#'):
                files.append(line)
        
        return files[:max_files]