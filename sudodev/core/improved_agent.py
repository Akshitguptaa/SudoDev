import re
from sudodev.core.client import LLMClient
from sudodev.runtime.container import Sandbox
from sudodev.core.utils.logger import log_step, log_success, log_error, setup_logger
from sudodev.core.tools import (
    extract_python_code,
    extract_file_paths,
    validate_python_code,
    extract_error_messages,
    create_diff_patch
)

from sudodev.core.context_search import ContextSearch
from sudodev.core.feedback_loop import FeedbackLoop
from sudodev.core.prompts import (
    build_improved_reproduce_prompt,
    build_improved_fix_prompt,
    build_improved_locate_prompt
)
from sudodev.core.framework_utils import (
    get_framework_from_instance_id,
    get_test_command,
    detect_repo_language,
    is_node_project,
    build_find_command,
    ALL_SOURCE_EXTENSIONS
)

logger = setup_logger(__name__)

SYSTEM_PROMPT = """You are SudoDev, a Senior Software Engineer specializing in debugging.
You are running inside a HEADLESS Linux Docker container with the repository checked out at /testbed.

CRITICAL CONSTRAINTS:
- NO display, NO GUI, NO graphical libraries (no tkinter, no pygame, no matplotlib plots)
- Python, Node.js, and common build tools are available
- For frontend/CSS/UI bugs, verify by reading source files programmatically
- All test scripts must run in a headless terminal environment

YOUR PROCESS:
1. Analyze the GitHub issue carefully
2. Create a reproduction script that demonstrates the bug
3. Locate the relevant files using smart search
4. Generate fixes for the actual source files
5. Verify the fix works
"""

