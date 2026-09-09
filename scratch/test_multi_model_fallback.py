import os
import sys
import json
sys.path.insert(0, ".")

from sutra.ai.router import AIMultiRouter
from sutra.ai.classifier import AIBlockClassifier
from sutra.tools.pdf_analyzer import PDFStyleAnalyzer

print("=== TESTING MULTI-MODEL FALLBACK CHAIN ===")

# Test 1: AIMultiRouter with no keys (should cascade straight to local fallback)
router_no_keys = AIMultiRouter(gemini_key="", openai_key="", anthropic_key="")
res1 = router_no_keys.call_json("Test prompt", timeout=1.0)
assert res1["success"] is False, "Expected False for no keys"
assert res1["provider"] == "sutra-local-semantic", f"Unexpected provider: {res1['provider']}"
print("[PASS] Test 1: No keys -> clean cascade to sutra-local-semantic")
print("       Fallback trace:", res1["fallback_trace"])

# Test 2: AIMultiRouter with invalid keys for all 3 cloud providers
# It should attempt Gemini, fail, attempt OpenAI, fail, attempt Claude, fail, then land safely on local engine!
router_bad_keys = AIMultiRouter(gemini_key="bad-gemini-key", openai_key="bad-openai-key", anthropic_key="bad-claude-key")
res2 = router_bad_keys.call_json("Test prompt", timeout=2.0)
assert res2["provider"] == "sutra-local-semantic", f"Unexpected provider: {res2['provider']}"
assert any("gemini" in step for step in res2["fallback_trace"]), "Gemini missing from trace"
assert any("openai" in step for step in res2["fallback_trace"]), "OpenAI missing from trace"
assert any("claude" in step for step in res2["fallback_trace"]), "Claude missing from trace"
assert any("local-semantic-engine" in step for step in res2["fallback_trace"]), "Local missing from trace"
print("[PASS] Test 2: Bad/unreachable cloud keys -> 4-stage cascade trace:")
for step in res2["fallback_trace"]:
    print(f"       -> {step}")

# Test 3: AIBlockClassifier fallback chain
classifier = AIBlockClassifier()
test_blocks = [
    {"id": "b1", "type": "paragraph", "content": "Journal of Applied and Natural Science"},
    {"id": "b2", "type": "paragraph", "content": "T. Prathima and K. Viswanath"},
    {"id": "b3", "type": "paragraph", "content": "Department of Agronomy, Agricultural College, Tirupati"},
    {"id": "b4", "type": "paragraph", "content": "Abstract: In the present investigation, field experiment was conducted..."},
    {"id": "b5", "type": "paragraph", "content": "1. Introduction"},
    {"id": "b6", "type": "paragraph", "content": "Sesamum is an important oilseed crop grown in India."}
]
result = classifier.classify_blocks(test_blocks)
assert result["status"] == "success", "Block classification did not succeed"
assert result["updated_count"] > 0, "No blocks updated"
print(f"[PASS] Test 3: Block Classifier succeeded with provider: '{result['provider']}', updated: {result['updated_count']} blocks")

# Test 4: PDFStyleAnalyzer end-to-end with MultiModelRouter
analyzer = PDFStyleAnalyzer("inputandoutput/Output-7042.pdf")
settings, ai_check, logo_bytes = analyzer.analyze()
assert ai_check["status"] == "passed", f"Unexpected AI check status: {ai_check['status']}"
assert "provider" in ai_check, "Missing provider in ai_check"
print(f"[PASS] Test 4: PDFStyleAnalyzer succeeded with provider: '{ai_check['provider']}'")
print(f"       AI Checks passed: {len(ai_check.get('checks', []))}")
print(f"       Fallback trace: {ai_check.get('fallback_trace', [])}")

print("\n🎉 ALL MULTI-MODEL CASCADING FALLBACK TESTS PASSED PERFECTLY!")
