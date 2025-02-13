import streamlit as st
from services.ai_service import generate_analysis
from config.prompts import SPECIALIST_PROMPTS
from utils.pdf_extractor import extract_text_from_pdf
from config.sample_data import SAMPLE_REPORT

def show_analysis_form():
    # Set default value to "Upload PDF" when it's a new session
    default_source = "Upload PDF"
    
    report_source = st.radio(
        "Choose report source",
        ["Upload PDF", "Use Sample PDF"],
        index=0,  # 0 corresponds to "Upload PDF"
        horizontal=True
    )

    pdf_contents = get_report_contents(report_source)
            
    if pdf_contents:  # Only show form if we have report content
        render_patient_form(pdf_contents)

def get_report_contents(report_source):
    if report_source == "Upload PDF":
        uploaded_file = st.file_uploader(
            "Upload blood report PDF", 
            type=['pdf'],
            help="Only PDF files containing medical reports are supported"
        )
        if uploaded_file:
            if uploaded_file.type != 'application/pdf':
                st.error("Please upload a valid PDF file.")
                return None
                
            pdf_contents = extract_text_from_pdf(uploaded_file)
            if isinstance(pdf_contents, str) and (
                pdf_contents.startswith(("File size exceeds", "Invalid file type", "Error validating")) or
                pdf_contents.startswith("The uploaded file") or
                "error" in pdf_contents.lower()
            ):
                st.error(pdf_contents)
                return None
            with st.expander("View Extracted Report"):
                st.text(pdf_contents)
            return pdf_contents
    else:
        with st.expander("View Sample Report"):
            st.text(SAMPLE_REPORT)
        return SAMPLE_REPORT
    return None

def render_patient_form(pdf_contents):
    with st.form("analysis_form"):
        patient_name = st.text_input("Patient Name")
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("Age", min_value=0, max_value=120)
        with col2:
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        
        if st.form_submit_button("Analyze Report"):
            handle_form_submission(patient_name, age, gender, pdf_contents)

def handle_form_submission(patient_name, age, gender, pdf_contents):
    if not all([patient_name, age, gender]):
        st.error("Please fill in all fields")
        return

    # Check rate limit first, outside of spinner
    can_analyze, error_msg = generate_analysis(None, None, check_only=True)
    if not can_analyze:
        st.error(error_msg)
        st.stop()
        return

    with st.spinner("Analyzing report..."):
        # Save user message and proceed with analysis
        st.session_state.auth_service.save_chat_message(
            st.session_state.current_session['id'],
            f"Analyzing report for patient: {patient_name}"
        )
        
        # Generate analysis
        result = generate_analysis({
            "patient_name": patient_name,
            "age": age,
            "gender": gender,
            "report": pdf_contents
        }, SPECIALIST_PROMPTS["comprehensive_analyst"])
        
        if result["success"]:
            st.session_state.auth_service.save_chat_message(
                st.session_state.current_session['id'],
                result["content"],
                role='assistant'
            )
            st.rerun()
        else:
            st.error(result["error"])
            st.stop()
