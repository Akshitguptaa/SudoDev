import re
from sudodev.client import LLMClient
from sudodev.sandbox.container import Sandbox
from sudodev.utils.logger import log_step, log_success, log_error, setup_logger
from sudodev.tools import (
    extract_python_code,
    extract_file_paths,
    validate_python_code,
    extract_error_messages,
    create_diff_patch
)

from sudodev.context_search import ContextSearch
from sudodev.feedback_loop import FeedbackLoop
from sudodev.improved_prompts import (
    build_improved_reproduce_prompt,
    build_improved_fix_prompt,
    build_improved_locate_prompt
)

logger = setup_logger(__name__)

SYSTEM_PROMPT = """You are SudoDev, a Senior Software Engineer specializing in debugging.
You are running inside a Linux environment with the repository checked out at /testbed.

YOUR PROCESS:
1. Analyze the GitHub issue carefully
2. Create a reproduction script that demonstrates the bug
3. Locate the relevant files using smart search
4. Extract only relevant code sections from large files
5. Generate fixes iteratively with error feedback
6. Verify the fix works

You learn from failures and try different approaches when needed.
"""

class ImprovedAgent:
    def __init__(self, issue_data):
        self.issue = issue_data
        self.llm = LLMClient()
        self.sandbox = Sandbox(issue_data['instance_id'])
        self.context_search = ContextSearch(self.llm)
        self.feedback_loop = FeedbackLoop(max_attempts=3)
        
        self.repro_script = "reproduce_issue.py"
        self.repro_output = ""
        self.target_files = []
        self.keywords = {}

    def run(self):
        log_step("INIT", f"Starting improved run for {self.issue['instance_id']}")
        try:
            self.sandbox.start()
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

    def _extract_keywords(self):
        log_step("ANALYZE", "Extracting keywords from the issue...")

        try:
            self.keywords = self.context_search.extract_keywords_from_issue(self.issue['problem_statement'])
            log_success(f"Extracted {sum(len(v) for v in self.keywords.values())} keywords")
        except Exception as e:
            logger.warning(f"Keyword extraction failed: {e}")
            self.keywords = {}

    def _get_file_tree(self, max_files=200):
        cmd = (
            "find /testbed -type f -name '*.py' "
            "! -path '*/.git/*' "
            "! -path '*/__pycache__/*' "
            "! -path '*/venv/*' "
            "! -path '*/env/*' "
            "! -name '*.pyc' "
            f"| head -n {max_files} "
            "| sort"
        )
        
        exit_code, output = self.sandbox.run_command(cmd)
        if exit_code == 0:
            files = [line.replace('/testbed/', '') for line in output.strip().split('\n') if line.strip()]
            return '\n'.join(files)
        return "Error getting file list"

    def _reproduce_bug(self):
        log_step("REPRODUCE", "Generating reproduction script with framework detection...")

        file_list = self._get_file_tree(max_files=100)

        prompt = build_improved_reproduce_prompt(
            issue_desc=self.issue['problem_statement'],
            repo_info=file_list[:500]
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
        print(f"\nReproduction output:\n{output[:1000]}")

        if exit_code != 0 or 'AssertionError' in output or 'Error' in output:
            log_success("Bug reproduced successfully")
            self.repro_output = output
            return True
        else:
            log_error("Could not reproduce the bug")
            return False
        
    def _locate_files_smart(self):
        log_step("LOCATE", "Using smart search to identify files...")
        issue_text = self.issue['problem_statement']
        potential_files = extract_file_paths(issue_text)

        if potential_files:
            log_success(f"Found explicit file mentions: {potential_files}")
            self.target_files = potential_files[:3]
            return True
        
        file_tree = self._get_file_tree(max_files=200)

        try:
            prompt = build_improved_locate_prompt(
                issue=self.issue['problem_statement'],
                repo_structure=file_tree,
                error_trace=self.repro_output
            )

            response = self.llm.get_completion(SYSTEM_PROMPT, prompt, temperature=0.2)
            files = extract_file_paths(response)

            if files:
                self.target_files = files[:3]
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
                self.target_files = files
                log_success(f"Context search found: {files}")
                return True
        except Exception as e:
            logger.error(f"Context search failed: {e}")
        
        log_error("Could not identify which files need fixing.")
        return False
    
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
        if len(original_content) > MAX_FILE_CHARS:
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
                log_error("Using first 25k characters as fallback")
        
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
        fixed_code = extract_python_code(response)
        
        if not fixed_code:
            log_error(f"No code extracted from LLM response for {filepath}")
            return False
        
        is_valid, error = validate_python_code(fixed_code)
        if not is_valid:
            log_error(f"Generated fix has syntax errors: {error}")
            return False
    
        if fixed_code.strip() == file_content.strip():
            log_error(f"LLM returned unchanged code for {filepath}")
            return False
        
        if len(original_content) <= MAX_FILE_CHARS:
            diff = create_diff_patch(original_content, fixed_code, filepath)
        else:
            diff = create_diff_patch(file_content, fixed_code, filepath)
        
        if diff:
            print(f"\nChanges to {filepath}:")
            print(diff[:800] + "..." if len(diff) > 800 else diff)
        
        self.sandbox.write_file(filepath, fixed_code)
        log_success(f"Applied fix to {filepath} (attempt {attempt})")
        
        return True
    
    def _verify_fix(self):
        """Verify the fix and return (success, error_output)"""
        log_step("VERIFY", "Verifying the fix...")
        exit_code, output = self.sandbox.run_command(f"python {self.repro_script}", timeout=30)
        
        print(f"\nVerification output:\n{output[:1000]}")
        
        # Check if reproduction script has import errors
        if 'ImportError: cannot import name' in output:
            log_error("Reproduction script has import errors, running real tests instead...")
            
            # Run Django tests as fallback
            exit_code, test_output = self.sandbox.run_command(
                'cd /testbed && python tests/runtests.py --settings=test_sqlite queries -v 2',
                timeout=60
            )
            
            print(f"\nDjango test output:\n{test_output[:1000]}")
            
            # Check Django test results
            if 'FAILED' not in test_output and 'ERROR' not in test_output:
                success = True
                output = test_output
                log_success("Django tests passed!")
            else:
                success = False
                output = test_output
                log_error("Django tests failed")
        else:
            # Reproduction script worked, use its result
            success = exit_code == 0 and not extract_error_messages(output)
        
        # Record in feedback loop
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