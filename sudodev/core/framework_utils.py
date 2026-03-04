from typing import Optional, Tuple, List
import re

REPO_TO_FRAMEWORK = {
    "django/django": "django",
    "pallets/flask": "flask",
    "pytest-dev/pytest": "pytest",
    "scikit-learn/scikit-learn": "pytest",
    "matplotlib/matplotlib": "pytest",
    "astropy/astropy": "pytest",
    "mwaskom/seaborn": "pytest",
    "pylint-dev/pylint": "pytest",
    "pylint-dev/astroid": "pytest",
    "pydata/xarray": "pytest",
    "psf/requests": "pytest",
    "marshmallow-code/marshmallow": "pytest",
    "sqlfluff/sqlfluff": "pytest",
    "pyvista/pyvista": "pytest",
    "pvlib/pvlib-python": "pytest",
    "pydicom/pydicom": "pytest",
    "dbt-labs/dbt-core": "pytest",
    "sympy/sympy": "sympy",
    "sphinx-doc/sphinx": "sphinx",
}

FRAMEWORK_TEST_COMMANDS = {
    "django": "./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1",
    "flask": "pytest -rA",
    "pytest": "pytest --no-header -rA --tb=no -p no:cacheprovider",
    "sympy": "PYTHONWARNINGS='ignore::UserWarning,ignore::SyntaxWarning' bin/test -C --verbose",
    "sphinx": "tox --current-env -epy39 -v --",
    "node": "npm test 2>&1 || npx jest 2>&1 || true",
    "generic": "pytest -rA 2>&1 || npm test 2>&1 || true",
}

SOURCE_EXTENSIONS = {
    "python": (".py",),
    "javascript": (".js", ".jsx", ".mjs", ".cjs"),
    "typescript": (".ts", ".tsx"),
    "css": (".css", ".scss", ".less", ".sass"),
    "html": (".html", ".htm"),
    "config": (".json", ".yaml", ".yml", ".toml"),
}

ALL_SOURCE_EXTENSIONS = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".scss",
    ".html", ".json", ".yaml", ".yml", ".toml",
    ".md", ".rst", ".cfg", ".ini",
)


def get_repo_from_instance_id(instance_id: str) -> str:
    if "__" not in instance_id:
        return instance_id

    parts = instance_id.split("__")
    if len(parts) < 2:
        return instance_id

    org = parts[0]
    repo_with_issue = parts[1]

    match = re.match(r'^(.+?)-\d+$', repo_with_issue)
    if match:
        repo = match.group(1)
    else:
        repo = repo_with_issue

    return f"{org}/{repo}"


def get_framework_from_instance_id(instance_id: str) -> str:
    if instance_id.startswith("github-"):
        return detect_framework_from_url(instance_id)

    repo = get_repo_from_instance_id(instance_id)
    return REPO_TO_FRAMEWORK.get(repo, "generic")


def detect_framework_from_url(instance_id_or_url: str) -> str:
    lower = instance_id_or_url.lower()

    framework_hints = {
        "django": "django",
        "flask": "flask",
        "pytest": "pytest",
        "sympy": "sympy",
        "sphinx": "sphinx",
        "fastapi": "pytest",
        "sklearn": "pytest",
        "scikit": "pytest",
        "matplotlib": "pytest",
        "numpy": "pytest",
        "pandas": "pytest",
    }

    for hint, framework in framework_hints.items():
        if hint in lower:
            return framework

    return "generic"


def detect_repo_language(file_tree: str) -> str:
    if not file_tree:
        return "python"

    lines = file_tree.strip().split('\n')
    counts = {
        "python": 0,
        "typescript": 0,
        "javascript": 0,
        "css": 0,
    }

    for line in lines:
        line = line.strip().lower()
        if line.endswith('.py'):
            counts["python"] += 1
        elif line.endswith('.ts') or line.endswith('.tsx'):
            counts["typescript"] += 1
        elif line.endswith('.js') or line.endswith('.jsx'):
            counts["javascript"] += 1
        elif line.endswith('.css') or line.endswith('.scss'):
            counts["css"] += 1

    has_package_json = any('package.json' in l for l in lines)
    has_tsconfig = any('tsconfig' in l for l in lines)

    if has_tsconfig or counts["typescript"] > counts["python"]:
        return "typescript"
    elif has_package_json or counts["javascript"] > counts["python"]:
        return "javascript"
    elif counts["python"] > 0:
        return "python"

    return "python"


def is_node_project(file_tree: str) -> bool:
    if not file_tree:
        return False
    return any(marker in file_tree for marker in [
        'package.json', 'tsconfig', '.tsx', '.jsx',
        'node_modules', 'webpack', 'vite.config',
        '.eslintrc', 'next.config'
    ])


def get_test_command(instance_id: str, version: str = None) -> str:
    if instance_id.startswith("github-"):
        framework = detect_framework_from_url(instance_id)
        return FRAMEWORK_TEST_COMMANDS.get(framework, FRAMEWORK_TEST_COMMANDS["generic"])

    repo = get_repo_from_instance_id(instance_id)

    # Try to get from SWE-bench specs if available
    try:
        from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS

        if repo in MAP_REPO_VERSION_TO_SPECS:
            repo_specs = MAP_REPO_VERSION_TO_SPECS[repo]

            # If version provided, try exact match
            if version and version in repo_specs:
                spec = repo_specs[version]
                if "test_cmd" in spec:
                    test_cmd = spec["test_cmd"]
                    # Handle list of commands
                    if isinstance(test_cmd, list):
                        return " && ".join(test_cmd)
                    return test_cmd

            # Otherwise get first available version's test command
            for ver, spec in repo_specs.items():
                if "test_cmd" in spec:
                    test_cmd = spec["test_cmd"]
                    if isinstance(test_cmd, list):
                        return " && ".join(test_cmd)
                    return test_cmd

    except ImportError:
        pass

    framework = get_framework_from_instance_id(instance_id)
    return FRAMEWORK_TEST_COMMANDS.get(framework, FRAMEWORK_TEST_COMMANDS["generic"])


def get_version_from_instance_id(instance_id: str) -> Optional[str]:
    return None


def get_file_extensions(instance_id: str = None, file_tree: str = None) -> Tuple[str, ...]:
    if file_tree and is_node_project(file_tree):
        return (".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ".json")

    return ALL_SOURCE_EXTENSIONS


def build_find_command(max_files: int = 200, extensions: Tuple[str, ...] = None) -> str:
    if extensions is None:
        extensions = ALL_SOURCE_EXTENSIONS

    name_conditions = " -o ".join(f"-name '*{ext}'" for ext in extensions)

    cmd = (
        f"find /testbed -type f \\( {name_conditions} \\) "
        "! -path '*/.git/*' "
        "! -path '*/__pycache__/*' "
        "! -path '*/node_modules/*' "
        "! -path '*/venv/*' "
        "! -path '*/env/*' "
        "! -path '*/.tox/*' "
        "! -path '*/dist/*' "
        "! -path '*/build/*' "
        "! -path '*/.next/*' "
        "! -path '*/.cache/*' "
        "! -name '*.pyc' "
        "! -name '*.min.js' "
        "! -name '*.min.css' "
        "! -name '*.map' "
        "! -name 'package-lock.json' "
        "! -name 'yarn.lock' "
        f"| head -n {max_files} "
        "| sort"
    )

    return cmd
