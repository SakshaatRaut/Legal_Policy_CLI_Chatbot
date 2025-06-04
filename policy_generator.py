import re
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from gdpr_parser import GDPRParser

class PrivacyPolicyGenerator:
    """
    A sophisticated privacy policy generator that creates legally compliant
    GDPR privacy policies based on company information and regulatory requirements.
    """
    
    def __init__(self, db_path="gdpr_knowledge_base.db"):
        """
        Initialize the privacy policy generator
        
        Args:
            db_path (str): Path to the GDPR knowledge base SQLite database
        """
        self.gdpr_reader = GDPRParser(db_path)
        self.company_info = {}
        self.policy_sections = {}
        self.current_question_index = 0
        self.load_questions()
        
    def load_questions(self):
        """Load the questions sequence for the policy generator"""
        self.questions = [
            {
                "id": "company_name",
                "question": "What is the name of your company?",
                "section": "data_controller",
                "required": True
            },
            {
                "id": "company_address",
                "question": "What is your company's registered address?",
                "section": "data_controller",
                "required": True
            },
            {
                "id": "company_contact_email",
                "question": "What email address should users contact for privacy-related inquiries?",
                "section": "data_controller",
                "required": True
            },
            {
                "id": "company_contact_phone",
                "question": "What phone number should users call for privacy-related inquiries? (Optional)",
                "section": "data_controller",
                "required": False
            },
            {
                "id": "has_dpo",
                "question": "Have you appointed a Data Protection Officer (DPO)?",
                "section": "dpo_info",
                "required": True,
                "options": ["Yes", "No"],
                "branch": {
                    "Yes": ["dpo_name", "dpo_contact"],
                    "No": ["dpo_alternative"]
                }
            },
            {
                "id": "dpo_name",
                "question": "What is the name of your Data Protection Officer?",
                "section": "dpo_info",
                "required": True,
                "condition": "has_dpo == 'Yes'"
            },
            {
                "id": "dpo_contact",
                "question": "What is the contact email for your Data Protection Officer?",
                "section": "dpo_info",
                "required": True,
                "condition": "has_dpo == 'Yes'"
            },
            {
                "id": "dpo_alternative",
                "question": "Who in your organization is responsible for data protection matters?",
                "section": "dpo_info",
                "required": True,
                "condition": "has_dpo == 'No'"
            },
            {
                "id": "data_collected",
                "question": "What types of personal data does your website/service collect? (Select all that apply)",
                "section": "processing_purposes",
                "required": True,
                "multi_select": True,
                "options": [
                    "Name",
                    "Email address",
                    "Phone number",
                    "Address",
                    "Date of birth",
                    "Payment information",
                    "IP address",
                    "Browser type",
                    "Device information",
                    "Location data",
                    "Cookies",
                    "Usage data",
                    "Special categories of personal data", 
                    "Other"
                ],
                "branch": {
                    "Special categories of personal data": ["special_data_details"],
                    "Other": ["other_data_collected"]
                }
            },
            {
                "id": "special_data_details",
                "question": "Please specify which special categories of personal data you collect (e.g., health data, biometric data, racial or ethnic origin):",
                "section": "processing_purposes",
                "required": True,
                "condition": "'Special categories of personal data' in data_collected"
            },
            {
                "id": "other_data_collected",
                "question": "Please specify what other types of personal data you collect:",
                "section": "processing_purposes",
                "required": True,
                "condition": "'Other' in data_collected"
            },
            {
                "id": "processing_purposes_list",
                "question": "For what purposes do you process personal data? (Select all that apply)",
                "section": "processing_purposes",
                "required": True,
                "multi_select": True,
                "options": [
                    "To provide and maintain our service",
                    "To notify about changes to our service",
                    "To allow participation in interactive features",
                    "To provide customer support",
                    "To gather analysis or valuable information",
                    "To process payments",
                    "To deliver advertisements",
                    "To detect, prevent and address technical issues",
                    "To send newsletters",
                    "To communicate about new products or services",
                    "To comply with legal obligations",
                    "Other"
                ],
                "branch": {
                    "Other": ["other_processing_purposes"]
                }
            },
            {
                "id": "other_processing_purposes",
                "question": "Please specify what other purposes you process personal data for:",
                "section": "processing_purposes",
                "required": True,
                "condition": "'Other' in processing_purposes_list"
            },
            {
                "id": "legal_basis",
                "question": "What is your legal basis for processing personal data? (Select all that apply)",
                "section": "processing_purposes",
                "required": True,
                "multi_select": True,
                "options": [
                    "Consent",
                    "Performance of a contract",
                    "Compliance with a legal obligation",
                    "Protection of vital interests",
                    "Public interest",
                    "Legitimate interests"
                ],
                "branch": {
                    "Legitimate interests": ["legitimate_interests_details"]
                }
            },
            {
                "id": "legitimate_interests_details",
                "question": "Please describe your legitimate interests for processing personal data:",
                "section": "legitimate_interests",
                "required": True,
                "condition": "'Legitimate interests' in legal_basis"
            },
            {
                "id": "data_sharing",
                "question": "Do you share personal data with third parties?",
                "section": "recipients",
                "required": True,
                "options": ["Yes", "No"],
                "branch": {
                    "Yes": ["third_party_categories"]
                }
            },
            {
                "id": "third_party_categories",
                "question": "What categories of third parties do you share data with? (Select all that apply)",
                "section": "recipients",
                "required": True,
                "multi_select": True,
                "condition": "data_sharing == 'Yes'",
                "options": [
                    "Service providers",
                    "Payment processors",
                    "Analytics providers",
                    "Advertising partners",
                    "Business partners",
                    "Affiliates",
                    "Cloud service providers",
                    "Legal authorities",
                    "Other"
                ],
                "branch": {
                    "Other": ["other_third_parties"]
                }
            },
            {
                "id": "third_party_purpose",
                "question": "For what purposes do you share data with third parties?",
                "section": "recipients",
                "required": True,
                "condition": "data_sharing == 'Yes'"
            },
            {
                "id": "other_third_parties",
                "question": "Please specify what other categories of third parties you share data with:",
                "section": "recipients",
                "required": True,
                "condition": "data_sharing == 'Yes' and 'Other' in third_party_categories"
            },
            {
                "id": "international_transfers",
                "question": "Do you transfer personal data to countries outside the EU/EEA?",
                "section": "transfers",
                "required": True,
                "options": ["Yes", "No"],
                "branch": {
                    "Yes": ["transfer_countries", "transfer_safeguards"]
                }
            },
            {
                "id": "transfer_countries",
                "question": "To which countries outside the EU/EEA do you transfer personal data?",
                "section": "transfers",
                "required": True,
                "condition": "international_transfers == 'Yes'"
            },
            {
                "id": "transfer_safeguards",
                "question": "What safeguards do you have in place for these international transfers? (Select all that apply)",
                "section": "transfers",
                "required": True,
                "multi_select": True,
                "condition": "international_transfers == 'Yes'",
                "options": [
                    "Standard Contractual Clauses (SCCs)",
                    "Binding Corporate Rules (BCRs)",
                    "Adequacy decision by the European Commission",
                    "Derogations for specific situations under Article 49",
                    "Explicit Consent",
                    "Other"
                ],
                "branch": {
                    "Other": ["other_safeguards"]
                }
            },
            {
                "id": "other_safeguards",
                "question": "Please specify what other safeguards you have for international transfers:",
                "section": "transfers",
                "required": True,
                "condition": "international_transfers == 'Yes' and 'Other' in transfer_safeguards"
            },
            {
                "id": "retention_period",
                "question": "How long do you retain personal data?",
                "section": "retention_period",
                "required": True,
                "options": [
                    "For the duration of the user account",
                    "For a specific time period",
                    "Until the purpose is fulfilled",
                    "As required by law",
                    "According to data minimization principles",
                    "Other"
                ],
                "branch": {
                    "For a specific time period": ["specific_retention_period"],
                    "Other": ["other_retention_period"]
                }
            },
            {
                "id": "specific_retention_period",
                "question": "Please specify the time period for which you retain personal data:",
                "section": "retention_period",
                "required": True,
                "condition": "retention_period == 'For a specific time period'"
            },
            {
                "id": "other_retention_period",
                "question": "Please specify your data retention criteria:",
                "section": "retention_period",
                "required": True,
                "condition": "retention_period == 'Other'"
            },
            {
                "id": "data_security",
                "question": "What security measures do you implement to protect personal data? (Select all that apply)",
                "section": "security_measures",
                "required": True,
                "multi_select": True,
                "options": [
                    "Encryption",
                    "Pseudonymization",
                    "Access controls",
                    "Regular security assessments",
                    "Data backup procedures",
                    "Staff training on data protection",
                    "Incident response plans",
                    "Other"
                ],
                "branch": {
                    "Other": ["other_security_measures"]
                }
            },
            {
                "id": "other_security_measures",
                "question": "Please specify what other security measures you implement:",
                "section": "security_measures",
                "required": True,
                "condition": "'Other' in data_security"
            },
            {
                "id": "automated_processing",
                "question": "Do you use automated decision-making or profiling?",
                "section": "automated_decision_making",
                "required": True,
                "options": ["Yes", "No"],
                "branch": {
                    "Yes": ["automated_processing_details", "automated_processing_safeguards"]
                }
            },
            {
                "id": "automated_processing_details",
                "question": "Please describe your automated decision-making or profiling processes:",
                "section": "automated_decision_making",
                "required": True,
                "condition": "automated_processing == 'Yes'"
            },
            {
                "id": "automated_processing_safeguards",
                "question": "What safeguards do you implement for automated decision-making?",
                "section": "automated_decision_making",
                "required": True,
                "condition": "automated_processing == 'Yes'"
            },
            {
                "id": "data_breach",
                "question": "Do you have procedures in place for handling personal data breaches?",
                "section": "data_breach",
                "required": True,
                "options": ["Yes", "No"],
                "branch": {
                    "Yes": ["data_breach_procedures"]
                }
            },
            {
                "id": "data_breach_procedures",
                "question": "Please describe your procedures for handling personal data breaches:",
                "section": "data_breach",
                "required": True,
                "condition": "data_breach == 'Yes'"
            },
            {
                "id": "uses_cookies",
                "question": "Does your website use cookies or similar tracking technologies?",
                "section": "cookies",
                "required": True,
                "options": ["Yes", "No"],
                "branch": {
                    "Yes": ["cookie_types", "cookie_duration"]
                }
            },
            {
                "id": "cookie_types",
                "question": "What types of cookies does your website use? (Select all that apply)",
                "section": "cookies",
                "required": True,
                "multi_select": True,
                "condition": "uses_cookies == 'Yes'",
                "options": [
                    "Essential/Necessary cookies",
                    "Preference/Functionality cookies",
                    "Statistics/Analytics cookies",
                    "Marketing/Advertising cookies",
                    "Social media cookies",
                    "Other"
                ],
                "branch": {
                    "Other": ["other_cookie_types"]
                }
            },
            {
                "id": "cookie_duration",
                "question": "How long are cookies stored on users' devices?",
                "section": "cookies",
                "required": True,
                "condition": "uses_cookies == 'Yes'"
            },
            {
                "id": "other_cookie_types",
                "question": "Please specify what other types of cookies your website uses:",
                "section": "cookies",
                "required": True,
                "condition": "uses_cookies == 'Yes' and 'Other' in cookie_types"
            },
            {
                "id": "children_data",
                "question": "Do you knowingly collect data from children under 16?",
                "section": "children_data",
                "required": True,
                "options": ["Yes", "No"],
                "branch": {
                    "Yes": ["children_data_safeguards"]
                }
            },
            {
                "id": "children_data_safeguards",
                "question": "What safeguards do you implement when processing children's data?",
                "section": "children_data",
                "required": True,
                "condition": "children_data == 'Yes'"
            },
            {
                "id": "supervisory_authority",
                "question": "Which supervisory authority is relevant for your company?",
                "section": "complaint_authority",
                "required": True,
                "options": [
                    "I'll provide the details",
                    "I don't know"
                ],
                "branch": {
                    "I'll provide the details": ["authority_details"]
                }
            },
            {
                "id": "authority_details",
                "question": "Please provide the name and contact details of the relevant supervisory authority:",
                "section": "complaint_authority",
                "required": True,
                "condition": "supervisory_authority == 'I\\'ll provide the details'"
            },
            {
                "id": "website_url",
                "question": "What is your website URL?",
                "section": "general",
                "required": True
            },
            {
                "id": "effective_date",
                "question": "When should this privacy policy take effect? (YYYY-MM-DD, leave blank for today's date)",
                "section": "general",
                "required": False
            }
        ]
    
    def get_next_question(self):
        """
        Get the next question based on previous answers
        
        Returns:
            dict: Question information or None if no more questions
        """
        if self.current_question_index >= len(self.questions):
            return None
        
        question = self.questions[self.current_question_index]
        
        # Check if this question should be skipped based on conditions
        if "condition" in question:
            condition = question["condition"]
            if not self._evaluate_condition(condition):
                self.current_question_index += 1
                return self.get_next_question()
        
        return question
    
    def _evaluate_condition(self, condition):
        """
        Evaluate a condition string based on previous answers
        
        Args:
            condition (str): Condition string to evaluate
            
        Returns:
            bool: Whether the condition is true
        """
        # Replace variable names with their values
        for key, value in self.company_info.items():
            if isinstance(value, str):
                condition = condition.replace(key, f"'{value}'")
            elif isinstance(value, list):
                condition = condition.replace(key, f"{value}")
            else:
                condition = condition.replace(key, f"{value}")
        
        try:
            return eval(condition)
        except:
            return False
    
    def process_answer(self, answer):
        """
        Process an answer to the current question
        
        Args:
            answer: The answer provided by the user
            
        Returns:
            tuple: (next_question, follow_up_message)
        """
        current_question = self.questions[self.current_question_index]
        question_id = current_question["id"]
        
        # Store the answer
        self.company_info[question_id] = answer
        
        # Add to the appropriate section
        section_name = current_question["section"]
        if section_name not in self.policy_sections:
            self.policy_sections[section_name] = {}
        self.policy_sections[section_name][question_id] = answer
        
        # Check for branching logic
        follow_up_message = None
        if isinstance(answer, list):
            if len(answer) == 1:
                answer = answer[0]  # Convert single-item list to a string or number
            else:
                answer = tuple(answer)  # Convert multi-item list to a tuple
        if "branch" in current_question and answer in current_question["branch"]:
            # Nothing to do here, as we'll handle this through the condition checks
            pass
            
        # Move to the next question
        self.current_question_index += 1
        next_question = self.get_next_question()
        
        return next_question, follow_up_message
    
    def format_question(self, question):
        """
        Format a question for presentation
        
        Args:
            question (dict): Question information
            
        Returns:
            str: Formatted question
        """
        message = question["question"]
        
        if "options" in question:
            if question.get("multi_select", False):
                message += "\n\nSelect all that apply:"
                for option in question["options"]:
                    message += f"\n- {option}"
            else:
                message += "\n\nOptions:"
                for option in question["options"]:
                    message += f"\n- {option}"
        
        if not question.get("required", True):
            message += "\n\n(Optional)"
        
        return message
    
    def validate_answer(self, question, answer):
        """
        Validate an answer to a question
        
        Args:
            question (dict): Question information
            answer: The answer provided by the user
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if question.get("required", True) and not answer:
            return False, "This field is required."
        
        if "options" in question:
            if question.get("multi_select", False):
                if not isinstance(answer, list):
                    # Try to convert to list
                    try:
                        answer = [a.strip() for a in answer.split(",")]
                    except:
                        return False, "Please select one or more options."
                
                valid_options = set(question["options"])
                if not all(option in valid_options for option in answer):
                    return False, "Please select only from the available options."
            else:
                if answer not in question["options"]:
                    return False, "Please select one of the available options."
        
        if question["id"] == "effective_date" and answer:
            try:
                datetime.strptime(answer, "%Y-%m-%d")
            except ValueError:
                return False, "Please enter a valid date in YYYY-MM-DD format."
        
        return True, ""
    
    def _format_list_items(self, items, format_type="bullet"):
        """
        Format a list of items for inclusion in the policy
        
        Args:
            items (list): List of items to format
            format_type (str): Type of formatting to apply ('bullet', 'numbered', or 'paragraph')
            
        Returns:
            list: List of formatted strings
        """
        formatted = []
        
        if format_type == "bullet":
            for item in items:
                formatted.append(f"- {item}")
        elif format_type == "numbered":
            for i, item in enumerate(items, 1):
                formatted.append(f"{i}. {item}")
        elif format_type == "paragraph":
            formatted = [", ".join(items) + "."]
        
        return formatted
    
    def generate_privacy_policy(self):
        """
        Generate a GDPR-compliant privacy policy based on the collected information
        
        Returns:
            str: The generated privacy policy
        """
        policy = []
        
        # Add title and introduction
        company_name = self.company_info.get("company_name", "Our Company")
        website_url = self.company_info.get("website_url", "our website")
        
        effective_date = self.company_info.get("effective_date", "")
        if not effective_date:
            effective_date = datetime.now().strftime("%Y-%m-%d")
        
        policy.append(f"# PRIVACY POLICY")
        policy.append(f"## {company_name}")
        policy.append(f"*Last Updated: {effective_date}*")
        policy.append("")
        
        # Introduction
        policy.append(f"## 1. INTRODUCTION")
        policy.append(f"{company_name} (hereinafter referred to as 'we', 'us', 'our', or 'the Company') is committed to protecting and respecting your privacy. This Privacy Policy (together with our Terms of Use and any other documents referred to therein) sets out the basis on which any personal data we collect from you, or that you provide to us, will be processed by us.")
        policy.append("")
        
        policy.append(f"This Privacy Policy applies to the personal data collected, processed, and stored by us through our website located at {website_url} and any related services, features, functions, software, applications, websites, or content offered by us (collectively, the 'Service').")
        policy.append("")
        
        policy.append(f"Please read the following carefully to understand our views and practices regarding your personal data and how we will treat it. By accessing or using our Service, you acknowledge that you have read, understood, and agree to the practices described in this Privacy Policy.")
        policy.append("")
        
        # Data Controller Information
        policy.append("## 2. DATA CONTROLLER INFORMATION")
        policy.append(f"For the purposes of the General Data Protection Regulation (EU) 2016/679 ('GDPR'), the data controller is:")
        policy.append(f"{company_name}")
        policy.append(f"{self.company_info.get('company_address', '')}")
        policy.append("")
        policy.append(f"For any questions or concerns regarding this Privacy Policy or our data practices, please contact us at:")
        policy.append(f"Email: {self.company_info.get('company_contact_email', '')}")
        
        if self.company_info.get('company_contact_phone'):
            policy.append(f"Telephone: {self.company_info.get('company_contact_phone')}")
        
        policy.append("")
        
        # Data Protection Officer
        policy.append("## 3. DATA PROTECTION OFFICER")
        
        if self.company_info.get('has_dpo') == 'Yes':
            policy.append(f"In accordance with Article 37 of the GDPR, we have appointed a Data Protection Officer ('DPO') who is responsible for overseeing questions in relation to this Privacy Policy and our compliance with data protection laws. The DPO can be contacted as follows:")
            policy.append(f"Name: {self.company_info.get('dpo_name', '')}")
            policy.append(f"Email: {self.company_info.get('dpo_contact', '')}")
        else:
            policy.append(f"We have not appointed a Data Protection Officer as we are not required to do so under Article 37 of the GDPR. However, we have designated the following individual(s) as responsible for ensuring our compliance with applicable data protection laws:")
            policy.append(f"{self.company_info.get('dpo_alternative', '')}")
        
        policy.append("")
        
        # Personal Data Collection
        policy.append("## 4. PERSONAL DATA WE COLLECT")
        
        data_collected = self.company_info.get('data_collected', [])
        if isinstance(data_collected, str):
            data_collected = [data_collected]
        
        policy.append("### 4.1 Categories of Personal Data")
        policy.append("We may collect, use, store, and transfer different kinds of personal data about you, which we have categorized as follows:")
        
        for data_type in data_collected:
            if data_type != 'Other' and data_type != 'Special categories of personal data':
                policy.append(f"- **{data_type}**")
        
        if 'Special categories of personal data' in data_collected and self.company_info.get('special_data_details'):
            policy.append("")
            policy.append("### 4.2 Special Categories of Personal Data")
            policy.append(f"In accordance with Article 9 of the GDPR, we also collect, process, and/or store the following special categories of personal data:")
            policy.append(f"{self.company_info.get('special_data_details')}")
            policy.append("")
            policy.append(f"We only process these special categories of personal data where we have obtained your explicit consent or where another legal basis under Article 9(2) of the GDPR applies.")
        
        if 'Other' in data_collected and self.company_info.get('other_data_collected'):
            policy.append("")
            policy.append("### 4.3 Other Personal Data")
            policy.append(f"Additionally, we may collect and process the following personal data:")
            policy.append(f"- {self.company_info.get('other_data_collected')}")
        
        policy.append("")
        
        # Processing Purposes
        policy.append("## 5. PURPOSE AND LEGAL BASIS FOR PROCESSING")
        
        purposes = self.company_info.get('processing_purposes_list', [])
        if isinstance(purposes, str):
            purposes = [purposes]
        
        policy.append("### 5.1 Purposes of Processing")
        policy.append("We have collected and process your personal data for the following purposes:")
        
        for purpose in purposes:
            if purpose != 'Other':
                policy.append(f"- {purpose}")
        
        if 'Other' in purposes and self.company_info.get('other_processing_purposes'):
            policy.append(f"- {self.company_info.get('other_processing_purposes')}")
        
        policy.append("")
        
        # Legal Basis
        policy.append("### 5.2 Legal Basis for Processing")
        
        legal_bases = self.company_info.get('legal_basis', [])
        if isinstance(legal_bases, str):
            legal_bases = [legal_bases]
        
        policy.append("We process your personal data in accordance with Article 6 of the GDPR on the following legal grounds:")
        
        if 'Consent' in legal_bases:
            policy.append("- **Consent**: You have given us your consent to process your personal data for one or more specific purposes.")
        
        if 'Performance of a contract' in legal_bases:
            policy.append("- **Performance of a Contract**: Processing is necessary for the performance of a contract to which you are a party or to take steps at your request prior to entering into a contract.")
        
        if 'Compliance with a legal obligation' in legal_bases:
            policy.append("- **Legal Obligation**: Processing is necessary for compliance with a legal obligation to which we are subject.")
        
        if 'Protection of vital interests' in legal_bases:
            policy.append("- **Vital Interests**: Processing is necessary to protect your vital interests or those of another natural person.")
        
        if 'Public interest' in legal_bases:
            policy.append("- **Public Interest**: Processing is necessary for the performance of a task carried out in the public interest or in the exercise of official authority vested in us.")
        
        if 'Legitimate interests' in legal_bases:
            policy.append("- **Legitimate Interests**: Processing is necessary for the purposes of our legitimate interests or those of a third party, except where such interests are overridden by your interests or fundamental rights and freedoms.")
        
        policy.append("")
        
        # Legitimate Interests section if applicable
        if 'Legitimate interests' in legal_bases:
            policy.append("### 5.3 Our Legitimate Interests")
            policy.append(f"Where we rely on legitimate interests as a legal basis for processing, our legitimate interests include:")
            policy.append(f"{self.company_info.get('legitimate_interests_details', '')}")
            policy.append("")
            policy.append("We have carefully considered and balanced our legitimate interests against your interests, fundamental rights, and freedoms. We believe that our processing on this basis is proportionate, necessary, and does not unduly impact your rights.")
            policy.append("")
        
        # Data Sharing
        policy.append("## 6. DISCLOSURES OF YOUR PERSONAL DATA")
        
        if self.company_info.get('data_sharing') == 'Yes':
            policy.append("### 6.1 Categories of Recipients")
            policy.append("We may share your personal data with the following categories of recipients:")
            
            third_parties = self.company_info.get('third_party_categories', [])
            if isinstance(third_parties, str):
                third_parties = [third_parties]
            
            for party in third_parties:
                if party != 'Other':
                    policy.append(f"- **{party}**")
            
            if 'Other' in third_parties and self.company_info.get('other_third_parties'):
                policy.append(f"- {self.company_info.get('other_third_parties')}")
                
            policy.append("")
            policy.append("### 6.2 Purpose of Sharing")
            policy.append(f"We share your personal data with these third parties for the following purposes:")
            policy.append(f"{self.company_info.get('third_party_purpose', '')}")
            policy.append("")
            policy.append("We require all third parties to respect the security of your personal data and to treat it in accordance with the law. We do not allow our third-party service providers to use your personal data for their own purposes and only permit them to process your personal data for specified purposes and in accordance with our instructions.")
            
        else:
            policy.append("We do not share your personal data with third parties except where required by law or as otherwise specified in this Privacy Policy.")
        
        policy.append("")
        
        # International Transfers
        policy.append("## 7. INTERNATIONAL TRANSFERS")
        
        if self.company_info.get('international_transfers') == 'Yes':
            policy.append(f"We transfer your personal data to the following countries outside the European Economic Area (EEA):")
            policy.append(f"{self.company_info.get('transfer_countries', '')}")
            policy.append("")
            policy.append("### 7.1 Safeguards for International Transfers")
            policy.append("To ensure that your personal data receives an adequate level of protection when transferred outside the EEA, we have put in place the following appropriate safeguards:")
            
            safeguards = self.company_info.get('transfer_safeguards', [])
            if isinstance(safeguards, str):
                safeguards = [safeguards]
            
            for safeguard in safeguards:
                if safeguard != 'Other':
                    policy.append(f"- **{safeguard}**")
            
            if 'Other' in safeguards and self.company_info.get('other_safeguards'):
                policy.append(f"- {self.company_info.get('other_safeguards')}")
            
            policy.append("")
            policy.append("You may obtain a copy of these safeguards by contacting us using the details provided in Section 2 of this Privacy Policy.")
        else:
            policy.append("We do not transfer your personal data outside the European Economic Area (EEA).")
        
        policy.append("")
        
        # Data Retention
        policy.append("## 8. DATA RETENTION")
        
        retention_period = self.company_info.get('retention_period', '')
        
        policy.append("### 8.1 Retention Period")
        policy.append("We will only retain your personal data for as long as necessary to fulfill the purposes for which we collected it, including for the purposes of satisfying any legal, accounting, or reporting requirements.")
        policy.append("")
        
        if retention_period == 'For a specific time period':
            policy.append(f"We retain your personal data for {self.company_info.get('specific_retention_period', '')}.")
        elif retention_period == 'For the duration of the user account':
            policy.append("We retain your personal data for the duration of your user account with us. If you delete your account, we will delete or anonymize your personal data within a reasonable time period, unless required to retain it by law.")
        elif retention_period == 'Until the purpose is fulfilled':
            policy.append("We retain your personal data only until the purpose for which we collected it is fulfilled. Once the purpose is fulfilled, we will delete or anonymize your personal data, unless required to retain it by law.")
        elif retention_period == 'As required by law':
            policy.append("We retain your personal data for the period required by applicable law. Different types of personal data may be subject to different retention periods in accordance with legal requirements.")
        elif retention_period == 'According to data minimization principles':
            policy.append("We apply data minimization principles and regularly review and delete personal data that is no longer necessary for the purposes for which it was collected.")
        elif retention_period == 'Other' and self.company_info.get('other_retention_period'):
            policy.append(f"{self.company_info.get('other_retention_period')}")
        
        policy.append("")
        policy.append("### 8.2 Criteria for Determining Retention")
        policy.append("To determine the appropriate retention period for personal data, we consider:")
        policy.append("- The amount, nature, and sensitivity of the personal data")
        policy.append("- The potential risk of harm from unauthorized use or disclosure of your personal data")
        policy.append("- The purposes for which we process your personal data and whether we can achieve those purposes through other means")
        policy.append("- The applicable legal, regulatory, tax, accounting, or other requirements")
        
        policy.append("")
        
        # Data Security
        policy.append("## 9. DATA SECURITY")
        
        policy.append("We have implemented appropriate technical and organizational measures to ensure a level of security appropriate to the risk of processing your personal data, including:")
        
        security_measures = self.company_info.get('data_security', [])
        if isinstance(security_measures, str):
            security_measures = [security_measures]
        
        for measure in security_measures:
            if measure != 'Other':
                policy.append(f"- {measure}")
        
        if 'Other' in security_measures and self.company_info.get('other_security_measures'):
            policy.append(f"- {self.company_info.get('other_security_measures')}")
        
        policy.append("")
        policy.append("We have procedures in place to deal with any suspected personal data breach and will notify you and any applicable regulator of a breach where we are legally required to do so.")
        
        policy.append("")
        
        # Data Breach Procedures
        if self.company_info.get('data_breach') == 'Yes':
            policy.append("### 9.1 Data Breach Procedures")
            policy.append(f"{self.company_info.get('data_breach_procedures', '')}")
            policy.append("")
        
        # Your Rights
        policy.append("## 10. YOUR LEGAL RIGHTS")
        
        policy.append("Under the GDPR, you have the following rights in relation to your personal data:")
        
        policy.append("1. **Right of access**: You have the right to request a copy of the personal data we hold about you.")
        policy.append("2. **Right to rectification**: You have the right to request correction of any inaccurate personal data we hold about you.")
        policy.append("3. **Right to erasure**: You have the right to request erasure of your personal data in certain circumstances.")
        policy.append("4. **Right to restriction of processing**: You have the right to request the restriction of processing of your personal data in certain circumstances.")
        policy.append("5. **Right to data portability**: You have the right to receive the personal data you have provided to us in a structured, commonly used, and machine-readable format.")
        policy.append("6. **Right to object**: You have the right to object to the processing of your personal data in certain circumstances, including processing based on legitimate interests and direct marketing.")
        policy.append("7. **Right to withdraw consent**: Where we rely on your consent as the legal basis for processing, you have the right to withdraw your consent at any time.")
        policy.append("8. **Right to lodge a complaint**: You have the right to lodge a complaint with a supervisory authority.")
        
        policy.append("")
        policy.append("### 10.1 How to Exercise Your Rights")
        policy.append("To exercise any of these rights, please contact us using the details provided in Section 2 of this Privacy Policy. We will respond to your request within one month of receiving it. Please note that we may need to verify your identity before processing your request.")
        
        policy.append("")
        policy.append("### 10.2 No Fee Usually Required")
        policy.append("You will not have to pay a fee to access your personal data (or to exercise any of the other rights). However, we may charge a reasonable fee if your request is clearly unfounded, repetitive, or excessive. Alternatively, we could refuse to comply with your request in these circumstances.")
        
        policy.append("")
        
        # Automated Decision Making
        policy.append("## 11. AUTOMATED DECISION-MAKING AND PROFILING")
        
        if self.company_info.get('automated_processing') == 'Yes':
            policy.append("We use automated decision-making and/or profiling in relation to your personal data.")
            policy.append("")
            policy.append("### 11.1 Details of Automated Processing")
            policy.append(f"{self.company_info.get('automated_processing_details', '')}")
            policy.append("")
            policy.append("### 11.2 Safeguards")
            policy.append("In accordance with Articles 22(3) and 22(4) of the GDPR, we implement suitable safeguards, including:")
            policy.append(f"{self.company_info.get('automated_processing_safeguards', '')}")
            policy.append("")
            policy.append("You have the right to obtain human intervention, express your point of view, and contest any decision based solely on automated processing that produces legal effects concerning you or similarly significantly affects you.")
        else:
            policy.append("We do not use automated decision-making, including profiling, in a way that produces legal effects concerning you or similarly significantly affects you.")
        
        policy.append("")
        
        # Cookies
        policy.append("## 12. COOKIES AND SIMILAR TECHNOLOGIES")
        
        if self.company_info.get('uses_cookies') == 'Yes':
            policy.append("Our website uses cookies and similar tracking technologies to distinguish you from other users of our website. This helps us to provide you with a good experience when you browse our website and also allows us to improve our site.")
            policy.append("")
            
            policy.append("### 12.1 What Are Cookies")
            policy.append("Cookies are small text files that are stored on your computer or mobile device when you visit a website. They allow the website to recognize your device and remember if you have been to the website before.")
            policy.append("")
            
            policy.append("### 12.2 Types of Cookies We Use")
            
            cookie_types = self.company_info.get('cookie_types', [])
            if isinstance(cookie_types, str):
                cookie_types = [cookie_types]
            
            for cookie_type in cookie_types:
                if cookie_type == 'Essential/Necessary cookies':
                    policy.append("- **Essential/Necessary cookies**: These are cookies that are required for the operation of our website. They include, for example, cookies that enable you to log into secure areas of our website.")
                elif cookie_type == 'Preference/Functionality cookies':
                    policy.append("- **Preference/Functionality cookies**: These allow our website to remember choices you make (such as your user name, language, or the region you are in) and provide enhanced, more personal features.")
                elif cookie_type == 'Statistics/Analytics cookies':
                    policy.append("- **Statistics/Analytics cookies**: These allow us to recognize and count the number of visitors and to see how visitors move around our website when they are using it. This helps us to improve the way our website works, for example, by ensuring that users are finding what they are looking for easily.")
                elif cookie_type == 'Marketing/Advertising cookies':
                    policy.append("- **Marketing/Advertising cookies**: These are used to deliver advertisements more relevant to you and your interests. They are also used to limit the number of times you see an advertisement as well as help measure the effectiveness of the advertising campaign.")
                elif cookie_type == 'Social media cookies':
                    policy.append("- **Social media cookies**: These cookies allow you to share our website content on social media platforms and interact with our content on those platforms.")
            
            if 'Other' in cookie_types and self.company_info.get('other_cookie_types'):
                policy.append(f"- **Other cookies**: {self.company_info.get('other_cookie_types')}")
            
            policy.append("")
            policy.append("### 12.3 Duration of Cookies")
            policy.append(f"{self.company_info.get('cookie_duration', '')}")
            
            policy.append("")
            policy.append("### 12.4 Managing Cookies")
            policy.append("Most web browsers allow you to manage your cookie preferences. You can set your browser to refuse cookies, or to alert you when cookies are being sent. The Help function within your browser should tell you how.")
            policy.append("")
            policy.append("Please note that if you disable or refuse cookies, some parts of our website may become inaccessible or not function properly.")
        else:
            policy.append("Our website does not use cookies or similar tracking technologies.")
        
        policy.append("")
        
        # Children's Data
        policy.append("## 13. CHILDREN'S DATA")
        
        if self.company_info.get('children_data') == 'Yes':
            policy.append("Our Service may be used by children under the age of 16. We knowingly collect personal data from children under 16 years of age.")
            policy.append("")
            policy.append("### 13.1 Safeguards for Children's Data")
            policy.append("In accordance with Article 8 of the GDPR, we implement the following safeguards when processing children's data:")
            policy.append(f"{self.company_info.get('children_data_safeguards', '')}")
            policy.append("")
            policy.append("If you are a parent or guardian and you believe that your child has provided us with personal data without your consent, please contact us using the details provided in Section 2 of this Privacy Policy.")
        else:
            policy.append("Our Service is not intended for children under 16 years of age, and we do not knowingly collect personal data from children under 16. If we learn that we have collected personal data from a child under 16 without verification of parental consent, we will take steps to delete that information.")
        
        policy.append("")
        
        # Complaints to Supervisory Authority
        policy.append("## 14. COMPLAINTS TO SUPERVISORY AUTHORITY")
        
        if self.company_info.get('supervisory_authority') == "I'll provide the details":
            authority_details = self.company_info.get('authority_details', '')
            policy.append(f"You have the right to lodge a complaint with a supervisory authority if you believe that our processing of your personal data infringes data protection laws. The relevant supervisory authority is:")
            policy.append(f"{authority_details}")
        else:
            policy.append("You have the right to lodge a complaint with a supervisory authority if you believe that our processing of your personal data infringes data protection laws. The relevant supervisory authority will typically be the one in the country where you reside, work, or where an alleged infringement has taken place.")
        
        policy.append("")
        
        # Changes to Privacy Policy
        policy.append("## 15. CHANGES TO THIS PRIVACY POLICY")
        
        policy.append(f"We may update this Privacy Policy from time to time by publishing a new version on our website. You should check this page occasionally to ensure you are happy with any changes to this Privacy Policy.")
        policy.append("")
        policy.append(f"We will notify you of significant changes to this Privacy Policy by email or through a prominent notice on our website prior to the change becoming effective.")
        
        policy.append("")
        
        # Final provisions
        policy.append("## 16. CONCLUSION")
        
        policy.append(f"By using our Service, you acknowledge that you have read and understood this Privacy Policy and agree to the collection, use, and disclosure of your information as described herein.")
        policy.append("")
        policy.append(f"If you have any questions about this Privacy Policy, please contact us using the details provided in Section 2.")
        
        return "\n".join(policy)
    
    def save_privacy_policy(self, output_path="privacy_policy.md"):
        """
        Generate and save the privacy policy to a file
        
        Args:
            output_path (str): Path to save the privacy policy file
            
        Returns:
            str: Path where the policy was saved
        """
        policy_text = self.generate_privacy_policy()
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(policy_text)
        
        return output_path
    
    def save_answers_json(self, output_path="company_data.json"):
        """
        Save all the collected answers to a JSON file
        
        Args:
            output_path (str): Path to save the JSON file
            
        Returns:
            str: Path where the JSON was saved
        """
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.company_info, f, indent=4)
        
        return output_path
    
    def load_answers_json(self, input_path):
        """
        Load answers from a JSON file
        
        Args:
            input_path (str): Path to the JSON file to load
            
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                self.company_info = json.load(f)
            
            # Organize the answers into sections
            for question in self.questions:
                question_id = question["id"]
                if question_id in self.company_info:
                    section_name = question["section"]
                    if section_name not in self.policy_sections:
                        self.policy_sections[section_name] = {}
                    self.policy_sections[section_name][question_id] = self.company_info[question_id]
            
            return True
        except:
            return False


