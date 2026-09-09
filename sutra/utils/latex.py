import re

LATEX_ESCAPE_MAP = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}

# Regex to match any of the characters that need escaping
LATEX_ESCAPE_RE = re.compile(r"([&%$#_{}~^\\])")

def latex_escape(text: str) -> str:
    """
    Safely escapes arbitrary text for inclusion in LaTeX content.
    Prevents LaTeX injection vulnerabilities (Critical SEC-05 / SEC-06).
    """
    if not text:
        return ""
        
    # Defense-in-depth: scan for and neutralize raw command patterns before character escaping
    unsafe_patterns = [
        r"\\input(?![a-zA-Z])", r"\\include(?![a-zA-Z])", r"\\write(?![a-zA-Z])", r"\\immediate(?![a-zA-Z])",
        r"\\openin(?![a-zA-Z])", r"\\openout(?![a-zA-Z])", r"\\read(?![a-zA-Z])", r"\\bibliography(?![a-zA-Z])",
        r"\\exec(?![a-zA-Z])", r"\\shellescape(?![a-zA-Z])"
    ]
    for pattern in unsafe_patterns:
        text = re.sub(pattern, lambda m: f"[neutralized command: {m.group(0)[1:]}]", text, flags=re.IGNORECASE)
        
    # Replace characters according to map
    return LATEX_ESCAPE_RE.sub(lambda match: LATEX_ESCAPE_MAP[match.group(1)], text)


import os
import subprocess
from typing import List, Dict, Any, Optional
from sutra.utils.download_tectonic import get_tectonic_path

def compile_latex_to_pdf(tex_path: str, output_dir: str) -> List[str]:
    """
    Compiles LaTeX to PDF using Tectonic.
    Returns a list of structured, human-readable error messages if compilation fails.
    """
    try:
        tectonic_bin = get_tectonic_path()
    except Exception as e:
        return [f"Failed to locate Tectonic compiler: {str(e)}"]
    
    output_dir = os.path.abspath(output_dir)
    tex_path = os.path.abspath(tex_path)
    tex_file = os.path.basename(tex_path)

    cmd = [
        tectonic_bin,
        "-o", output_dir,
        "--keep-logs",
        tex_file
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=output_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False # We handle non-zero exit codes ourselves
        )
    except Exception as e:
        return [f"Failed to execute Tectonic compiler: {str(e)}"]
        
    if result.returncode == 0:
        return []
        
    # Compile failed. Let's parse the log file to trace the errors
    base_name = os.path.splitext(os.path.basename(tex_path))[0]
    log_path = os.path.join(output_dir, f"{base_name}.log")
    
    errors = []
    log_content = ""
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            log_content = f.read()
            
    # Read generated tex lines to map back
    tex_lines = []
    if os.path.exists(tex_path):
        with open(tex_path, "r", encoding="utf-8", errors="ignore") as f:
            tex_lines = f.read().splitlines()
            
    if log_content:
        parsed_errors = parse_latex_log_errors(log_content)
        for err in parsed_errors:
            msg = err["message"]
            line = err["line"]
            
            if line and tex_lines:
                sutra_id = map_latex_line_to_sutra_id(tex_lines, line)
                err_detail = f"LaTeX Error at line {line}"
                if sutra_id:
                    err_detail += f" (associated with document element: '{sutra_id}')"
                err_detail += f": {msg}"
                errors.append(err_detail)
            else:
                errors.append(f"LaTeX Error: {msg}")
    else:
        # Fallback if log is missing
        errors.append(f"Tectonic compile failed (exit code {result.returncode}). Stderr: {result.stderr.strip()}")
        
    return errors

def parse_latex_log_errors(log_content: str) -> List[Dict[str, Any]]:
    errors = []
    lines = log_content.splitlines()
    current_error = None
    
    for idx, line in enumerate(lines):
        if line.startswith("!"):
            current_error = line[1:].strip()
            # Look ahead to find the line number (l.<num>)
            line_num = None
            for j in range(idx + 1, min(idx + 10, len(lines))):
                next_line = lines[j]
                m = re.match(r"^l\.(\d+)", next_line.strip())
                if m:
                    line_num = int(m.group(1))
                    break
            errors.append({
                "message": current_error,
                "line": line_num
            })
    return errors

def map_latex_line_to_sutra_id(tex_lines: List[str], line_num: int) -> Optional[str]:
    start_idx = min(line_num - 1, len(tex_lines) - 1)
    for i in range(start_idx, -1, -1):
        line = tex_lines[i]
        m = re.match(r"^%\s*sutra-id:\s*(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return None