class ImprovedAgent:
    def __init__(self, issue_data):
        self.issue = issue_data
        self.llm = LLMClient()

        self.instance_id = issue_data.get('instance_id', 'unknown')
        self.is_swebench = '__' in self.instance_id and not self.instance_id.startswith('github-')

        if self.is_swebench:
            self.sandbox = Sandbox(self.instance_id)
        else:
            self.sandbox = None

        self.context_search = ContextSearch(self.llm)
        self.feedback_loop = FeedbackLoop(max_attempts=3)
        
        self.repro_script = "reproduce_issue.py"
        self.repro_output = ""
        self.target_files = []
        self.keywords = {}
        self.patches = []

        # Detect framework from instance_id
        self.framework = get_framework_from_instance_id(self.instance_id)
        self.repo_language = "python"
        self.file_tree_cache = None
        logger.info(f"Detected framework: {self.framework}")

    def run(self):
        log_step("INIT", f"Starting run for {self.instance_id}")
        try:
            self.sandbox.start()

            self.file_tree_cache = self._get_file_tree(max_files=300)
            self.repo_language = detect_repo_language(self.file_tree_cache)
            logger.info(f"Detected repo language: {self.repo_language}")

            self._extract_keywords()

            if not self._reproduce_bug():
                logger.error("Failed to reproduce the bug. Aborting.")
                return False
            
            if not self._locate_files_smart():
                logger.error("Failed to locate files to fix. Aborting.")
                return False
            
            if not self._generate_fix_with_retry():
                logger.error("Failed to generate fix after multiple attempts. Aborting.")
                return False

            return True
        
        except Exception as e:
            logger.critical(f"Agent failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            logger.info(f"\n{self.feedback_loop.get_summary()}")
            self.sandbox.cleanup()
    
    def get_patch(self) -> str:
        if not self.patches:
            return ""
        return "\n\n".join(self.patches)

    def _extract_keywords(self):
        log_step("ANALYZE", "Extracting keywords from the issue...")

        try:
            self.keywords = self.context_search.extract_keywords_from_issue(
                self.issue['problem_statement']
            )
            log_success(f"Extracted {sum(len(v) for v in self.keywords.values())} keywords")
        except Exception as e:
            logger.warning(f"Keyword extraction failed: {e}")
            self.keywords = {}

    def _get_file_tree(self, max_files=300):
        cmd = build_find_command(max_files=max_files)

        exit_code, output = self.sandbox.run_command(cmd)
        if exit_code == 0:
            files = [line.replace('/testbed/', '') for line in output.strip().split('\n') if line.strip()]
            return '\n'.join(files)
        return "Error getting file list"

    def _resolve_file_paths(self, paths):
        # find the actual full path in the repo
        results = []
        
        for path in paths:
            path = path.replace('/testbed/', '')
            filename = path.split('/')[-1]
            
            exit_code, found = self.sandbox.run_command(
                f"find /testbed -name '{filename}' -type f "
                "! -path '*/node_modules/*' ! -path '*/.git/*' | head -1"
            )
            
            if exit_code == 0 and found.strip():
                actual_path = found.strip().replace('/testbed/', '')
                results.append(actual_path)
                logger.info(f"Found {filename} at {actual_path}")
        
        return results

    def _reproduce_bug(self):
        log_step("REPRODUCE", "Generating reproduction script...")

        file_list = self.file_tree_cache or self._get_file_tree(max_files=150)

        prompt = build_improved_reproduce_prompt(
            issue_desc=self.issue['problem_statement'],
            repo_info=file_list[:1000],
            instance_id=self.instance_id if self.is_swebench else None
        )
        response = self.llm.get_completion(SYSTEM_PROMPT, prompt, temperature=0.3)
        code = extract_python_code(response)

        is_valid, error = validate_python_code(code)
        if not is_valid:
            log_error(f"Generated code has syntax errors: {error}")
            return False
        
        self.sandbox.write_file(self.repro_script, code)
        log_success(f"Wrote {self.repro_script}")

        exit_code, output = self.sandbox.run_command(f"python {self.repro_script}", timeout=30)
        print(f"\nReproduction output:\n{output[:1500]}")

        if exit_code != 0:
            if 'ImportError' in output or 'ModuleNotFoundError' in output:
                log_error("Reproduction script has import errors, retrying...")
                return self._reproduce_bug_retry(file_list)

            log_success("Bug reproduced successfully")
            self.repro_output = output
            return True
        else:
            errors = extract_error_messages(output)
            if errors:
                log_success("Bug confirmed from output")
                self.repro_output = output
                return True

            if 'bug' in output.lower() and ('found' in output.lower() or 'confirmed' in output.lower() or 'present' in output.lower()):
                log_success("Bug confirmed from output text")
                self.repro_output = output
                return True

            log_error("Could not reproduce the bug")
            return False

    def _reproduce_bug_retry(self, file_list: str):
        log_step("REPRODUCE", "Retrying reproduction with stricter constraints...")

        retry_prompt = f"""The previous reproduction script FAILED because it used unsupported imports.

You are in a HEADLESS Docker container. You CANNOT use:
- tkinter, pygame, or any GUI library
- matplotlib.pyplot.show() or any display function
- Any library that requires a display or graphical environment

Rewrite the reproduction script. For frontend/CSS/UI bugs, verify by READING SOURCE FILES:
- Use open() to read the relevant source files
- Use string matching or regex to check if the bug exists in the code
- Do NOT try to render or display anything

Issue:
{self.issue['problem_statement']}

Repository files:
{file_list[:1000]}

Return ONLY Python code in a ```python``` block.
"""

        response = self.llm.get_completion(SYSTEM_PROMPT, retry_prompt, temperature=0.3)
        code = extract_python_code(response)

        is_valid, error = validate_python_code(code)
        if not is_valid:
            log_error(f"Retry code has syntax errors: {error}")
            return False

        self.sandbox.write_file(self.repro_script, code)

        exit_code, output = self.sandbox.run_command(f"python {self.repro_script}", timeout=30)
        print(f"\nRetry reproduction output:\n{output[:1500]}")

        if exit_code != 0 and 'ImportError' not in output and 'ModuleNotFoundError' not in output:
            log_success("Bug reproduced on retry")
            self.repro_output = output
            return True

        if 'bug' in output.lower() and ('found' in output.lower() or 'confirmed' in output.lower()):
            log_success("Bug confirmed from retry output")
            self.repro_output = output
            return True

        log_error("Reproduction retry also failed")
        return False

    def _locate_files_smart(self):
        log_step("LOCATE", "Using smart search to identify files...")
        issue_text = self.issue['problem_statement']

        all_file_paths = self._extract_all_file_paths(issue_text)
        if all_file_paths:
            log_success(f"Found explicit file mentions: {all_file_paths}")
            resolved = self._resolve_file_paths(all_file_paths[:5])
            if resolved:
                self.target_files = resolved[:3]
                return True

        file_tree = self.file_tree_cache or self._get_file_tree(max_files=300)

        try:
            prompt = build_improved_locate_prompt(
                issue=self.issue['problem_statement'],
                repo_structure=file_tree,
                error_trace=self.repro_output
            )

            response = self.llm.get_completion(SYSTEM_PROMPT, prompt, temperature=0.2)
            files = self._extract_all_file_paths(response)

            if files:
                resolved = self._resolve_file_paths(files[:5])
                if resolved:
                    self.target_files = resolved[:3]
                    log_success(f"Smart search identified: {self.target_files}")
                    return True
        except Exception as e:
            logger.error(f"Smart search failed: {e}")

        try:
            files = self.context_search.search_files_by_relevance(
                issue_text,
                file_tree,
                max_files=3
            )
            if files:
                resolved = self._resolve_file_paths(files)
                if resolved:
                    self.target_files = resolved[:3]
                    log_success(f"Context search found: {self.target_files}")
                    return True
        except Exception as e:
            logger.error(f"Context search failed: {e}")

        log_error("Could not identify which files need fixing.")
        return False

    def _extract_all_file_paths(self, text: str):
        patterns = [
            r'`([a-zA-Z0-9_/\-\.]+\.\w{1,5})`',
            r'"([a-zA-Z0-9_/\-\.]+\.\w{1,5})"',
            r'([a-zA-Z0-9_/\-\.]+\.(?:py|ts|tsx|js|jsx|css|scss|html|json|yaml|yml))\b',
        ]

        paths = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            paths.extend(matches)

        seen = set()
        unique = []
        skip_extensions = {'.md', '.txt', '.rst', '.log', '.lock', '.map'}
        for path in paths:
            ext = '.' + path.rsplit('.', 1)[-1] if '.' in path else ''
            if path not in seen and ext not in skip_extensions:
                seen.add(path)
                unique.append(path)

        return unique

    def _generate_fix_with_retry(self):
        """Generate fix with error feedback loop"""
        log_step("FIX", f"Generating fixes with up to {self.feedback_loop.max_attempts} attempts...")

        for attempt in range(1, self.feedback_loop.max_attempts + 1):
            log_step("FIX", f"Attempt {attempt}/{self.feedback_loop.max_attempts}")
            
            fixed_any = False
            for filepath in self.target_files:
                if self._try_fix_file(filepath, attempt):
                    fixed_any = True
                    break 
            
            if not fixed_any:
                log_error(f"Attempt {attempt}: Could not generate any valid fixes")
                continue
            
            success, error_output = self._verify_fix()
            
            if success:
                log_success(f"Fix verified successfully on attempt {attempt}!")
                return True
            else:
                log_error(f"Attempt {attempt} failed verification")
        
        log_error(f"All {self.feedback_loop.max_attempts} attempts exhausted")
        return False
    
    def _try_fix_file(self, filepath: str, attempt: int) -> bool:
        """Try to fix a single file, handling large files with context extraction"""
        log_step("FIX", f"Processing {filepath}")
        
        original_content = self.sandbox.read_file(filepath)
        if not original_content:
            log_error(f"Could not read {filepath}, skipping...")
            return False
        
        file_content = original_content
        relevant_sections = None

        MAX_FILE_CHARS = 25000
        file_ext = filepath.rsplit('.', 1)[-1] if '.' in filepath else 'py'
        is_python = file_ext == 'py'

        if len(original_content) > MAX_FILE_CHARS and is_python:
            log_step("EXTRACT", f"File too large ({len(original_content)} chars), extracting relevant context...")
            
            try:
                file_content, relevant_sections = self.context_search.extract_relevant_sections(
                    original_content,
                    self.keywords,
                    max_chars=MAX_FILE_CHARS
                )
                    
                    # Check if extraction returned empty content
                if not file_content or len(file_content.strip()) < 100:
                    logger.warning("Context extraction returned empty/tiny content, using fallback")
                    file_content = original_content[:MAX_FILE_CHARS]
                    relevant_sections = ["Full file (extraction returned empty content)"]
                
                log_success(f"Extracted {len(relevant_sections)} sections ({len(file_content)} chars)")

            except Exception as e:
                logger.error(f"Context extraction failed: {e}")
                file_content = original_content[:MAX_FILE_CHARS]

        elif len(original_content) > MAX_FILE_CHARS:
            file_content = original_content[:MAX_FILE_CHARS]

        if attempt == 1:
            prompt = build_improved_fix_prompt(
                issue=self.issue['problem_statement'],
                file_content=file_content,
                file_path=filepath,
                error_trace=self.repro_output,
                relevant_sections=relevant_sections
            )
        else:
            last_error = self.feedback_loop.attempts_history[-1]['error_output'] if self.feedback_loop.attempts_history else ""
            prompt = self.feedback_loop.build_retry_prompt(
                original_issue=self.issue['problem_statement'],
                file_content=file_content,
                file_path=filepath,
                current_error=last_error
            )

        response = self.llm.get_completion(SYSTEM_PROMPT, prompt, temperature=0.2, max_tokens=8192)

        if is_python:
            fixed_code = extract_python_code(response)

            if not fixed_code:
                log_error(f"No code extracted from LLM response for {filepath}")
                return False

            is_valid, error = validate_python_code(fixed_code)
            if not is_valid:
                log_error(f"Generated fix has syntax errors: {error}")
                return False
        else:
            fixed_code = self._extract_code_block(response, file_ext)
            if not fixed_code:
                log_error(f"No code extracted from LLM response for {filepath}")
                return False

        if fixed_code.strip() == file_content.strip():
            log_error(f"LLM returned unchanged code for {filepath}")
            return False
        
        if len(original_content) <= MAX_FILE_CHARS:
            diff = create_diff_patch(original_content, fixed_code, filepath)
        else:
            diff = create_diff_patch(file_content, fixed_code, filepath)
        
        if diff:
            self.patches.append(diff)
            print(f"\nChanges to {filepath}:")
            print(diff[:800] + "..." if len(diff) > 800 else diff)
        
        self.sandbox.write_file(filepath, fixed_code)
        log_success(f"Applied fix to {filepath} (attempt {attempt})")
        
        return True

    def _extract_code_block(self, response: str, file_ext: str) -> str:
        lang_map = {
            'ts': ['typescript', 'ts'],
            'tsx': ['typescript', 'tsx', 'ts'],
            'js': ['javascript', 'js'],
            'jsx': ['javascript', 'jsx', 'js'],
            'css': ['css'],
            'scss': ['scss', 'css'],
            'json': ['json'],
            'yaml': ['yaml', 'yml'],
            'html': ['html'],
        }

        languages = lang_map.get(file_ext, [file_ext])

        for lang in languages:
            pattern = rf"```{lang}\s*(.*?)```"
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if matches:
                return matches[0].strip()

        pattern = r"```\s*(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            longest = max(matches, key=len)
            return longest.strip()

        return ""

    def _verify_fix(self):
        """Verify the fix and return (success, error_output)"""
        log_step("VERIFY", "Verifying the fix...")
        exit_code, output = self.sandbox.run_command(f"python {self.repro_script}", timeout=30)

        print(f"\nVerification output:\n{output[:1500]}")

        # Check if reproduction script has import errors - run framework tests as fallback
        if 'ImportError' in output or 'ModuleNotFoundError' in output:
            log_error("Reproduction script has import errors, running framework tests instead...")
            success, output = self._run_framework_tests()
        else:
            has_errors = extract_error_messages(output)
            success = exit_code == 0 and not has_errors

            if exit_code == 0 and not has_errors:
                if 'bug' in output.lower() and 'present' in output.lower():
                    success = False

        self.feedback_loop.add_attempt(
            attempt_num=len(self.feedback_loop.attempts_history) + 1,
            file_path=', '.join(self.target_files),
            code_applied="(see above)",
            error_output=output,
            success=success
        )
        
        if success:
            log_success("Fix verified successfully!")
            return True, output
        else:
            log_error("Fix did not resolve the issue")
            return False, output

    def _run_framework_tests(self):
        test_cmd = get_test_command(self.instance_id)
        log_step("VERIFY", f"Running {self.framework} tests: {test_cmd[:50]}...")

        exit_code, test_output = self.sandbox.run_command(
            f'cd /testbed && {test_cmd}',
            timeout=120
        )

        print(f"\n{self.framework.capitalize()} test output:\n{test_output[:1500]}")

        # Check test results based on framework
        if 'FAILED' in test_output or 'ERROR' in test_output or 'error:' in test_output.lower():
            log_error(f"{self.framework.capitalize()} tests failed")
            return False, test_output
        else:
            log_success(f"{self.framework.capitalize()} tests passed!")
            return True, test_output