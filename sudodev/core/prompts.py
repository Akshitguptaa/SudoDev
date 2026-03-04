from typing import List, Dict, Optional

from sudodev.core.framework_utils import get_framework_from_instance_id, detect_repo_language


ENVIRONMENT_CONSTRAINTS = """
IMPORTANT ENVIRONMENT CONSTRAINTS:
- You are running in a HEADLESS Docker container (no display, no GUI)
- Do NOT use: tkinter, pygame, matplotlib.pyplot.show(), any GUI library
- Do NOT open browser windows, pop-ups, or graphical interfaces
- If you need to verify visual/CSS changes, read the source files and check values programmatically
- For web/frontend projects, verify by checking file contents, CSS values, or config programmatically
- Keep the script minimal and focused on the core logic bug
"""


def detect_framework(issue_desc: str, repo_info: str = None, instance_id: str = None) -> str:
    if instance_id:
        return get_framework_from_instance_id(instance_id)
        
    issue_lower = issue_desc.lower()
    repo_lower = (repo_info or '').lower()
    
    hints = {
        'django': 'django',
        'flask': 'flask',
        'sympy': 'sympy',
        'sphinx': 'sphinx',
        'matplotlib': 'pytest',
        'sklearn': 'pytest',
        'scikit': 'pytest',
        'pytest': 'pytest',
        'react': 'node',
        'vue': 'node',
        'angular': 'node',
        'next.js': 'node',
        'nextjs': 'node',
        'webpack': 'node',
        'vite': 'node',
        'typescript': 'node',
        'npm': 'node',
    }

    for keyword, framework in hints.items():
        if keyword in issue_lower or keyword in repo_lower:
            return framework

    if any(ext in repo_lower for ext in ['.ts', '.tsx', '.jsx', 'package.json', 'tsconfig']):
        return 'node'

    if 'test_' in issue_lower or 'pytest.ini' in repo_lower:
        return 'pytest'

    return 'generic'


FRAMEWORK_TEMPLATES = {
    'django': '''For Django projects, set up the environment first:

```python
import os
import sys
import django
from django.conf import settings

sys.path.append(os.getcwd())

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        INSTALLED_APPS=['django.contrib.contenttypes', 'django.contrib.auth', 'tests'],
        SECRET_KEY='test',
        USE_TZ=True,
    )
    try:
        django.setup()
    except Exception as e:
        print(f"Setup warning: {e}")

from django.db import models, connection

print("Testing bug...")
```

''',

    'flask': '''For Flask projects:

```python
from flask import Flask

app = Flask(__name__)
app.config['TESTING'] = True

with app.app_context():
    print("Testing bug...")
```

''',

    'pytest': '''For pytest-based projects (sklearn, matplotlib, astropy, etc.):

```python
import sys

def test_bug():
    print("Testing bug...")
    result = function_with_bug()
    assert result == expected, f"Bug: got {result}, expected {expected}"

if __name__ == '__main__':
    test_bug()
    print("Test passed - bug NOT present")
```

''',

    'sympy': '''For SymPy projects:

```python
from sympy import *

print("Testing bug...")
```

''',

    'sphinx': '''For Sphinx documentation projects:

```python
import sys
import os

print("Testing bug...")
```

''',

    'node': '''For JavaScript/TypeScript/Node.js projects:

Since this is a JS/TS project, write a Python script that verifies the bug by:
1. Reading the relevant source files and checking for the problematic code
2. Using string matching or regex to verify the bug exists in the source
3. Do NOT try to run JavaScript directly - verify by analyzing file contents

```python
import os
import re

# Read the relevant source file
with open("path/to/relevant/file.ts", "r") as f:
    content = f.read()

# Check for the problematic pattern
if "buggy_pattern" in content:
    print("Bug confirmed: found problematic pattern")
    raise AssertionError("Bug is present in the source code")
else:
    print("Bug not found - code looks correct")
```

''',

    'generic': '''Create a reproduction script. If this is a code/logic bug, write Python to demonstrate it.
If this is a frontend/CSS/UI bug, verify by reading and analyzing the source files:

```python
import os
import re

# For code bugs: import and test the buggy function
# For UI/CSS bugs: read the file and check for the problematic values

print("Testing bug...")
```

'''
}


