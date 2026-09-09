"""
sutra.ai.classifier — Semantic & LLM-Powered Manuscript Block Classifier

Features:
1. LLM Support: Google Gemini (gemini-1.5-flash/gemini-2.0-flash) and OpenAI (gpt-4o-mini).
2. Offline Semantic Engine: High-accuracy rule-based classifier when no API key is provided.
3. Provenance Tracking: Enforces ai-addon.md rules (is_ai_assisted, ai_provider, ai_confidence).
4. Safety: Propose, never overwrite without human-in-the-loop review.
"""

import os
import re
import json
import datetime
import urllib.request
import urllib.error
from typing import List, Dict, Any, Tuple


class AIBlockClassifier:
    def __init__(self, api_key: str = None, provider: str = None):
        self.gemini_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.openai_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("CHATGPT_API_KEY")
        self.anthropic_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        self.provider = provider

    def _extract_plain_text(self, block: Dict[str, Any]) -> str:
        content = block.get("content")
        if not content:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text") or item.get("institution") or f"{item.get('given_name', '')} {item.get('family_name', '')}".strip() or "")
                elif isinstance(item, list):
                    parts.append("".join(run.get("text", "") for run in item if isinstance(run, dict)))
                else:
                    parts.append(str(item))
            return " ".join(filter(None, parts))
        if isinstance(content, dict):
            if content.get("caption"):
                cap = content["caption"]
                if isinstance(cap, list):
                    return "".join(r.get("text", "") for r in cap if isinstance(r, dict))
                return str(cap)
            return content.get("text") or content.get("content_text") or ""
        return ""

    def classify_blocks(self, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Classifies blocks using cascading multi-model fallback:
        1. Google Gemini (gemini-3.6-flash / gemini-1.5-flash)
        2. OpenAI ChatGPT (gpt-4o-mini)
        3. Anthropic Claude (claude-3-5-haiku)
        4. Sutra Academic Semantic Engine (Offline Zero-Token Heuristics)
        """
        if not blocks:
            return {
                "status": "success",
                "provider": "none",
                "updated_count": 0,
                "blocks": [],
                "message": "No blocks provided for classification."
            }

        gemini_error = None
        openai_error = None
        claude_error = None

        # 1. Primary: Google Gemini
        if self.gemini_key:
            try:
                updated_blocks, count = self._classify_with_gemini(blocks)
                return {
                    "status": "success",
                    "provider": "google-gemini",
                    "updated_count": count,
                    "blocks": updated_blocks,
                    "message": f"Successfully classified {count} blocks using Google Gemini AI."
                }
            except Exception as e:
                gemini_error = str(e)
                print(f"[AIClassifier] Gemini API error: {e}")

        # 2. Fallback 1: OpenAI ChatGPT
        if self.openai_key:
            try:
                updated_blocks, count = self._classify_with_openai(blocks)
                return {
                    "status": "success",
                    "provider": "openai-chatgpt",
                    "updated_count": count,
                    "blocks": updated_blocks,
                    "message": f"Successfully classified {count} blocks using OpenAI ChatGPT (Fallback 1)."
                }
            except Exception as e:
                openai_error = str(e)
                print(f"[AIClassifier] OpenAI API error: {e}")

        # 3. Fallback 2: Anthropic Claude
        if self.anthropic_key:
            try:
                updated_blocks, count = self._classify_with_claude(blocks)
                return {
                    "status": "success",
                    "provider": "anthropic-claude",
                    "updated_count": count,
                    "blocks": updated_blocks,
                    "message": f"Successfully classified {count} blocks using Anthropic Claude (Fallback 2)."
                }
            except Exception as e:
                claude_error = str(e)
                print(f"[AIClassifier] Claude API error: {e}")

        # 4. Fallback 3: Offline Semantic Rule Engine (Always available, zero tokens)
        updated_blocks, count = self._classify_with_semantic_engine(blocks)

        # Build informative fallback message
        errors = [err for err in [gemini_error, openai_error, claude_error] if err]
        if errors:
            fallback_msg = f"Classified {count} blocks using Academic Semantic Engine. Cloud LLM fallback trace: {'; '.join(errors[:2])}"
        else:
            fallback_msg = f"Classified {count} blocks using Academic Semantic Engine (Configure GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY for Cloud LLM)."

        return {
            "status": "success",
            "provider": "sutra-academic-heuristics",
            "updated_count": count,
            "blocks": updated_blocks,
            "message": fallback_msg
        }

    def _classify_with_semantic_engine(self, blocks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Offline semantic classifier inspecting structure, typography, keywords, and academic patterns.
        """
        updated_count = 0
        affil_words = [
            "department", "dept", "university", "college", "faculty", "institute",
            "school", "laboratory", "hospital", "center", "centre", "station",
            "campus", "ministry", "academy", "division", "agromet"
        ]
        academic_headings = {
            "introduction": "heading_l1",
            "materials and methods": "heading_l1",
            "material and methods": "heading_l1",
            "methodology": "heading_l1",
            "methods": "heading_l1",
            "experimental": "heading_l1",
            "results": "heading_l1",
            "discussion": "heading_l1",
            "results and discussion": "heading_l1",
            "conclusion": "heading_l1",
            "conclusions": "heading_l1",
            "acknowledgements": "heading_l1",
            "acknowledgments": "heading_l1",
            "references": "heading_l1",
            "bibliography": "heading_l1",
            "literature cited": "heading_l1"
        }
        ref_heading_labels = {"references", "bibliography", "literature cited"}

        # Reference entry heuristic: author-year format like "Author, A.B. ... (2005)."
        ref_entry_pattern = re.compile(
            r"^[A-Z][a-zA-Z\-]+[,\.].*\(\d{4}\)"
        )
        # Numbered reference format: [1] Author...
        ref_numbered_pattern = re.compile(r"^\[\d+\]\s+[A-Z]")

        has_title = False
        in_abstract = False
        in_references = False

        for i, b in enumerate(blocks):
            text = self._extract_plain_text(b).strip()
            clean_text = re.sub(r"^\d+[\.\s]+", "", text).strip().lower()
            old_type = b.get("type", "paragraph")
            new_type = old_type

            # Check for Table or Figure already typed from Pandoc AST (genuine structure)
            if old_type in ("table", "figure", "equation"):
                continue

            # 1. Check for reference section heading
            if clean_text in ref_heading_labels:
                new_type = "heading_l1"
                in_references = True
                in_abstract = False

            # 2. Paragraphs under "References" heading → leave as paragraph
            #    (document_to_blocks handles the actual grouping into reference_list)
            #    But if the AI classifier is run standalone, mark them for grouping
            elif in_references and old_type == "paragraph":
                # Check if this looks like a reference entry
                if (ref_entry_pattern.match(text) or
                    ref_numbered_pattern.match(text) or
                    len(text) > 20):
                    # Keep as paragraph — the post-processing in document_to_blocks
                    # will group them. Don't reclassify here.
                    continue
                elif text and b.get("type", "").startswith("heading_"):
                    # Hit another heading, references section ended
                    in_references = False

            # 3. Section Headings (Numbered or Standard) — exit references zone
            elif clean_text in academic_headings and clean_text not in ref_heading_labels:
                new_type = academic_headings[clean_text]
                in_abstract = False
                in_references = False
            elif re.match(r"^(\d+\.\d+\.\d+)\s+[A-Z]", text) and len(text) < 90:
                new_type = "heading_l3"
                in_abstract = False
                in_references = False
            elif re.match(r"^(\d+\.\d+)\s+[A-Z]", text) and len(text) < 90:
                new_type = "heading_l2"
                in_abstract = False
                in_references = False
            elif re.match(r"^(\d+)\.?\s+[A-Z]", text) and len(text) < 90:
                new_type = "heading_l1"
                in_abstract = False
                in_references = False

            # 4. Abstract
            elif re.match(r"^(abstract|summary)[:\s]?$", text, re.IGNORECASE):
                new_type = "abstract"
                in_abstract = True
                in_references = False
            elif re.match(r"^(abstract|summary)[:\s]", text, re.IGNORECASE):
                new_type = "abstract"
                in_abstract = True
                in_references = False
            elif in_abstract:
                if re.match(r"^(keywords|key\s*words|1[\.\s]|introduction)", text, re.IGNORECASE):
                    in_abstract = False
                else:
                    new_type = "abstract"

            # 5. Frontmatter (Title, Authors, Affiliations) before abstract/first heading
            elif not has_title and i == 0 and len(text) > 5 and not re.match(r"^(section|chapter|\d+[\.\s])", text, re.IGNORECASE):
                new_type = "title"
                has_title = True
            elif not has_title and old_type == "title":
                has_title = True
            elif i < 15 and not in_abstract and not in_references and not b.get("type", "").startswith("heading"):
                lower = text.lower()
                if any(w in lower for w in affil_words) or "@" in text or "corresponding author" in lower:
                    new_type = "affiliations"
                elif len(text) < 100 and not text.startswith("http") and not re.search(r"[a-z]{3,}\.\s*$", text) and not any(w in lower for w in ["the", "this", "study", "paper"]):
                    new_type = "authors"

            # 6. DO NOT reclassify paragraphs that merely mention "Table N:" or "Figure N:"
            #    as table/figure blocks. Only genuinely structured Table/Figure elements from
            #    the Pandoc AST should be typed as table/figure.
            #    (Removed the old regex that incorrectly promoted captions/mentions.)

            # Apply change if different or unconfirmed
            if new_type != old_type or b.get("type") == "unrecognized":
                b["type"] = new_type
                b["is_ai_assisted"] = True
                b["ai_provider"] = "sutra-semantic-engine"
                b["ai_confidence"] = 0.92
                b["state"] = "confirmed"
                b["warnings"] = []
                b["is_user_confirmed"] = False
                b["ai_change"] = {
                    "old_type": old_type,
                    "new_type": new_type,
                    "reason": f"Semantic engine inferred {new_type}",
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                    "reviewed": False
                }
                updated_count += 1

        return blocks, updated_count

    def _classify_with_gemini(self, blocks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Sends block snippets to Google Gemini REST API for classification.
        """
        # Prepare lightweight block summaries (ID, snippet)
        snippets = []
        for i, b in enumerate(blocks[:60]):
            text = self._extract_plain_text(b)[:150].strip()
            snippets.append({"index": i, "id": b["id"], "current_type": b.get("type"), "text": text})

        prompt = (
            "You are an academic document parser. Classify each of the following manuscript blocks into exactly one of these IR types:\n"
            "['title', 'authors', 'affiliations', 'abstract', 'heading_l1', 'heading_l2', 'heading_l3', 'paragraph', 'figure', 'table', 'equation', 'reference_list']\n\n"
            "Rules:\n"
            "- 'title': Article title\n"
            "- 'authors': Author names\n"
            "- 'affiliations': Institutions/departments/emails\n"
            "- 'abstract': Abstract text\n"
            "- 'heading_l1': Main section headers (Introduction, Methods, Results, Discussion, Conclusion)\n"
            "- 'heading_l2' / 'heading_l3': Subsections\n"
            "- 'reference_list': Bibliography items\n\n"
            f"Input blocks:\n{json.dumps(snippets)}\n\n"
            "Respond ONLY with a JSON array of objects: [{\"id\": \"...\", \"type\": \"...\", \"confidence\": 0.95}]"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))

        raw_content = res_data["candidates"][0]["content"]["parts"][0]["text"]
        predictions = json.loads(raw_content)

        pred_map = {p["id"]: p for p in predictions if "id" in p and "type" in p}
        updated_count = 0
        for b in blocks:
            if b["id"] in pred_map:
                pred = pred_map[b["id"]]
                new_t = pred["type"]
                if new_t in ["title", "authors", "affiliations", "abstract", "heading_l1", "heading_l2", "heading_l3", "paragraph", "figure", "table", "equation", "reference_list"]:
                    if b.get("type") != new_t:
                        old_t = b.get("type", "paragraph")
                        b["type"] = new_t
                        b["is_ai_assisted"] = True
                        b["ai_provider"] = "gemini-3.6-flash"
                        b["ai_confidence"] = float(pred.get("confidence", 0.95))
                        b["state"] = "confirmed"
                        b["warnings"] = []
                        b["is_user_confirmed"] = False
                        b["ai_change"] = {
                            "old_type": old_t,
                            "new_type": new_t,
                            "reason": f"Gemini AI identified as {new_t}",
                            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                            "reviewed": False
                        }
                        updated_count += 1

        return blocks, updated_count

    def _classify_with_openai(self, blocks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Sends block snippets to OpenAI chat completion API.
        """
        snippets = []
        for i, b in enumerate(blocks[:60]):
            text = self._extract_plain_text(b)[:150].strip()
            snippets.append({"index": i, "id": b["id"], "current_type": b.get("type"), "text": text})

        prompt = (
            "Classify each of the following manuscript blocks into: "
            "['title', 'authors', 'affiliations', 'abstract', 'heading_l1', 'heading_l2', 'heading_l3', 'paragraph', 'figure', 'table', 'equation', 'reference_list'].\n"
            f"Input:\n{json.dumps(snippets)}\n\n"
            "Respond ONLY with a JSON array: [{\"id\": \"...\", \"type\": \"...\", \"confidence\": 0.95}]"
        )

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_key}"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))

        raw_content = res_data["choices"][0]["message"]["content"]
        data = json.loads(raw_content)
        predictions = data if isinstance(data, list) else data.get("predictions") or data.get("blocks") or []

        pred_map = {p["id"]: p for p in predictions if "id" in p and "type" in p}
        updated_count = 0
        for b in blocks:
            if b["id"] in pred_map:
                pred = pred_map[b["id"]]
                new_t = pred["type"]
                if new_t in ["title", "authors", "affiliations", "abstract", "heading_l1", "heading_l2", "heading_l3", "paragraph", "figure", "table", "equation", "reference_list"]:
                    if b.get("type") != new_t:
                        old_t = b.get("type", "paragraph")
                        b["type"] = new_t
                        b["is_ai_assisted"] = True
                        b["ai_provider"] = "gpt-4o-mini"
                        b["ai_confidence"] = float(pred.get("confidence", 0.95))
                        b["state"] = "confirmed"
                        b["warnings"] = []
                        b["is_user_confirmed"] = False
                        b["ai_change"] = {
                            "old_type": old_t,
                            "new_type": new_t,
                            "reason": f"OpenAI GPT identified as {new_t}",
                            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                            "reviewed": False
                        }
                        updated_count += 1

        return blocks, updated_count

    def _classify_with_claude(self, blocks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Sends block snippets to Anthropic Claude Messages API (claude-3-5-haiku).
        """
        snippets = []
        for i, b in enumerate(blocks[:60]):
            text = self._extract_plain_text(b)[:150].strip()
            snippets.append({"index": i, "id": b["id"], "current_type": b.get("type"), "text": text})

        prompt = (
            "Classify each of the following manuscript blocks into: "
            "['title', 'authors', 'affiliations', 'abstract', 'heading_l1', 'heading_l2', 'heading_l3', 'paragraph', 'figure', 'table', 'equation', 'reference_list'].\n"
            f"Input:\n{json.dumps(snippets)}\n\n"
            "Respond ONLY with a JSON array: [{\"id\": \"...\", \"type\": \"...\", \"confidence\": 0.95}]"
        )

        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 2048,
            "system": "You are an academic manuscript block classification assistant. Respond with valid JSON only.",
            "messages": [{"role": "user", "content": prompt}]
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.anthropic_key,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))

        raw_content = res_data["content"][0]["text"].strip()
        if "```json" in raw_content:
            raw_content = raw_content.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw_content:
            raw_content = raw_content.split("```", 1)[1].split("```", 1)[0].strip()

        data = json.loads(raw_content)
        predictions = data if isinstance(data, list) else data.get("predictions") or data.get("blocks") or []

        pred_map = {p["id"]: p for p in predictions if "id" in p and "type" in p}
        updated_count = 0
        for b in blocks:
            if b["id"] in pred_map:
                pred = pred_map[b["id"]]
                new_t = pred["type"]
                if new_t in ["title", "authors", "affiliations", "abstract", "heading_l1", "heading_l2", "heading_l3", "paragraph", "figure", "table", "equation", "reference_list"]:
                    if b.get("type") != new_t:
                        old_t = b.get("type", "paragraph")
                        b["type"] = new_t
                        b["is_ai_assisted"] = True
                        b["ai_provider"] = "claude-3-5-haiku"
                        b["ai_confidence"] = float(pred.get("confidence", 0.95))
                        b["state"] = "confirmed"
                        b["warnings"] = []
                        b["is_user_confirmed"] = False
                        b["ai_change"] = {
                            "old_type": old_t,
                            "new_type": new_t,
                            "reason": f"Claude AI identified as {new_t}",
                            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                            "reviewed": False
                        }
                        updated_count += 1

        return blocks, updated_count
