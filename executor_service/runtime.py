import os
import shutil
import subprocess
import sys
import tempfile
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

LANGUAGE_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "c++": "cpp",
}

LANGUAGE_CONFIG = {
    "python": {
        "label": "Python",
        "extension": "py",
        "monaco_language": "python",
        "starter_code": "def solve():\n    # Write your solution here\n    return 'hello'\n\nprint(solve())\n",
    },
    "javascript": {
        "label": "JavaScript",
        "extension": "js",
        "monaco_language": "javascript",
        "starter_code": "function solve() {\n  // Write your solution here\n  return 'hello';\n}\n\nconsole.log(solve());\n",
    },
    "typescript": {
        "label": "TypeScript",
        "extension": "ts",
        "monaco_language": "typescript",
        "starter_code": "function solve(): string {\n  // Write your solution here\n  return 'hello';\n}\n\nconsole.log(solve());\n",
    },
    "java": {
        "label": "Java",
        "extension": "java",
        "monaco_language": "java",
        "starter_code": "public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"hello\");\n    }\n}\n",
    },
    "cpp": {
        "label": "C++",
        "extension": "cpp",
        "monaco_language": "cpp",
        "starter_code": "#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << \"hello\" << endl;\n    return 0;\n}\n",
    },
    "c": {
        "label": "C",
        "extension": "c",
        "monaco_language": "c",
        "starter_code": "#include <stdio.h>\n\nint main() {\n    printf(\"hello\\n\");\n    return 0;\n}\n",
    },
}

PRIMARY_EDITOR_LANGUAGES = ["python", "javascript", "typescript", "java", "cpp"]


def normalize_language(language: str) -> str:
    lang = (language or "").strip().lower()
    return LANGUAGE_ALIASES.get(lang, lang)


def get_execution_config() -> dict:
    languages = []
    for key in PRIMARY_EDITOR_LANGUAGES:
        config = LANGUAGE_CONFIG[key]
        languages.append(
            {
                "id": key,
                "label": config["label"],
                "monaco_language": config["monaco_language"],
                "starter_code": config["starter_code"],
            }
        )

    return {
        "languages": languages,
        "default_language": "python",
        "executor": "custom_cloud_run_executor",
        "supports_stdin": True,
        "supports_validation": True,
        "run_timeout_seconds": 5,
    }


def validate_code(code: str, language: str) -> dict:
    lang = normalize_language(language)
    if lang not in LANGUAGE_CONFIG:
        return {"valid": False, "language": lang, "errors": [{"message": f"Unsupported language: {language}"}]}

    if lang == "python":
        try:
            compile(code, "<string>", "exec")
            return {"valid": True, "language": lang, "errors": []}
        except SyntaxError as e:
            return {
                "valid": False,
                "language": lang,
                "errors": [{"line": e.lineno, "message": str(e.msg), "offset": e.offset}],
            }

    if not code.strip():
        return {"valid": False, "language": lang, "errors": [{"message": "Empty code"}]}

    return {"valid": True, "language": lang, "errors": []}


def execute_code(code: str, language: str, stdin: str = "", timeout_seconds: int = 5) -> dict:
    lang = normalize_language(language)
    if lang not in LANGUAGE_CONFIG:
        return _error_response(lang, "unsupported_language", f"Unsupported language: {language}")

    if not code.strip():
        return _error_response(lang, "validation_error", "Empty code")

    try:
        with tempfile.TemporaryDirectory(prefix=f"skillup-{lang}-") as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = _write_source_file(tmp_path, lang, code)
            result = _run_language(tmp_path, file_path, lang, stdin, timeout_seconds)
            if result["success"]:
                logger.info(f"Executor service ran {lang} code successfully")
            return result
    except subprocess.TimeoutExpired:
        return _error_response(lang, "timeout", "Execution timed out", exit_code=-1)
    except Exception as e:
        logger.error(f"Executor runtime error for {lang}: {e}")
        return _error_response(lang, "system_error", str(e), exit_code=-1)


