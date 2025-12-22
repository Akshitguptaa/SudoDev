import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()


def test_imports():
    print("Testing imports...")
    
    try:
        from sudodev.agent import Agent
        from sudodev.client import LLMClient
        from sudodev.sandbox.container import Sandbox
        from sudodev.tools import (
            extract_python_code,
            build_reproduce_prompt,
            build_fix_prompt,
            validate_python_code
        )
        print("[PASS] All imports successful")
        return True
    except ImportError as e:
        print(f"[FAIL] Import failed: {e}")
        return False


def test_llm_client():
    print("\nTesting LLM client...")
    
    if not os.getenv("GROQ_API_KEY"):
        print("[FAIL] GROQ_API_KEY not set")
        return False
    
    try:
        from sudodev.client import LLMClient
        client = LLMClient()
        
        response = client.get_completion(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Hello SudoDev' and nothing else.",
            temperature=0.1,
            max_tokens=50
        )
        
        if response and "sudodev" in response.lower():
            print(f"[PASS] LLM client working: {response[:50]}")
            return True
        else:
            print(f"[FAIL] Unexpected response: {response}")
            return False
    except Exception as e:
        print(f"[FAIL] LLM client test failed: {e}")
        return False


def test_tools():
    print("\nTesting tools...")
    
    from sudodev.tools import (
        extract_python_code,
        validate_python_code,
        extract_file_paths,
        build_reproduce_prompt
    )
    
    test_text = """
    Here's the code:
    ```python
    def hello():
        return "world"
    ```
    """
    code = extract_python_code(test_text)
    assert 'def hello' in code, "extract_python_code failed"
    print("[PASS] extract_python_code works")
    
    valid, error = validate_python_code("def foo():\n    return True")
    assert valid, f"validate_python_code failed: {error}"
    print("[PASS] validate_python_code works")
    
    valid, error = validate_python_code("def foo(\n    return")
    assert not valid, "validate_python_code should detect syntax errors"
    print("[PASS] validate_python_code detects errors")
    
    text = "Check the file `django/core/handlers/base.py` for issues"
    paths = extract_file_paths(text)
    assert 'django/core/handlers/base.py' in paths, "extract_file_paths failed"
    print("[PASS] extract_file_paths works")
    
    prompt = build_reproduce_prompt("Fix the bug", hints="Some hints")
    assert "Fix the bug" in prompt, "build_reproduce_prompt failed"
    print("[PASS] build_reproduce_prompt works")
    
    return True


def test_docker():
    print("\nTesting Docker...")
    
    try:
        import docker
        client = docker.from_env()
        client.ping()
        print("[PASS] Docker is running")
        
        images = client.images.list()
        sweb_images = [img for img in images if any('sweb.eval' in tag for tag in img.tags)]
        
        if sweb_images:
            print(f"[PASS] Found {len(sweb_images)} SWE-bench Docker images")
            for img in sweb_images[:3]:
                print(f"  - {img.tags[0] if img.tags else 'untagged'}")
        else:
            print("[WARN] No SWE-bench Docker images found")
            print("  Run: cd SWE-bench && python -m swebench.harness.docker_build --instance_id <id>")
        
        return True
    except Exception as e:
        print(f"[FAIL] Docker test failed: {e}")
        return False


def test_sandbox():
    print("\nTesting sandbox...")
    
    try:
        from sudodev.sandbox.container import Sandbox
        
        test_instance = "django__django-11001"
        sandbox = Sandbox(test_instance)
        
        print(f"  Starting sandbox for {test_instance}...")
        sandbox.start()
        print("  [PASS] Sandbox started")
        
        exit_code, output = sandbox.run_command("echo 'Hello from sandbox'")
        assert exit_code == 0, f"Command failed with exit code {exit_code}: {output}"
        assert output and len(output.strip()) > 0, f"Command output empty: {output}"
        print("  [PASS] Command execution works")
        
        sandbox.write_file("test.txt", "Hello World!")
        content = sandbox.read_file("test.txt")
        assert content == "Hello World!", f"File read/write failed: {content}"
        print("  [PASS] File operations work")
        
        sandbox.cleanup()
        print("  [PASS] Sandbox cleanup successful")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Sandbox test failed: {e}")
        print(f"  Make sure Docker image exists for the test instance")
        return False


def test_agent_minimal():
    print("\nTesting agent initialization...")
    
    try:
        from sudodev.agent import Agent
        
        issue = {
            'instance_id': 'test_instance',
            'problem_statement': 'Fix the bug in test.py',
            'repo': 'test/repo'
        }
        
        agent = Agent(issue)
        assert agent.issue == issue
        assert agent.repro_script == "reproduce_issue.py"
        print("[PASS] Agent initialization works")
        
        return True
    except Exception as e:
        print(f"[FAIL] Agent test failed: {e}")
        return False


def test_end_to_end():
    print("\n" + "="*60)
    print("END-TO-END TEST")
    print("="*60)
    
    try:
        from datasets import load_dataset
        from sudodev.agent import Agent
        
        print("\nLoading SWE-bench dataset...")
        dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        print(f"[PASS] Loaded {len(dataset)} issues")
        
        instance_id = "django__django-11001"
        print(f"\nTesting with instance: {instance_id}")
        
        issue = next((item for item in dataset if item["instance_id"] == instance_id), None)
        if not issue:
            print(f"[FAIL] Issue {instance_id} not found in dataset")
            return False
        
        print(f"Issue: {issue['problem_statement'][:100]}...")
        
        print("\nRunning agent...")
        agent = Agent(issue)
        success = agent.run()
        
        if success:
            print("\n" + "="*60)
            print("END-TO-END TEST PASSED")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("Agent completed but fix was not verified")
            print("="*60)
        
        return success
        
    except Exception as e:
        print(f"\n[FAIL] End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("="*60)
    print("SudoDev Test Suite")
    print("="*60)
    
    results = {}
    
    results['imports'] = test_imports()
    results['tools'] = test_tools()
    results['docker'] = test_docker()
    results['llm_client'] = test_llm_client()
    results['agent_init'] = test_agent_minimal()
    
    if results['docker']:
        results['sandbox'] = test_sandbox()
    else:
        results['sandbox'] = None
        print("\n[WARN] Skipping sandbox test (Docker not available)")
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for test_name, result in results.items():
        status = "PASS" if result is True else "FAIL" if result is False else "SKIP"
        print(f"[{status:4}] {test_name}")
    
    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")
    
    if passed >= 4:
        print("\n" + "="*60)
        choice = input("Run full end-to-end test? (y/N): ").strip().lower()
        if choice == 'y':
            results['e2e'] = test_end_to_end()
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())