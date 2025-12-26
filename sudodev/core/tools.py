import re
import difflib 
import ast
from typing import List, Tuple, Dict, Optional

def extract_python_code(text: str) -> str:
    pattern = r"```(?:python3|python|py)\b\s*(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

    if matches:
        return matches[0].strip()
    
    pattern = r"```\s*(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)

    if matches:
        return matches[0].strip()
    
    return text.strip()

def extract_bash_commands(text: str) -> List[str]:
    commands = []
    pattern = r"```(?:bash|sh)\s*(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    for match in matches:
        lines = match.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                commands.append(line)

    if not commands:
        lines = text.split('\n')
        for line in lines:
            if line.startswith('$ '):
                line = line[2:]
            if any(line.startswith(cmd) for cmd in ['python', 'pytest', 'django-admin', './manage.py', 'bash']):
                commands.append(line)
    return commands

def extract_file_paths(text: str) -> List[str]:
    patterns = [
        r'`([a-zA-Z0-9_/\-\.]+\.py)`',  # Paths in backticks
        r'([a-zA-Z0-9_/\-\.]+\.py)\b',   # Standalone .py files
        r'"([a-zA-Z0-9_/\-\.]+\.py)"',   # Paths in quotes
    ]

    paths = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        paths.extend(matches)

    seen = set()
    unique_paths = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)
    
    return unique_paths

def build_reproduce_prompt(issue_desc: str, hints: str = None) -> str:
    prompt = f"""You are a software testing expert. Your task is to write a Python script that reproduces the bug described below.

Issue Description:
{issue_desc}

Requirements:
1. Write a complete, runnable Python script
2. The script should clearly demonstrate the bug
3. Include comments explaining what should happen vs what actually happens
4. Use assertions to verify the bug exists
5. Make the script self-contained (import all necessary modules)

Output Format:
Provide only the Python code wrapped in ```python blocks, nothing else.
"""
    if hints:
        prompt += f"\nHints:\n{hints}\n"

    return prompt

def build_fix_prompt(issue: str, file_content: str, file_path: str, error_trace: str = None) -> str:
    prompt = f"""You are an expert software engineer. Fix the bug in the following code.
Issue Description:
{issue}

File to fix: {file_path}

```python
{file_content}
```
"""
    if error_trace:
        prompt += f"\n**Error Trace:**\n```\n{error_trace}\n```\n"

    prompt += """
Your Task:
1. Identify the root cause of the bug
2. Provide the COMPLETE fixed version of the file
3. Explain what you changed and why

Output Format:
First explain your changes briefly, then provide the complete fixed code in a ```python block.
"""

    return prompt

def build_locate_files_prompt(issue: str, repo_structure: str = None) -> str:
    prompt = f"""You are analyzing a software bug report. Identify which source files need to be modified to fix this issue.
Issue Description:
{issue}
"""
    if repo_structure:
        prompt += f"\n**Repository Structure:**\n```\n{repo_structure}\n```\n"

    prompt += """
Your Task:
List the file paths that likely need modification to fix this issue.

Output Format:
Provide a list of file paths, one per line, like:
path/to/file1.py
path/to/file2.py
"""
    return prompt

def build_verification_prompt(issue: str, fix_applied: str, test_output: str) -> str:
    prompt = f"""You are verifying whether a bug fix successfully resolves an issue.

Original Issue:
{issue}

Fix Applied:
{fix_applied}

Test Output:
```
{test_output}
```

Your Task:
Analyze whether the fix successfully resolves the issue. Consider:
1. Does the test output show the bug is fixed?
2. Are there any new errors introduced?
3. Is the behavior now correct?

Output Format:
Respond with:
VERDICT: [FIXED/NOT_FIXED/PARTIAL]
REASONING: [Your explanation]
"""
    return prompt

def create_diff_patch(original: str, modified: str, filepath: str) -> str:
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
        lineterm='\n'
    )

    return ''.join(diff)

def parse_patch(patch_text: str) -> Dict[str, any]:
    lines = patch_text.split('\n')
    result = {
        'filepath': None,
        'additions': [],
        'deletions': []
    }

    current_hunk = None

    for line in lines:
        if line.startswith('---') or line.startswith('+++'):
            match = re.search(r'[ab]/(.*?)(?:\s|$)', line)
            if match:
                result['filepath'] = match.group(1)
        elif line.startswith('@@'):
            if current_hunk:
                result['hunks'].append(current_hunk)

            header_match = re.search(
                r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line
            )

            current_hunk = {
                'header': line,
                'old_start': int(header_match.group(1)),
                'old_count': int(header_match.group(2) or 1),
                'new_start': int(header_match.group(3)),
                'new_count': int(header_match.group(4) or 1),
                'lines': []
            }


        elif line.startswith('+') and not line.startswith('+++'):
            result['additions'].append(line[1:])
            if current_hunk:
                current_hunk['lines'].append(line)

        elif line.startswith('-') and not line.startswith('---'):
            result['deletions'].append(line[1:])
            if current_hunk:
                current_hunk['lines'].append(line)
        
        elif line.startswith(' '):
            if current_hunk:
                current_hunk['lines'].append(line)

        if current_hunk:
            result['hunk'].append(current_hunk)

    return result

def validate_python_code(code: str) -> Tuple[bool, str]:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} at line {e.lineno}, offset {e.offset}"
    except Exception as e:
        return False, f"Parsing Error: {str(e)}"

def extract_error_messages(output: str) -> List[Dict[str, str]]:
    errors = []
    exception_pattern = r'(\w+Error|Exception): (.+?)(?=\n|$)'
    matches = re.findall(exception_pattern, output)

    for error_type, message in matches:
        errors.append({
            'type': error_type,
            'message': message.strip()
        })
    
    assertion_pattern = r'AssertionError: (.+?)(?=\n|$)'
    assertion_matches = re.findall(assertion_pattern, output)
    
    for message in assertion_matches:
        errors.append({
            'type': 'AssertionError',
            'message': message.strip()
        })
    
    return errors

def format_test_results(results: Dict[str, any]) -> str:
    output = []
    output.append("test results")

    if 'total_tests' in results:
        output.append(f"  total tests: {results['total_tests']}")
    
    if 'passed' in results:
        output.append(f"Passed: {results['passed']}")
    
    if 'failed' in results:
        output.append(f"Failed: {results['failed']}")
    
    if 'errors' in results and results['errors']:
        output.append("\nErrors:")
        for i, error in enumerate(results['errors'], 1):
            output.append(f"  {i}. {error.get('type', 'Unknown')}: {error.get('message', '')}")
    
    return "\n".join(output)

import re

def clean_llm_response(text: str) -> str:
    
    code_block_pattern = re.compile(
        r"```(?:\w+)?\n([\s\S]*?)```",
        re.MULTILINE
    )
    match = code_block_pattern.search(text)
    if match:
        return match.group(1).strip()

    prefix_pattern = re.compile(
        r"""^\s*(
            here[’']?s the code[:!]? |
            here is the code[:!]? |
            sure[,!]? here[’']?s |
            sure[,!]? |
            certainly[,!]? |
            below is the code[:!]?
        )\s*""",
        re.IGNORECASE | re.VERBOSE
    )

    text = re.sub(prefix_pattern, "", text)

    return text.strip()


def extract_code_from_response(response: str, language: str = "python") -> str:
    response = clean_llm_response(response)

    if language.lower() == "python":
        return extract_python_code(response)
    elif language.lower() in ["bash", "sh"]:
        commands = extract_bash_commands(response)
        return '\n'.join(commands)
    else:
        pattern = r"```.*?\s*(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            return matches[0].strip()
    
    return response.strip()