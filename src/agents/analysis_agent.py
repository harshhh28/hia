from datetime import datetime, timedelta
import streamlit as st
from agents.model_manager import ModelManager

class AnalysisAgent:
    """
    Agent responsible for managing report analysis, rate limiting,
    and implementing in-context learning from previous analyses.
    """
    
    def __init__(self, supabase_client=None):
        self.model_manager = ModelManager()
        self.supabase = supabase_client  # Store supabase client for persistent learning
        self._init_state()
        
    def _init_state(self):
        """Initialize analysis-related session state variables."""
        if 'analysis_count' not in st.session_state:
            st.session_state.analysis_count = 0
        if 'last_analysis' not in st.session_state:
            st.session_state.last_analysis = datetime.now()
        if 'analysis_limit' not in st.session_state:
            st.session_state.analysis_limit = 15
        if 'models_used' not in st.session_state:
            st.session_state.models_used = {}
        if 'knowledge_base' not in st.session_state:
            st.session_state.knowledge_base = {}
            
    def check_rate_limit(self):
        """Check if user has reached their analysis limit."""
        # Calculate time until reset
        time_until_reset = timedelta(days=1) - (datetime.now() - st.session_state.last_analysis)
        hours, remainder = divmod(time_until_reset.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        # Reset counter after 24 hours
        if time_until_reset.days < 0:
            st.session_state.analysis_count = 0
            st.session_state.last_analysis = datetime.now()
            return True, None
        
        # Check if limit reached
        if st.session_state.analysis_count >= st.session_state.analysis_limit:
            error_msg = f"Daily limit reached. Reset in {hours}h {minutes}m"
            return False, error_msg
        return True, None

    def analyze_report(self, data, system_prompt, check_only=False, chat_history=None):
        """
        Analyze report data using in-context learning from previous analyses.
        
        Args:
            data: Report data to analyze
            system_prompt: Base system prompt
            check_only: If True, only check rate limit without generating analysis
            chat_history: Previous messages in the current session (optional)
        """
        can_analyze, error_msg = self.check_rate_limit()
        if not can_analyze:
            return {"success": False, "error": error_msg}
        
        if check_only:
            return can_analyze, error_msg
        
        # Process data before sending to model
        processed_data = self._preprocess_data(data)
        
        # Enhance prompt with in-context learning (only if chat_history is provided)
        enhanced_prompt = self._build_enhanced_prompt(system_prompt, processed_data, chat_history) if chat_history else system_prompt
        
        # Generate analysis using model manager
        result = self.model_manager.generate_analysis(processed_data, enhanced_prompt)
        
        if result["success"]:
            # Update analytics and learning systems
            self._update_analytics(result)
            self._update_knowledge_base(processed_data, result["content"])
        
        return result
    
    def _update_analytics(self, result):
        """Update analytics after successful analysis."""
        st.session_state.analysis_count += 1
        st.session_state.last_analysis = datetime.now()
        
        # Track which models are being used
        model_used = result.get("model_used", "unknown")
        if model_used in st.session_state.models_used:
            st.session_state.models_used[model_used] += 1
        else:
            st.session_state.models_used[model_used] = 1
    
    def _update_knowledge_base(self, data, analysis):
        """
        Update knowledge base with new analysis results for in-context learning.
        Maps key health indicators to analysis patterns.
        Stores in both session state (for current session) and Supabase (for persistence).
        """
        if not isinstance(data, dict) or 'report' not in data:
            return
            
        # Extract key health indicators and map them to analysis outcomes
        report_text = data['report'].lower()
        patient_profile = f"{data.get('age', 'unknown')}-{data.get('gender', 'unknown')}"
        
        # Look for key health indicators in the report
        key_indicators = [
            "hemoglobin", "glucose", "cholesterol", "triglycerides", 
            "hdl", "ldl", "wbc", "rbc", "platelet", "creatinine"
        ]
        
        # Store snippets of analysis associated with key health indicators
        for indicator in key_indicators:
            if indicator in report_text:
                # Find any mentions of this indicator in the analysis
                if indicator in analysis.lower():
                    # Store in session state (for current session)
                    if indicator not in st.session_state.knowledge_base:
                        st.session_state.knowledge_base[indicator] = {}
                    
                    if patient_profile not in st.session_state.knowledge_base[indicator]:
                        st.session_state.knowledge_base[indicator][patient_profile] = []
                    
                    # Extract the relevant section from analysis
                    lines = analysis.split('\n')
                    relevant_lines = [l for l in lines if indicator in l.lower()]
                    if relevant_lines:
                        # Limit knowledge base size to prevent overflow
                        if len(st.session_state.knowledge_base[indicator][patient_profile]) >= 3:
                            st.session_state.knowledge_base[indicator][patient_profile].pop(0)
                        st.session_state.knowledge_base[indicator][patient_profile].append(relevant_lines[0])
                        
                        # Also store to persistent database
                        self._store_learning_to_database(
                            indicator=indicator,
                            value_range=data.get('value_range', ''),
                            condition=data.get('condition', 'analyzed'),
                            outcome=relevant_lines[0],
                            patient_demographics={
                                "age": data.get('age'),
                                "gender": data.get('gender')
                            }
                        )
    
    def _store_learning_to_database(self, indicator, value_range, condition, outcome, patient_demographics):
        """Store a learning record to Supabase for persistence."""
        if not self.supabase:
            return  # Supabase client not available
        
        try:
            learning_record = {
                "indicator": indicator.lower().strip(),
                "value_range": value_range or "not_specified",
                "condition": condition.lower().strip(),
                "outcome": outcome,
                "patient_demographics": patient_demographics or {},
                "confidence": 0.6,  # Default confidence for new learnings
                "usage_count": 1
            }
            
            self.supabase.table("analysis_learnings").insert(learning_record).execute()
        except Exception as e:
            # Silently fail if database is not available
            # Don't interrupt analysis flow for persistent learning failures
            pass
    
    def _build_enhanced_prompt(self, system_prompt, data, chat_history):
        """
        Build an enhanced prompt using in-context learning from:
        1. Knowledge base of previous analyses
        2. Current session chat history
        """
        enhanced_prompt = system_prompt
        
        # Add in-context learning from knowledge base
        if isinstance(data, dict) and 'report' in data:
            kb_context = self._get_knowledge_base_context(data)
            if kb_context:
                enhanced_prompt += "\n\n## Relevant Learning From Previous Analyses\n" + kb_context
        
        # Add session context from chat history
        if chat_history:
            session_context = self._get_session_context(chat_history)
            if session_context:
                enhanced_prompt += "\n\n## Current Session History\n" + session_context
        
        return enhanced_prompt
    
    def _get_knowledge_base_context(self, data):
        """
        Extract relevant context from knowledge base.
        First checks persistent database, then falls back to session state.
        """
        context_items = []
        
        if not isinstance(data, dict) or 'report' not in data:
            return ""
        
        report_text = data.get('report', '').lower()
        patient_profile = f"{data.get('age', 'unknown')}-{data.get('gender', 'unknown')}"
        
        # Try to retrieve from persistent database first
        if self.supabase:
            context_items.extend(self._get_database_context(report_text, patient_profile))
        
        # Fall back to session state for backwards compatibility
        if 'knowledge_base' in st.session_state and st.session_state.knowledge_base:
            for indicator, profiles in st.session_state.knowledge_base.items():
                if indicator in report_text:
                    # Get insights from similar patient profiles first
                    if patient_profile in profiles:
                        for insight in profiles[patient_profile]:
                            context_items.append(f"- {indicator} (similar patient profile): {insight}")
                    
                    # Then get general insights
                    for profile, insights in profiles.items():
                        if profile != patient_profile:
                            for insight in insights:
                                context_items.append(f"- {indicator} (other patient profile): {insight}")
        
        # Limit context size to prevent token explosion
        if len(context_items) > 10:
            context_items = context_items[:10]
            
        return "\n".join(context_items) if context_items else ""
    
    def _get_database_context(self, report_text, patient_profile):
        """Retrieve relevant learnings from persistent database."""
        context_items = []
        
        try:
            # Extract health indicators from report
            key_indicators = [
                "hemoglobin", "glucose", "cholesterol", "triglycerides", 
                "hdl", "ldl", "wbc", "rbc", "platelet", "creatinine"
            ]
            
            for indicator in key_indicators:
                if indicator in report_text:
                    # Query database for learnings about this indicator
                    response = (
                        self.supabase.table("analysis_learnings")
                        .select("indicator, condition, outcome, confidence, usage_count")
                        .eq("indicator", indicator.lower())
                        .eq("is_archived", False)
                        .order("confidence", desc=True)
                        .order("usage_count", desc=True)
                        .limit(3)
                        .execute()
                    )
                    
                    if response.data:
                        for record in response.data:
                            context_items.append(
                                f"- {record['indicator'].title()} "
                                f"({record['condition']}): {record['outcome']}"
                            )
        except Exception as e:
            # Silently fail - database access failure shouldn't break analysis
            pass
        
        return context_items
    
    def _get_session_context(self, chat_history):
        """Extract relevant context from current session."""
        if not chat_history or len(chat_history) < 2:
            return ""
            
        # Get the last few message pairs (up to 2)
        context_items = []
        for i in range(len(chat_history) - 1, 0, -2):
            if i >= 1 and chat_history[i-1]['role'] == 'user' and chat_history[i]['role'] == 'assistant':
                user_msg = chat_history[i-1]['content']
                ai_msg = chat_history[i]['content']
                
                # Keep only the first 200 chars of each message to avoid token explosion
                if len(user_msg) > 200:
                    user_msg = user_msg[:197] + "..."
                if len(ai_msg) > 200:
                    ai_msg = ai_msg[:197] + "..."
                    
                context_items.append(f"User: {user_msg}\nAssistant: {ai_msg}")
                
                # Limit to last 2 exchanges
                if len(context_items) >= 2:
                    break
                    
        return "\n\n".join(reversed(context_items)) if context_items else ""
    
    def _preprocess_data(self, data):
        """Pre-process data before sending to model."""
        if isinstance(data, dict):
            # Extract only necessary information to reduce token usage
            processed = {
                "patient_name": data.get("patient_name", ""),
                "age": data.get("age", ""),
                "gender": data.get("gender", ""),
                "report": data.get("report", "")
            }
            return processed
        return data
