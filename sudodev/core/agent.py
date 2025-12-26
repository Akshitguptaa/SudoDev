import re
from sudodev.core.client import LLMClient
from sudodev.runtime.container import Sandbox
from sudodev.core.utils.logger import log_step, log_success, log_error, setup_logger
from sudodev.core.tools import (
    build_reproduce_prompt,
    build_fix_prompt,
    extract_python_code,
    extract_file_paths,
    validate_python_code,
    extract_error_messages,
    create_diff_patch
)
import sudodev.runtime.config as config

logger = setup_logger(__name__)

SYSTEM_PROMPT = """You are SudoDev, an Senior software engineer.
You are running inside a Linux environment with the repository checked out at /testbed.

YOUR PROCESS:
1. You will be given a GitHub Issue.
2. You must first create a reproduction script named `reproduce_issue.py` that fails when the bug is present.
3. You will then modify the source code to fix the bug by providing the COMPLETE fixed file content.
"""

class Agent:
    def __init__(self, issue_data):
        self.issue = issue_data
        self.llm = LLMClient()
        self.sandbox = Sandbox(issue_data['instance_id'])
        self.repro_script = "reproduce_issue.py"
        self.repro_output = "" 
        self.target_files = []

    def run(self):
        log_step("INIT", f"Starting run for {self.issue['instance_id']}")
        
        try:
            self.sandbox.start()
            
            if not self._reproduce_bug():
                logger.error("Failed to reproduce the bug. Aborting.")
                return False

            if not self._locate_files():
                logger.error("Failed to locate files to fix. Aborting.")
                return False

            if not self._generate_fix():
                logger.error("Failed to generate fix. Aborting.")
                return False

            return self._verify_fix()

        except Exception as e:
            logger.critical(f"Agent failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.sandbox.cleanup()

    def _get_file_tree(self, max_files=50):
        cmd = (
            "find /testbed -type f -name '*.py' "
            "! -path '*/.git/*' "
            "! -path '*/__pycache__/*' "
            "! -path '*/venv/*' "
            "! -path '*/env/*' "
            "! -name '*.pyc' "
            "| head -n {} "
            "| sort"
        ).format(max_files)
        
        exit_code, output = self.sandbox.run_command(cmd)
        if exit_code == 0:
            files = [line.replace('/testbed/', '') for line in output.strip().split('\n') if line.strip()]
            return '\n'.join(files)
        return "Error getting file list"

    def _reproduce_bug(self):
        log_step("REPRODUCE", "Generating reproduction script...")

        file_list = self._get_file_tree(max_files=100)
        
        prompt = build_reproduce_prompt(
            issue_desc=self.issue['problem_statement'],
            hints=f"Repository files (sample):\n{file_list[:1000]}"
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
        print(f"\nReproduction output:\n{output}")
        
        if exit_code != 0:
            log_success("Bug reproduced successfully")
            self.repro_output = output
            return True
        else:
            errors = extract_error_messages(output)
            if errors:
                log_success("Bug confirmed from output")
                self.repro_output = output
                return True
            else:
                log_error("Could not reproduce the bug")
                return False

    def _locate_files(self):
        log_step("LOCATE", "Identifying files to fix...")

        issue_text = self.issue['problem_statement']
        potential_files = extract_file_paths(issue_text)
        
        if potential_files:
            log_success(f"Found file hints in issue: {potential_files}")
            self.target_files = potential_files
            return True
        
        file_tree = self._get_file_tree(max_files=150)
        
        from sudodev.tools import build_locate_files_prompt
        prompt = build_locate_files_prompt(
            issue=self.issue['problem_statement'],
            repo_structure=file_tree
        )
        
        response = self.llm.get_completion(SYSTEM_PROMPT, prompt, temperature=0.2)
        files = extract_file_paths(response)
        
        if files:
            self.target_files = files[:3]
            log_success(f"Identified files to fix: {self.target_files}")
            return True
        else:
            log_error("Could not identify which files need fixing.")
            return False

    def _generate_fix(self):
        log_step("FIX", f"Generating fixes for {len(self.target_files)} file(s)...")

        fixed_any = False
        
        for filepath in self.target_files:
            log_step("FIX", f"Processing {filepath}")
            
            original_content = self.sandbox.read_file(filepath)
            if not original_content:
                log_error(f"Could not read {filepath}, skipping...")
                continue
            
            MAX_FILE_CHARS = 32000
            if len(original_content) > MAX_FILE_CHARS:
                log_error(f"File {filepath} too large ({len(original_content)} chars, max {MAX_FILE_CHARS})")
                log_error("Skipping this file. Consider implementing chunking or using a different strategy.")
                continue
            
            prompt = build_fix_prompt(
                issue=self.issue['problem_statement'],
                file_content=original_content,
                file_path=filepath,
                error_trace=self.repro_output
            )
            
            response = self.llm.get_completion(SYSTEM_PROMPT, prompt, temperature=0.2, max_tokens=8192)
            
            fixed_code = extract_python_code(response)
            
            if not fixed_code:
                log_error(f"No code extracted from LLM response for {filepath}")
                continue
            
            is_valid, error = validate_python_code(fixed_code)
            if not is_valid:
                log_error(f"Generated fix has syntax errors: {error}")
                continue
            
            if fixed_code.strip() == original_content.strip():
                log_error(f"LLM returned unchanged file for {filepath}")
                continue
            
            diff = create_diff_patch(original_content, fixed_code, filepath)
            if diff:
                print(f"\nChanges to {filepath}:")
                print(diff[:500] + "..." if len(diff) > 500 else diff)
            
            self.sandbox.write_file(filepath, fixed_code)
            log_success(f"Applied fix to {filepath}")
            fixed_any = True
        
        return fixed_any

    def _verify_fix(self):
        log_step("VERIFY", "Verifying the fix...")
        exit_code, output = self.sandbox.run_command(f"python {self.repro_script}", timeout=30)
        
        print(f"\nVerification output:\n{output}")
        
        if exit_code == 0:
            errors = extract_error_messages(output)
            if not errors:
                log_success("Fix verified successfully")
                return True
            else:
                log_error(f"Script passed but still has {len(errors)} errors")
                return False
        else:
            log_error("Fix did not resolve the issue")
            return False