def build_improved_reproduce_prompt(issue_desc: str, repo_info: str = None, instance_id: str = None) -> str:
    framework = detect_framework(issue_desc, repo_info, instance_id)

    repo_language = "python"
    if repo_info:
        repo_language = detect_repo_language(repo_info)

    base_prompt = f"""Write a Python script that reproduces/verifies this bug:

{issue_desc}

{ENVIRONMENT_CONSTRAINTS}

The primary language of this repository is: {repo_language}

The script should:
- Clearly demonstrate or verify the bug exists
- Exit with a non-zero code (raise an error or use sys.exit(1)) if the bug is present
- Exit normally (exit code 0) if the bug is NOT present (i.e., it's been fixed)
- Be minimal and self-contained
"""

    if repo_language in ("typescript", "javascript"):
        base_prompt += """
IMPORTANT: This is a TypeScript/JavaScript project. Since we're running Python:
- Do NOT try to import or run JavaScript/TypeScript code directly
- Instead, READ the relevant source files and check for the bug programmatically
- Use Python's file I/O and string/regex matching to verify the bug exists
- Check CSS values, TypeScript types, config settings, etc. by reading the files
- Example: read a .css file and check if a CSS property has the wrong value

"""

    template = FRAMEWORK_TEMPLATES.get(framework, FRAMEWORK_TEMPLATES['generic'])
    base_prompt += template

    base_prompt += """
Return ONLY Python code in a ```python``` block. No explanations outside the code block.
"""

    if repo_info:
        base_prompt += f"\nRepository file structure (sample):\n{repo_info[:800]}\n"

    return base_prompt


def build_improved_fix_prompt(
    issue: str,
    file_content: str,
    file_path: str,
    error_trace: str = None,
    previous_attempts: List[Dict] = None,
    relevant_sections: List[str] = None
) -> str:
    file_ext = file_path.rsplit('.', 1)[-1] if '.' in file_path else 'py'

    lang_map = {
        'py': 'python', 'ts': 'typescript', 'tsx': 'typescript',
        'js': 'javascript', 'jsx': 'javascript',
        'css': 'css', 'scss': 'scss',
        'json': 'json', 'yaml': 'yaml', 'yml': 'yaml',
        'html': 'html', 'md': 'markdown',
    }
    language = lang_map.get(file_ext, file_ext)

    prompt = f"""You are an expert software engineer fixing a bug.

Issue Description:
{issue}

File to fix: {file_path}
"""
    
    if relevant_sections:
        prompt += f"\n**Note**: This file has been filtered to show only relevant sections: {', '.join(relevant_sections)}\n"
    
    prompt += f"""
Current File Content:
```{language}
{file_content}
```
"""
    
    if error_trace:
        prompt += f"""
Error Trace from Reproduction:
```
{error_trace[-2000:]}
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

Then provide the complete fixed code in a ```{language} block.
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
        trace_files = re.findall(r'(?:File "([^"]+)")|([a-zA-Z0-9_/\-\.]+\.\w+)', error_trace)
        if trace_files:
            flat_files = [f[0] or f[1] for f in trace_files if f[0] or f[1]]
            prompt += f"""
Files mentioned in error trace:
{chr(10).join(set(flat_files))}
"""
    
    prompt += f"""
Repository Structure (sample):
{repo_structure}

Your Task:
Identify the TOP 3 source code files that most likely need modification to fix this bug.

Consider:
1. Files explicitly mentioned in the issue description
2. Files that match the component/module mentioned in the issue
3. For CSS/styling issues: look for .css, .scss, or theme files
4. For UI issues: look for component files (.tsx, .jsx, .ts, .js)
5. Avoid test files unless the issue is specifically about tests
6. Avoid generated files, lock files, and config files

Ranking Priority:
- HIGH: Files mentioned in issue or error trace
- MEDIUM: Files in related modules/components
- LOW: Generic utility files

Output Format:
List EXACTLY 3 file paths, one per line, in order of relevance.
No explanations, just paths.
"""
    
    return prompt