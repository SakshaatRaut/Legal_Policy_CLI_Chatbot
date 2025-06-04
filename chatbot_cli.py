import os
import sys
import json
from pathlib import Path
from policy_generator import PrivacyPolicyGenerator

class PrivacyPolicyChatbot:
    """
    Command-line interface for the privacy policy generator chatbot
    """
    
    def __init__(self):
        """Initialize the chatbot"""
        self.generator = PrivacyPolicyGenerator()
        self.welcome_message()
        self.current_question = self.generator.get_next_question()
    
    def welcome_message(self):
        """Display welcome message"""
        print("\n" + "=" * 80)
        print("Welcome to the GDPR Privacy Policy Generator!")
        print("=" * 80)
        print("I'll ask you a series of questions about your company and data practices.")
        print("Your answers will be used to create a GDPR-compliant privacy policy.")
        print("Let's get started!\n")
    
    def run(self):
        """Run the chatbot conversation"""
        while self.current_question:
            # Format and display the question
            question_text = self.generator.format_question(self.current_question)
            print("\n" + question_text)
            
            # Get user response
            answer = self.get_user_input(self.current_question)
            
            # Validate the answer
            is_valid, error_message = self.generator.validate_answer(self.current_question, answer)
            
            if not is_valid:
                print(f"\nError: {error_message}")
                continue
            
            # Process the answer
            next_question, follow_up = self.generator.process_answer(answer)
            
            if follow_up:
                print(f"\n{follow_up}")
            
            self.current_question = next_question
        
        self.generate_policy()
    
    def get_user_input(self, question):
        """
        Get user input for a question
        
        Args:
            question (dict): Question information
            
        Returns:
            str or list: User's answer
        """
        # For questions with options
        if "options" in question:
            if question.get("multi_select", False):
                return self.get_multiselect_input(question)
            else:
                return self.get_singleselect_input(question)
        
        # For free text input
        answer = input("\nYour answer: ").strip()
        
        # Handle empty input for optional questions
        if not answer and not question.get("required", True):
            return ""
        
        return answer
    
    def get_singleselect_input(self, question):
        """
        Get single-select input from user
        
        Args:
            question (dict): Question information
            
        Returns:
            str: Selected option
        """
        while True:
            answer = input("\nYour choice (type the option): ").strip()
            
            if answer in question["options"]:
                return answer
            
            print(f"Please select one of the available options: {', '.join(question['options'])}")
    
    def get_multiselect_input(self, question):
        """
        Get multi-select input from user
        
        Args:
            question (dict): Question information
            
        Returns:
            list: Selected options
        """
        print("\nEnter each choice separated by commas, or 'all' to select all options")
        while True:
            answer = input("\nYour choices: ").strip()
            
            if answer.lower() == "all":
                return question["options"]
            
            # Split by comma and clean up
            selections = [option.strip() for option in answer.split(",")]
            
            # Check if all selections are valid
            valid_options = set(question["options"])
            if all(selection in valid_options for selection in selections):
                return selections
            
            print(f"Please select only from the available options: {', '.join(question['options'])}")
    
    def generate_policy(self):
        """Generate and save the privacy policy"""
        print("\n" + "=" * 80)
        print("Thank you for providing all the information!")
        print("Generating your GDPR-compliant privacy policy...")
        
        # Generate and save the policy
        policy_file = self.generator.save_privacy_policy()
        info_file = self.generator.save_answers_json()
        
        print("\nYour privacy policy has been generated successfully!")
        print(f"Policy saved to: {policy_file}")
        print(f"Your information saved to: {info_file}")
        
        # Ask if user wants to view the policy
        view_policy = input("\nWould you like to view your privacy policy now? (yes/no): ").strip().lower()
        
        if view_policy in ["yes", "y"]:
            with open(policy_file, "r", encoding="utf-8") as f:
                print("\n" + "=" * 80)
                print("PRIVACY POLICY")
                print("=" * 80 + "\n")
                print(f.read())


if __name__ == "__main__":
    # Initialize the database if needed
    if not os.path.exists("gdpr_knowledge_base.db"):
        from gdpr_parser import GDPRDatabaseBuilder
        
        print("Initializing GDPR knowledge base...")
        builder = GDPRDatabaseBuilder()
        
        # Check if a GDPR PDF file path was provided
        if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
            print(f"Parsing GDPR PDF: {sys.argv[1]}")
            builder.parse_gdpr_pdf(sys.argv[1])
        else:
            print("No GDPR PDF provided or file not found.")
            print("The database has been created with minimal topic information.")
            print("For full functionality, please run with a GDPR PDF file path.")
            print("Example: python chatbot_cli.py path/to/gdpr.pdf\n")
    
    # Start the chatbot
    chatbot = PrivacyPolicyChatbot()
    chatbot.run()