def _write_source_file(tmp_path: Path, lang: str, code: str) -> Path:
    if lang == "java":
        file_name = "Main.java"
    else:
        file_name = f"main.{LANGUAGE_CONFIG[lang]['extension']}"
    file_path = tmp_path / file_name
    file_path.write_text(code, encoding="utf-8")
    return file_path


def _run_language(tmp_path: Path, file_path: Path, lang: str, stdin: str, timeout_seconds: int) -> dict:
    if lang == "python":
        interpreter = sys.executable
        return _run_process([interpreter, str(file_path)], tmp_path, stdin, timeout_seconds, lang)

    if lang == "javascript":
        node = _require_binary("node", lang)
        return _run_process([node, str(file_path)], tmp_path, stdin, timeout_seconds, lang)

    if lang == "typescript":
        node = _require_binary("node", lang)
        tsx = shutil.which("tsx")
        if tsx:
            return _run_process([tsx, str(file_path)], tmp_path, stdin, timeout_seconds, lang)
        tsc = _require_binary("tsc", lang)
        compile_result = _run_process([tsc, "--target", "es2020", "--module", "commonjs", str(file_path)], tmp_path, "", timeout_seconds, lang, capture_language="typescript")
        if not compile_result["success"]:
            compile_result["type"] = "compilation_error"
            return compile_result
        compiled = tmp_path / "main.js"
        return _run_process([node, str(compiled)], tmp_path, stdin, timeout_seconds, lang)

    if lang == "java":
        javac = _require_binary("javac", lang)
        compile_result = _run_process([javac, str(file_path)], tmp_path, "", timeout_seconds, lang)
        if not compile_result["success"]:
            compile_result["type"] = "compilation_error"
            return compile_result
        java = _require_binary("java", lang)
        return _run_process([java, "-cp", str(tmp_path), "Main"], tmp_path, stdin, timeout_seconds, lang)

    if lang == "cpp":
        compiler = _require_binary("g++", lang)
        output_bin = tmp_path / ("main.exe" if os.name == "nt" else "main")
        compile_result = _run_process([compiler, str(file_path), "-o", str(output_bin)], tmp_path, "", timeout_seconds, lang)
        if not compile_result["success"]:
            compile_result["type"] = "compilation_error"
            return compile_result
        return _run_process([str(output_bin)], tmp_path, stdin, timeout_seconds, lang)

    if lang == "c":
        compiler = _require_binary("gcc", lang)
        output_bin = tmp_path / ("main.exe" if os.name == "nt" else "main")
        compile_result = _run_process([compiler, str(file_path), "-o", str(output_bin)], tmp_path, "", timeout_seconds, lang)
        if not compile_result["success"]:
            compile_result["type"] = "compilation_error"
            return compile_result
        return _run_process([str(output_bin)], tmp_path, stdin, timeout_seconds, lang)

    return _error_response(lang, "unsupported_language", f"Unsupported language: {lang}")


def _run_process(command: list[str], cwd: Path, stdin: str, timeout_seconds: int, lang: str, capture_language: str | None = None) -> dict:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            input=stdin,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except FileNotFoundError as e:
        return _error_response(capture_language or lang, "runtime_not_available", str(e), exit_code=-1)

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    success = completed.returncode == 0 and not stderr

    return {
        "success": success,
        "stdout": stdout,
        "stderr": stderr,
        "error": None if success else (stderr or stdout or f"Process exited with code {completed.returncode}"),
        "exit_code": completed.returncode,
        "language": capture_language or lang,
        "type": "success" if success else "runtime_error",
    }


def _require_binary(binary: str, lang: str) -> str:
    resolved = shutil.which(binary)
    if not resolved:
        raise FileNotFoundError(f"Required runtime for {lang} is not available: {binary}")
    return resolved


def _error_response(lang: str, error_type: str, message: str, exit_code: int = 1) -> dict:
    return {
        "success": False,
        "stdout": "",
        "stderr": "",
        "error": message,
        "exit_code": exit_code,
        "language": lang,
        "type": error_type,
    }
