from typing import List, Dict

def build_improved_reproduce_prompt(issue_desc: str, repo_info: str = None) -> str:
    """Build reproduction prompt with framework detection"""
    
    # Detect framework
    is_django = 'django' in issue_desc.lower() or (repo_info and 'django' in repo_info.lower())
    is_flask = 'flask' in issue_desc.lower()
    
    base_prompt = f"""You are a software testing expert. Write a Python script that reproduces the bug.

Issue Description:
{issue_desc}

Requirements:
1. Write a complete, runnable Python script
2. The script should clearly demonstrate the bug
3. Include comments explaining expected vs actual behavior
4. Use assertions or print statements to show the bug
5. Make the script self-contained
"""

    if is_django:
        base_prompt += """
6. **IMPORTANT**: For Django projects, include this setup at the beginning:

```python
import os
import django
from django.conf import settings

# Configure Django settings FIRST
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        SECRET_KEY='test-secret-key',
    )
    django.setup()

# Import Django models/components AFTER django.setup()
from django.db import models
from django.db.models.expressions import RawSQL  # Note: RawSQL is in expressions module, not db.models
```

Then proceed with your test code using these imports.
"""
    
    elif is_flask:
        base_prompt += """
6. **IMPORTANT**: For Flask projects, create a test app context:

```python
from flask import Flask
app = Flask(__name__)
app.config['TESTING'] = True
with app.app_context():
    # Your test code here
```
"""
    
    base_prompt += """
Output Format:
Provide ONLY the Python code wrapped in ```python blocks. No explanations outside the code block.
"""
    
    if repo_info:
        base_prompt += f"\n\nRepository Context:\n{repo_info[:500]}\n"
    
    return base_prompt


def build_improved_fix_prompt(
    issue: str,
    file_content: str,
    file_path: str,
    error_trace: str = None,
    previous_attempts: List[Dict] = None,
    relevant_sections: List[str] = None
) -> str:
    """Build fix prompt with context from previous attempts"""
    
    prompt = f"""You are an expert software engineer fixing a bug.

Issue Description:
{issue}

File to fix: {file_path}
"""
    
    if relevant_sections:
        prompt += f"\n**Note**: This file has been filtered to show only relevant sections: {', '.join(relevant_sections)}\n"
    
    prompt += f"""
Current File Content:
```python
{file_content}
```
"""
    
    if error_trace:
        prompt += f"""
Error Trace from Reproduction:
```
{error_trace[-2000:]}  # Last 2000 chars
```
"""
    
    if previous_attempts:
        prompt += "\n**Previous Fix Attempts (all failed):**\n"
        for i, attempt in enumerate(previous_attempts[-2:], 1):  # Show last 2 attempts
            prompt += f"""
Attempt {i}:
- Error: {attempt.get('error', 'Unknown')[:200]}
- What was tried: {attempt.get('description', 'N/A')[:200]}
"""
    
    prompt += """
Your Task:
1. Identify the root cause of the bug
2. Provide the COMPLETE fixed version of the file (or section if filtered)
3. Explain your changes briefly

**CRITICAL RULES:**
- Provide the ENTIRE file content with your fixes applied
- Do NOT truncate or summarize the code
- Maintain all imports, function signatures, and structure
- Only modify the specific lines that fix the bug
- Keep all other code exactly as-is

Output Format:
First, briefly explain what you're changing (2-3 sentences).

Then provide the complete fixed code in a ```python block.
"""
    
    return prompt


def build_improved_locate_prompt(
    issue: str,
    repo_structure: str,
    error_trace: str = None
) -> str:
    """Build file location prompt with better context"""
    
    prompt = f"""You are a debugging expert analyzing a software bug.

Issue Description:
{issue}
"""
    
    if error_trace:
        import re
        trace_files = re.findall(r'File "([^"]+\.py)"', error_trace)
        if trace_files:
            prompt += f"""
Files mentioned in error trace:
{chr(10).join(set(trace_files))}
"""
    
    prompt += f"""
Repository Structure (sample):
{repo_structure}

Your Task:
Identify the TOP 3 source code files that most likely need modification to fix this bug.

Consider:
1. Files explicitly mentioned in the issue or error trace
2. Files that match the component/module mentioned
3. Avoid test files unless the issue is about tests

Ranking Priority:
- HIGH: Files mentioned in issue/error
- MEDIUM: Files in related modules
- LOW: Generic utility files

Output Format:
List EXACTLY 3 file paths, one per line, in order of relevance:
/path/to/most_relevant.py
/path/to/second_relevant.py
/path/to/third_relevant.py

No explanations, just paths.
"""
    
    return prompt