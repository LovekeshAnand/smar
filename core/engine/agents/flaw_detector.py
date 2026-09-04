"""
Nyaya AI Flaw Detector Agent
Runs rule-based + simulated LLM critique logic to intercept hallucinations and jurisdictional errors.
Outputs explicit structured JSON analytics.
"""
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from core.engine.critique_pass import CritiqueEngine

class FlawDetector:
    def __init__(self):
        self.base_critique = CritiqueEngine()

    def analyze_document(self, final_draft_text: str, source_context: str, document_type: str = "Bail Application") -> str:
        """
        Wraps the baseline factual critique logic and expands it into a JSON structure
        validating missing clauses, jurisdictional limits, and hallucination blocks.
        """
        # Baseline interception
        is_factually_grounded = self.base_critique.validate_draft(final_draft_text, source_context, document_type)
        
        flaws = []
        
        if not is_factually_grounded:
            flaws.append({
                "type": "Hallucinated Statute",
                "section": "Body Argument",
                "severity": "CRITICAL",
                "suggestion": "Draft contains a citation not mapped to the original facts. Engine halted output."
            })
            
        # Hardcoded structural checks (Simulating LLM flaw detection)
        if "jurisdiction" not in final_draft_text.lower() and "court" in final_draft_text.lower():
            flaws.append({
                "type": "Missing Jurisdiction Clause",
                "section": "Preamble",
                "severity": "HIGH",
                "suggestion": "Explicit statement of jurisdictional territory must be established."
            })
            
        if "BNS" not in final_draft_text and "IPC" in final_draft_text:
            flaws.append({
                "type": "Outdated Statute",
                "section": "Charges",
                "severity": "CRITICAL",
                "suggestion": "Replace all 1860 IPC references with BNS 2023 mapped counterparts."
            })
        
        # Check for outdated CrPC references (replaced by BNSS 2023)
        draft_lower = final_draft_text.lower()
        if "crpc" in draft_lower or "cr.p.c" in draft_lower or "code of criminal procedure" in draft_lower:
            if "bnss" not in draft_lower:
                flaws.append({
                    "type": "Outdated Procedural Code",
                    "section": "Procedural Framework",
                    "severity": "HIGH",
                    "suggestion": "Replace CrPC references with BNSS 2023. E.g., CrPC 439 -> BNSS 483 for bail."
                })
        
        if "evidence act" in draft_lower or "section 65b" in draft_lower:
            if "bharatiya sakshya" not in draft_lower and "bsa" not in draft_lower:
                flaws.append({
                    "type": "Outdated Evidence Law",
                    "section": "Evidence Citations",
                    "severity": "HIGH",
                    "suggestion": "Replace Indian Evidence Act 1872 references with Bharatiya Sakshya Adhiniyam (BSA) 2023."
                })

        # Check for repetitive endings (Repetition Bug)
        if len(final_draft_text) > 500:
            tail = final_draft_text[-600:]
            # Count occurrences of lines > 10 chars
            lines = [l.strip() for l in tail.split('\n') if len(l.strip()) > 10]
            if len(lines) > 3:
                from collections import Counter
                counts = Counter(lines)
                # If many lines repeat, it's a hallucination loop
                num_repeats = sum(1 for c in counts.values() if c > 1)
                if num_repeats >= 2:
                    flaws.append({
                        "type": "Repetitive Content",
                        "section": "Footer/Closing",
                        "severity": "MEDIUM",
                        "suggestion": "Document contains repetitive signature blocks or closing statements."
                    })

        result = {
            "is_valid_for_production": len([f for f in flaws if f["severity"] == "CRITICAL"]) == 0,
            "flaws": flaws
        }
        
        return json.dumps(result, indent=4)
