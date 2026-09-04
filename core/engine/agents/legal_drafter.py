"""
Nyaya AI Legal Drafter Engine
Embeds LLM outputs securely inside predefined Database LaTeX/Text templates
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from core.engine.db.database import SessionLocal
from core.engine.db.models import Template

class LegalDrafter:
    def __init__(self):
        # We spawn an ephemeral DB session exclusively during draft generation 
        # to pull the required DB structural letterheads securely.
        self.db = SessionLocal()
        
    def construct_draft(self, generated_llm_text: str, document_type: str, user_metadata: dict) -> str:
        """
        Pulls explicit template headnotes from the SQLite Database.
        Combines the extracted LLM text directly into the [DYNAMIC_BODY_CONTENT] slot, saving thousands of tokens.
        """
        # Retrieve strict template
        template_obj = self.db.query(Template).filter_by(document_type=document_type).first()
        
        # If DB lookup fails or template missing, use fallback
        if not template_obj:
            print(f"[WARN] No strict DB Template found for '{document_type}'. Initializing Hard Fallback Template...")
            
            if document_type == "Bail Application":
                base_layout = r"""<font size="16"><b>IN THE HON'BLE HIGH COURT OF [COURT_LOCATION] AT [COURT_CITY]</b></font>

<b><font size="14">CRIMINAL MISC. BAIL APPLICATION NO. _____ OF 2026</font></b>

<font size="12">(Under Section 483 of Bharatiya Nagarik Suraksha Sanhita, 2023)</font>

<b>----------</b>

<b>IN THE MATTER OF:</b>
[APPLICANT_NAME] [GENDER_PREFIX] [FATHER_NAME], R/o [ADDRESS]
... APPLICANT

<b>VERSUS</b>

[RESPONDENT_STATE]
... RESPONDENT

<b>----------</b>

<b><u><font size="14">APPLICATION FOR GRANT OF REGULAR BAIL</font></u></b>

<b>MOST RESPECTFULLY SHOWETH TO THE HON'BLE CHIEF JUSTICE AND HIS COMPANION JUDGES:</b>

[DYNAMIC_BODY_CONTENT]

<b>[ADVOCATE_NAME]</b>
ADVOCATE FOR APPLICANT
[BAR_COUNCIL_NO]

<b>VERIFICATION:</b>
I, [APPLICANT_NAME], the above-named Applicant, do hereby solemnly affirm and declare that the contents of this Bail Application are true and correct to the best of my knowledge, belief, and information, and nothing material has been concealed therefrom.

<b>DEPONENT / APPLICANT</b>"""
            elif document_type == "Criminal Complaint":
                base_layout = r"""<font size="16"><b>BEFORE THE COURT OF CHIEF METROPOLITAN MAGISTRATE, [COURT_CITY]</b></font>

<b><u><font size="12">APPLICATION UNDER SECTION 175(3) OF THE BHARATIYA NAGARIK SURAKSHA SANHITA (BNSS), 2023</font></u></b>

<b>IN THE MATTER OF:</b>

<b>COMPLAINANT:</b>
[APPLICANT_NAME],
R/o [ADDRESS]

<b>VERSUS</b>

<b>ACCUSED:</b>
[DEFENDANT_NAME],
[DEFENDANT_ADDRESS]

<b>----------</b>

<b><u><font size="14">[DYNAMIC_TITLE]</font></u></b>

<b>MOST RESPECTFULLY SHOWETH:</b>
[DYNAMIC_BODY_CONTENT]

<b>LIST OF ANNEXURES / DIGITAL EVIDENCE:</b>
1. Certified Bank Account Statements / Transaction Ledgers
2. Server Access Logs / Digital IP Traces
3. Certificate under Section 63 of Bharatiya Sakshya Adhiniyam, 2023 (Para-materia to legacy Sec 65B of Evidence Act) certifying digital logs

<b>[ADVOCATE_NAME]</b>
ADVOCATE FOR COMPLAINANT
[BAR_COUNCIL_NO]

<b>VERIFICATION:</b>
I, the above-named complainant, do hereby solemnly affirm and declare that the contents of this criminal complaint are true and correct based on personal knowledge, physical facts, and verified digital transaction records.
<br/><br/>
<b>DEPONENT / COMPLAINANT</b>"""
            else:
                base_layout = r"""<font size="16"><b>IN THE COURT OF THE DISTRICT JUDGE, [COURT_CITY]</b></font>

<b><font size="14">CIVIL SUIT NO. _____ OF 2026</font></b>

<b>IN THE MATTER OF:</b>

<b>PLAINTIFF:</b>
[APPLICANT_NAME],
R/o [ADDRESS] 

<b>VERSUS</b>

<b>DEFENDANT:</b>
[DEFENDANT_NAME],
R/o [DEFENDANT_ADDRESS]

<b>----------</b>

<b><u><font size="14">[DYNAMIC_TITLE]</font></u></b>

<b>MOST RESPECTFULLY SHOWETH:</b>
[DYNAMIC_BODY_CONTENT]

<b>VALUATION AND COURT FEE:</b>
The suit for the purpose of jurisdiction and court fee is valued at INR 5,00,00,000/- (Rupees Five Crores Only). The requisite ad-valorem court fee as per the Court Fees Act has been paid and affixed herewith.

<b>JURISDICTION:</b>
The cause of action arose substantially within the territorial limits of this Hon'ble Court upon the execution of the disputed instruments. Furthermore, the Defendant's primary registered corporate branches operate within this jurisdiction, thereby conferring absolute competency upon this Hon'ble Court under Section 20 of the Code of Civil Procedure, 1908.

<b>[ADVOCATE_NAME]</b>
ADVOCATE FOR PLAINTIFF
[BAR_COUNCIL_NO]

<b>LIST OF ANNEXURES:</b>
1. Original Copy of the Disputed Joint Development Agreement
2. Copies of Forged Board Resolutions / Electronic Correspondence
3. Certified Financial Transaction Ledgers
4. Application for Ex-Parte Interim Injunction (Order 39 CPC)

<b>VERIFICATION:</b>
Verified at [COURT_CITY] on this day that the contents of the above paragraphs are true and correct to the best of my knowledge, derived from physical records, and nothing material has been concealed therefrom.
<br/><br/>
<b>DEPONENT / PLAINTIFF</b>"""
        else:
            base_layout = template_obj.latex_content

        # Add explicit protection for DYNAMIC_TITLE if it was missing 
        if "DYNAMIC_TITLE" not in user_metadata:
             user_metadata["DYNAMIC_TITLE"] = "LEGAL DOCUMENT"

        
        # Mapping physical metadata replacements securely.
        # e.g., mapping [APPLICANT_NAME] to the actual data injected from User interface
        for key, value in user_metadata.items():
            slot_token = f"[{key.upper()}]"
            base_layout = base_layout.replace(slot_token, str(value))
            
        # Finally map the generated LLM text physics inside the layout
        final_draft = base_layout.replace("[DYNAMIC_BODY_CONTENT]", generated_llm_text)
        
        return final_draft

    def __del__(self):
        try:
            self.db.close()
        except:
            pass
