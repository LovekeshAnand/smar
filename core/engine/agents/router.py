"""
Nyaya AI Router - Zero-AI Task Classification & BNS Injection
Implements pure deterministic keyword heuristics to bypass expensive LLM token burns.
"""

import re
from typing import Dict, Any, List

# Indian Penal Code (1860) to Bharatiya Nyaya Sanhita (2023) Mapping Dictionary
IPC_TO_BNS_MAP = {
    "IPC 302": ("BNS 103", "Punishment for murder"),
    "IPC 376": ("BNS 63", "Punishment for rape"),
    "IPC 420": ("BNS 318", "Cheating and dishonestly inducing delivery of property"),
    "IPC 498A": ("BNS 85", "Cruelty by husband or relatives"),
    "IPC 304B": ("BNS 80", "Dowry death"),
    "IPC 307": ("BNS 109", "Attempt to murder"),
    "IPC 354": ("BNS 74", "Assault to outrage modesty of woman"),
    "IPC 379": ("BNS 303", "Punishment for theft"),
    "IPC 506": ("BNS 351", "Criminal intimidation"),
    "IPC 120B": ("BNS 61", "Criminal conspiracy")
}

CLASSIFICATION_KEYWORDS = {
    "LEGAL_DRAFT": ["draft", "petition", "agreement", "application", "notice", "fir", "writ", "file a case", "file a suit", "bail for", "quash", "case against"],
    "DOC_FLAW": ["flaw", "review", "check", "analyze", "missing clause", "validate", "critique"],
    "PDF_PARSE": ["parse", "extract", "read pdf", "scan", "ocr"],
}

COMPLEXITY_SIGNALS = {
    "constitutional": 4, "article 21": 4, "fundamental rights": 4, "jurisdiction": 4,
    "supreme court": 4, "high court": 4, "multi-state": 4,
    "multiple respondents": 3, "joint applicants": 3,
    "section 420": 2, "bns 318": 2, "crpc 439": 2, "murder": 2, "theft": 2, "assault": 2, "fir": 2,
    "rental": 1, "lease": 1, "deed": 1, "agreement": 1
}

class LegalRouter:
    def __init__(self):
        pass

    def detect_task_type(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        for task_type, keywords in CLASSIFICATION_KEYWORDS.items():
            if any(kw in prompt_lower for kw in keywords):
                return task_type
        return "LEGAL_QUERY" # Fallback

    def calculate_complexity(self, prompt: str) -> int:
        prompt_lower = prompt.lower()
        score = 0
        for signal, weight in COMPLEXITY_SIGNALS.items():
            if signal in prompt_lower:
                score += weight
        return min(score, 10) # Cap at 10

    def select_model_tier(self, complexity: int) -> str:
        if complexity <= 2:
            return "FAST (BitNet-2B)"
        elif complexity <= 6:
            return "BALANCED (Saul-7B)"
        else:
            return "DEEP (CPU-Fallback)"

    def detect_document_type(self, prompt: str) -> str:
        """Determines the exact legal instrument required based on context mapping."""
        prompt_lower = prompt.lower()
        if any(x in prompt_lower for x in ["bail", "release", "jail", "remand"]):
            return "Bail Application"
        elif any(x in prompt_lower for x in ["sue", "suit", "compensation", "damages", "civil", "recovery", "loan"]):
            return "Civil Suit"
        elif any(x in prompt_lower for x in ["fir", "complaint", "cyber", "hacked", "corrupted", "fraud", "case against", "report", "theft", "stolen", "murder"]):
            return "Criminal Complaint"
        return "Civil Suit" # Safest generic fallback for generic Drafting requests

    def inject_bns_mappings(self, prompt: str) -> Dict[str, Any]:
        """Scans for old IPC codes and enforces the new BNS 2023 standard."""
        mappings_found = []
        injected_notice = ""
        prompt_upper = prompt.upper()
        
        # Match: "IPC 302", "IPC Section 302", "Section 302 IPC", "Section 302", "IPC302"
        for ipc, (bns, desc) in IPC_TO_BNS_MAP.items():
            section_num = ipc.replace("IPC ", "")
            patterns = [
                ipc,                                    # IPC 420
                ipc.replace("IPC ", "IPC"),              # IPC420 (no space)
                f"IPC SECTION {section_num}",            # IPC Section 420
                f"SECTION {section_num} IPC",            # Section 420 IPC
                f"SECTION {section_num} OF IPC",         # Section 420 of IPC
                f"SECTION {section_num} OF THE IPC",     # Section 420 of the IPC
            ]
            
            # Robust matching: check for patterns in original and space-normalized prompt
            norm_prompt = prompt_upper.replace(" ", "").replace("SECTION", " SECTION")
            if any(p in norm_prompt or p in prompt_upper for p in patterns):
                if not any(m["ipc"] == ipc for m in mappings_found):  # dedupe
                    mappings_found.append({"ipc": ipc, "bns": bns, "offence": desc})
                
        if mappings_found:
            injected_notice = "\n[CRITICAL SYSTEM OVERRIDE: STATUTE UPDATE APPLIED]\n"
            for mapping in mappings_found:
                injected_notice += f"-> User referenced '{mapping['ipc']}'. By law (July 2024), apply '{mapping['bns']}' ({mapping['offence']}).\n"
        
        return {
            "mapped_prompt": prompt + "\n" + injected_notice if injected_notice else prompt,
            "mappings_found": mappings_found,
            "bns_injected_text": injected_notice
        }

    def route_request(self, prompt: str) -> Dict[str, Any]:
        """Complete deterministic routing hook taking < 1ms on CPU."""
        task_type = self.detect_task_type(prompt)
        complexity = self.calculate_complexity(prompt)
        tier = self.select_model_tier(complexity)
        doc_type = self.detect_document_type(prompt)
        mapping_data = self.inject_bns_mappings(prompt)
        
        return {
            "task_type": task_type,
            "complexity_score": complexity,
            "assigned_tier": tier,
            "document_type": doc_type,
            "final_prompt_payload": mapping_data["mapped_prompt"],
            "statute_corrections": mapping_data["mappings_found"]
        }