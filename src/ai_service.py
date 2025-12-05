import google.generativeai as genai
import streamlit as st
import json
import os
from src.config import get_config_value

class AIService:
    def __init__(self):
        # Use Google AI API key (simpler than Vertex AI)
        self.api_key = os.getenv("GOOGLE_AI_API_KEY", "")
        self.model = None
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('models/gemini-2.0-flash')
            except Exception as e:
                st.error(f"Failed to initialize Google AI: {e}")
        else:
            st.warning("GOOGLE_AI_API_KEY not set. AI Analysis disabled.")

    def analyze_ticket(self, transcript, prompt_qa, prompt_alert):
        """
        Analyzes the ticket transcript using Google AI.
        Returns a structured dictionary with QA and Alert data.
        """
        if not self.model:
            return None

        # Construct the master prompt
        master_prompt = f"""
        Ste QA špecialista analyzujúci tiket zákazníckej podpory.
        DÔLEŽITÉ: Všetky textové odpovede (verbal_summary, reason) MUSIA byť v SLOVENČINE.
        
        TRANSCRIPT:
        {transcript}
        
        TASK 1: QUALITY ASSURANCE
        {prompt_qa}
        
        TASK 2: RISK ALERTING
        {prompt_alert}
        
        OUTPUT FORMAT:
        Return ONLY a valid JSON object with the following structure:
        {{
          "alert_data": {{
            "is_critical": boolean,
            "reason": "String v slovenčine alebo null"
          }},
          "qa_data": {{
            "verbal_summary": "String v slovenčine (3 vety)",
            "criteria": {{
              "empathy": int (0-100),
              "expertise": int (0-100),
              "problem_solving": int (0-100),
              "error_rate": int (0-100)
            }},
            "overall_score": int (0-100)
          }}
        }}
        """

        try:
            # Generate response
            response = self.model.generate_content(master_prompt)
            
            # Get response text
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            result_json = json.loads(response_text)
            return result_json
            
        except json.JSONDecodeError as e:
            st.error(f"AI Analysis failed (JSON parse error): {e}")
            st.code(response.text[:500] if response.text else "Empty response")
            return None
        except Exception as e:
            st.error(f"AI Analysis failed: {e}")
            return None
