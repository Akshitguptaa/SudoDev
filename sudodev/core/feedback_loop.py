from typing import List, Dict, Tuple, Optional
import time
from sudodev.core.utils.logger import log_step, log_success, log_error, setup_logger
logger = setup_logger(__name__)

class FeedbackLoop:
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
        self.attempts_history = []

    def add_attempt(
        self,
        attempt_num: int,
        file_path: str,
        code_applied: str,
        error_output: str,
        success: bool
    ):
        """Record a fix attempt"""
        self.attempts_history.append({
            'attempt': attempt_num,
            'file_path': file_path,
            'code_applied': code_applied[:500],
            'error_output': error_output,
            'success': success,
            'timestamp': time.time()
        })

    def should_retry(self, current_attempt: int) -> bool:
        return current_attempt < self.max_attempts
    
    def analyze_errors(self, error_output: str) -> Dict[str, any]:
        """Analyze error output to guide next fix attempt"""
        analysis = {
            'error_type': None,
            'error_message': None,
            'failed_line': None,
            'suggestions': []
        }
        
        error_patterns = [
            (r'(\w+Error): (.+)', 'exception'),
            (r'AssertionError: (.+)', 'assertion'),
            (r'FAILED (.+)', 'test_failure'),
        ]
        
        for pattern, error_category in error_patterns:
            import re
            match = re.search(pattern, error_output)
            if match:
                if error_category == 'exception':
                    analysis['error_type'] = match.group(1)
                    analysis['error_message'] = match.group(2)
                elif error_category == 'assertion':
                    analysis['error_type'] = 'AssertionError'
                    analysis['error_message'] = match.group(1)
                elif error_category == 'test_failure':
                    analysis['error_type'] = 'TestFailure'
                    analysis['error_message'] = match.group(1)
                break
        
        line_match = re.search(r'line (\d+)', error_output)
        if line_match:
            analysis['failed_line'] = int(line_match.group(1))

        if analysis['error_type']:
            analysis['suggestions'] = self._generate_suggestions(analysis)
        
        return analysis
    
    def _generate_suggestions(self, analysis: Dict) -> List[str]:
        """Generate suggestions based on error analysis"""
        suggestions = []
        error_type = analysis.get('error_type', '')
        
        if error_type == 'NameError':
            suggestions.append("Check for undefined variables or missing imports")
        elif error_type == 'AttributeError':
            suggestions.append("Verify object has the expected attributes/methods")
        elif error_type == 'TypeError':
            suggestions.append("Check function arguments and type compatibility")
        elif error_type == 'ImportError' or error_type == 'ModuleNotFoundError':
            suggestions.append("Verify import paths and module availability")
        elif error_type == 'SyntaxError':
            suggestions.append("Review code syntax and indentation")
        elif error_type == 'AssertionError':
            suggestions.append("The fix didn't achieve expected behavior - review logic")
        elif 'Django' in analysis.get('error_message', ''):
            suggestions.append("Ensure Django settings are properly configured")

        if len(self.attempts_history) > 1:
            last_error = self.attempts_history[-1].get('error_output', '')
            if analysis['error_type'] in last_error:
                suggestions.append("CRITICAL: Same error repeating - try a different approach")
        
        return suggestions
    
    def build_retry_prompt(
        self,
        original_issue: str,
        file_content: str,
        file_path: str,
        current_error: str
    ) -> str:
        """Build a prompt for retry attempt with feedback"""
        
        analysis = self.analyze_errors(current_error)
        
        prompt = f"""You are debugging a fix that FAILED. Learn from the error and try a different approach.

Original Issue:
{original_issue[:1000]}

File: {file_path}

Current Code (that failed):
```python
{file_content[:10000]}
```

VERIFICATION FAILED with this error:
```
{current_error[-1500:]}
```

Error Analysis:
- Type: {analysis['error_type'] or 'Unknown'}
- Message: {analysis['error_message'] or 'See above'}
"""
        
        if analysis['failed_line']:
            prompt += f"- Failed at line: {analysis['failed_line']}\n"
        
        if analysis['suggestions']:
            prompt += "\nSuggestions:\n"
            for suggestion in analysis['suggestions']:
                prompt += f"- {suggestion}\n"
        
        if len(self.attempts_history) > 0:
            prompt += f"\n**Previous Attempts**: {len(self.attempts_history)} failed\n"
            for i, attempt in enumerate(self.attempts_history[-2:], 1):
                brief_error = attempt['error_output'][:200].split('\n')[-1]
                prompt += f"  Attempt {attempt['attempt']}: {brief_error}\n"
        
        prompt += """
Your Task:
1. Carefully review the error and understand why the previous fix failed
2. Think about what needs to change differently
3. Provide a COMPLETE fixed version of the file

**IMPORTANT:**
- Do NOT repeat the same fix that just failed
- Try a fundamentally different approach if needed
- Ensure all syntax is correct
- Provide the ENTIRE file content

Output Format:
First explain what you're changing differently this time (3-4 sentences).

Then provide the complete fixed code in a ```python block.
"""
        
        return prompt
    
    def get_summary(self) -> str:
        """Get a summary of all attempts"""
        if not self.attempts_history:
            return "No attempts made yet"
        
        summary = f"Total attempts: {len(self.attempts_history)}\n"
        for attempt in self.attempts_history:
            status = "✓" if attempt['success'] else "✗"
            summary += f"{status} Attempt {attempt['attempt']}: {attempt['file_path']}\n"
        
        return summary