class PolicyGeneratorUI:
    """
    Command-line interface for the PrivacyPolicyGenerator
    """
    
    def __init__(self):
        """Initialize the UI"""
        self.generator = PrivacyPolicyGenerator()
        
    def run(self):
        """Run the interactive privacy policy generator"""
        print("="*80)
        print("GDPR Privacy Policy Generator".center(80))
        print("="*80)
        print("\nWelcome to the GDPR-compliant Privacy Policy Generator!")
        print("Answer the following questions to generate a customized privacy policy for your website or service.\n")
        
        # Check if the user wants to load existing data
        load_existing = input("Do you want to load existing company data? (y/n): ").lower()
        if load_existing == 'y':
            filepath = input("Enter the path to your JSON file: ")
            if self.generator.load_answers_json(filepath):
                print("Data loaded successfully!")
                
                # Ask if they want to generate the policy now
                generate_now = input("Do you want to generate the privacy policy now? (y/n): ").lower()
                if generate_now == 'y':
                    self._generate_policy()
                    return
                
                # Or ask if they want to review and edit
                review_edit = input("Do you want to review and edit your answers? (y/n): ").lower()
                if review_edit != 'y':
                    print("Exiting without changes.")
                    return
            else:
                print("Failed to load data. Starting fresh.")
        
        # Start the questionnaire
        self._run_questionnaire()
        
    def _run_questionnaire(self):
        """Run the interactive questionnaire"""
        next_question = self.generator.get_next_question()
        
        while next_question:
            print("\n" + "-"*80)
            print(self.generator.format_question(next_question))
            
            # Get user input
            if "options" in next_question:
                if next_question.get("multi_select", False):
                    print("\nEnter the numbers of your selections separated by commas, or enter 'all' to select all options.")
                    for i, option in enumerate(next_question["options"], 1):
                        print(f"{i}. {option}")
                    
                    answer_input = input("\nYour selection(s): ")
                    
                    if answer_input.lower() == 'all':
                        answer = next_question["options"]
                    else:
                        try:
                            indices = [int(idx.strip()) - 1 for idx in answer_input.split(",")]
                            answer = [next_question["options"][idx] for idx in indices if 0 <= idx < len(next_question["options"])]
                        except:
                            print("Invalid input. Please try again.")
                            continue
                else:
                    for i, option in enumerate(next_question["options"], 1):
                        print(f"{i}. {option}")
                    
                    answer_input = input("\nYour selection (enter number): ")
                    
                    try:
                        index = int(answer_input.strip()) - 1
                        if 0 <= index < len(next_question["options"]):
                            answer = next_question["options"][index]
                        else:
                            print("Invalid selection. Please try again.")
                            continue
                    except:
                        print("Invalid input. Please try again.")
                        continue
            else:
                answer = input("\nYour answer: ")
            
            # Validate the answer
            is_valid, error_message = self.generator.validate_answer(next_question, answer)
            if not is_valid:
                print(f"Error: {error_message} Please try again.")
                continue
            
            # Process the answer
            next_question, follow_up = self.generator.process_answer(answer)
            
            if follow_up:
                print(f"\nNote: {follow_up}")
        
        print("\n" + "-"*80)
        print("Questionnaire completed! Thank you for providing your information.")
        
        self._generate_policy()
    
    def _generate_policy(self):
        """Generate and save the privacy policy"""
        # Ask where to save the policy
        print("\nWhere would you like to save your privacy policy?")
        output_path = input("Enter a filename (default: privacy_policy.md): ")
        
        if not output_path:
            output_path = "privacy_policy.md"
        
        # Ask if they want to save their answers
        save_answers = input("Would you like to save your answers for future use? (y/n): ").lower()
        if save_answers == 'y':
            json_path = input("Enter a filename for your answers (default: company_data.json): ")
            
            if not json_path:
                json_path = "company_data.json"
            
            self.generator.save_answers_json(json_path)
            print(f"Your answers have been saved to {json_path}")
        
        # Generate and save the policy
        saved_path = self.generator.save_privacy_policy(output_path)
        print(f"\nYour GDPR-compliant Privacy Policy has been generated and saved to {saved_path}")
        print("\nThank you for using the GDPR Privacy Policy Generator!")


if __name__ == "__main__":
    ui = PolicyGeneratorUI()
    ui.run()