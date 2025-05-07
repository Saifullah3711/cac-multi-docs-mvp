import streamlit as st
import boto3
import requests
import uuid
# import os # Removed as unused
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
import pandas as pd # Added for st.dataframe

st.set_page_config(layout="wide", initial_sidebar_state="collapsed") # Start with sidebar collapsed

# --- Initialize Session State ---
if 'view' not in st.session_state: # For Multi-Docs Flow
    st.session_state.view = 'upload'
if 'analysis_results' not in st.session_state: # For Multi-Docs Flow
    st.session_state.analysis_results = None
if 'analysis_nav' not in st.session_state: # For Multi-Docs Flow
    st.session_state.analysis_nav = None

if 'run_id' not in st.session_state:
    st.session_state.run_id = str(uuid.uuid4())

# New session states for flow selection and Commercial Rent Roll
if 'selected_flow' not in st.session_state:
    st.session_state.selected_flow = "Multi-Docs Smart Analysis" # Default flow
if 'view_rent_roll' not in st.session_state: # For Rent Roll Flow
    st.session_state.view_rent_roll = 'upload_rr'
if 'rent_roll_analysis_results' not in st.session_state: # For Rent Roll Flow
    st.session_state.rent_roll_analysis_results = None


# --- Configuration & Secrets ---
try:
    # AWS/API Config
    AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
    AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
    AWS_REGION = st.secrets["AWS_REGION"]
    S3_BUCKET_NAME = st.secrets["S3_BUCKET_NAME"]
    API_BASE_URL_MULTI_DOCS = st.secrets["API_BASE_URL"].rstrip('/') # Existing API for multi-docs

    # Load new secret for Commercial Rent Roll API
    # User needs to add this to .streamlit/secrets.toml
    if "API_BASE_URL_COMMERCIAL_RENT_ROLL" in st.secrets:
        API_BASE_URL_COMMERCIAL_RENT_ROLL = st.secrets["API_BASE_URL_COMMERCIAL_RENT_ROLL"].rstrip('/')
    else:
        API_BASE_URL_COMMERCIAL_RENT_ROLL = None # Will be checked before use

except KeyError as e:
    # Adjusted error message slightly
    st.error(f"Missing a required secret in .streamlit/secrets.toml: {e}. Please ensure AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME, API_BASE_URL are set. If using Commercial Rent Roll, API_BASE_URL_COMMERCIAL_RENT_ROLL is also needed.")
    st.stop()

API_ENDPOINT_ROUTE_MULTI_DOCS = "cactus-ai-multi-docs-smart-analysis"
API_ENDPOINT_ROUTE_RENT_ROLL = "cactus-ai-commercial-rent-roll" # New route
S3_BASE_FOLDER = "USER#2/ai-agent-rentroll-parser"
ALLOWED_EXTENSIONS = ['pdf', 'xlsx', 'xls']

# --- S3 Client (Initialize directly) ---
@st.cache_resource
def get_s3_client():
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        return s3_client
    except (NoCredentialsError, PartialCredentialsError):
        st.error("AWS credentials not found or incomplete. Check your secrets.toml.")
        return None
    except ClientError as e:
        st.error(f"Error connecting to S3: {e}. Check region and credentials.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during S3 client initialization: {e}")
        return None

s3_client = get_s3_client() # Initialize directly


# --- Helper Functions (upload_to_s3, is_allowed_file) ---
def upload_to_s3(file_obj, bucket_name, s3_folder, s3_client_instance):
    if file_obj is None or s3_client_instance is None:
        return ""

    file_name = file_obj.name

    s3_key = f"{s3_folder}/{file_name}"
    try:
        s3_client_instance.upload_fileobj(file_obj, bucket_name, s3_key)
        st.info(f"Successfully uploaded {file_name}")
        return s3_key
    except ClientError as e:
        st.error(f"Failed to upload {file_name} to S3: {e}")
        return ""
    except Exception as e:
        st.error(f"An unexpected error occurred during S3 upload of {file_name}: {e}")
        return ""

def is_allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Sidebar for Flow Selection ---
flow_options = ["Multi-Docs Smart Analysis", "Commercial Rent Roll Analysis"]
# Get current index safely, default to 0 if key missing or value invalid
current_flow_index = 0
if 'selected_flow' in st.session_state:
    try:
        current_flow_index = flow_options.index(st.session_state.selected_flow)
    except ValueError: # Handle case where session state might have an invalid flow name
        st.session_state.selected_flow = flow_options[0] # Default to first option
else: # If 'selected_flow' is not in session_state yet
    st.session_state.selected_flow = flow_options[0]


st.sidebar.title("Select Analysis Flow")
selected_flow_from_radio = st.sidebar.radio(
    "Choose the type of analysis:",
    flow_options,
    key='flow_selection_radio', # Unique key for this radio button
    index=current_flow_index
)

# If the user changes the flow selection
if selected_flow_from_radio != st.session_state.selected_flow:
    st.session_state.selected_flow = selected_flow_from_radio
    # Reset states relevant to both flows to ensure a clean slate
    st.session_state.run_id = str(uuid.uuid4()) # New run ID for the new flow context

    # Reset view states for Multi-Docs flow
    st.session_state.view = 'upload'
    st.session_state.analysis_results = None
    st.session_state.analysis_nav = None

    # Reset view states for Commercial Rent Roll flow
    st.session_state.view_rent_roll = 'upload_rr'
    st.session_state.rent_roll_analysis_results = None
    st.rerun() # Rerun to apply changes immediately


# --- Main Application Logic ---

# =================================
# ===== MULTI-DOCS SMART ANALYSIS FLOW =====
# =================================
if st.session_state.selected_flow == "Multi-Docs Smart Analysis":
    st.title("Cactus AI - Multi-Document Smart Analysis - Self Storage")
    st.write("Current support is only for self storage properties.")

    # =========================
    # ===== UPLOAD VIEW (Multi-Docs) =====
    # =========================
    if st.session_state.view == 'upload':
        # Hide sidebar for this specific view for better focus as per original design
        # st.markdown(
        #     """
        #     <style>
        #         [data-testid="stSidebar"] { display: none; }
        #     </style>
        #     """,
        #     unsafe_allow_html=True,
        # )

        # Reset analysis state if returning to upload view (redundant if reset on flow change, but safe)
        st.session_state.analysis_results = None
        st.session_state.analysis_nav = None

        uploaded_files = {}
        s3_run_folder = f"{S3_BASE_FOLDER}/{st.session_state.run_id}/multi_docs" # Specific subfolder

        col1, col2 = st.columns(2)
        with col1:
            st.header("Management Summary")
            uploaded_files["management_summary"] = st.file_uploader(
                "Upload Management Summary (PDF/Excel)", type=ALLOWED_EXTENSIONS, key="mgmt_summary_upload"
            )
            st.header("Offering Memorandum")
            uploaded_files["offering_memo"] = st.file_uploader(
                "Upload Offering Memorandum (PDF/Excel)", type=ALLOWED_EXTENSIONS, key="offering_memo_upload"
            )
        with col2:
            st.header("Occupancy Report")
            uploaded_files["occupancy_report"] = st.file_uploader(
                "Upload Occupancy Report (PDF/Excel)", type=ALLOWED_EXTENSIONS, key="occupancy_report_upload"
            )
            st.header("Other Document")
            uploaded_files["other_docs"] = st.file_uploader(
                "Upload Other Document (PDF/Excel)", type=ALLOWED_EXTENSIONS, key="other_docs_upload"
            )
        st.markdown("---")

        if st.button("Run Smart Analysis", type="primary", disabled=(s3_client is None)):
            if not any(uploaded_files.values()):
                st.warning("Please upload at least one document before running the analysis.")
                st.stop()
            if s3_client is None: # Should be caught by disabled state, but good check
                st.error("S3 Client could not be initialized. Cannot upload files or run analysis. Check AWS credentials in secrets.toml.")
                st.stop()

            s3_keys = {"management_summary_s3_key": "", "occupancy_report_s3_key": "", "offering_memo_s3_key": "", "other_docs_s3_key": ""}
            with st.spinner("Uploading files ..."):
                valid_uploads = False
                # Standard file upload logic for multi-docs
                if uploaded_files["management_summary"] and is_allowed_file(uploaded_files["management_summary"].name):
                    s3_keys["management_summary_s3_key"] = upload_to_s3(uploaded_files["management_summary"], S3_BUCKET_NAME, s3_run_folder, s3_client)
                    valid_uploads = True if s3_keys["management_summary_s3_key"] else valid_uploads
                elif uploaded_files["management_summary"]:
                     st.warning(f"Skipping Management Summary: Invalid file type for {uploaded_files['management_summary'].name}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

                if uploaded_files["occupancy_report"] and is_allowed_file(uploaded_files["occupancy_report"].name):
                    s3_keys["occupancy_report_s3_key"] = upload_to_s3(uploaded_files["occupancy_report"], S3_BUCKET_NAME, s3_run_folder, s3_client)
                    valid_uploads = True if s3_keys["occupancy_report_s3_key"] else valid_uploads
                elif uploaded_files["occupancy_report"]:
                     st.warning(f"Skipping Occupancy Report: Invalid file type for {uploaded_files['occupancy_report'].name}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

                if uploaded_files["offering_memo"] and is_allowed_file(uploaded_files["offering_memo"].name):
                    s3_keys["offering_memo_s3_key"] = upload_to_s3(uploaded_files["offering_memo"], S3_BUCKET_NAME, s3_run_folder, s3_client)
                    valid_uploads = True if s3_keys["offering_memo_s3_key"] else valid_uploads
                elif uploaded_files["offering_memo"]:
                     st.warning(f"Skipping Offering Memorandum: Invalid file type for {uploaded_files['offering_memo'].name}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

                if uploaded_files["other_docs"] and is_allowed_file(uploaded_files["other_docs"].name):
                    s3_keys["other_docs_s3_key"] = upload_to_s3(uploaded_files["other_docs"], S3_BUCKET_NAME, s3_run_folder, s3_client)
                    valid_uploads = True if s3_keys["other_docs_s3_key"] else valid_uploads
                elif uploaded_files["other_docs"]:
                     st.warning(f"Skipping Other Document: Invalid file type for {uploaded_files['other_docs'].name}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

            if not valid_uploads and any(uploaded_files.values()): # If some files were attempted but all failed
                 st.error("Upload failed for all provided files. Please check file types or S3 connection errors above.")
                 st.stop()
            elif not any(s3_keys.values()): # If no s3 keys were successfully obtained (e.g. no valid files uploaded)
                st.warning("No valid documents were uploaded successfully. Cannot proceed with analysis.")
                st.stop()

            api_url = f"{API_BASE_URL_MULTI_DOCS}/{API_ENDPOINT_ROUTE_MULTI_DOCS}"
            payload = {**s3_keys, "property_type": "self_storage", "run_id": st.session_state.run_id}
            st.info(f"Calling Backend for Multi-Doc Analysis...")
            try:
                with st.spinner("Performing smart analysis... This may take a moment."):
                    response = requests.post(api_url, json=payload, timeout=300) # 5 min timeout
                    response.raise_for_status()
                st.success("Multi-Doc Analysis Complete!")
                analysis_results_data = response.json()
                st.session_state.analysis_results = analysis_results_data
                # Determine first page to show in results
                first_result_key = next((k for k, v in analysis_results_data.items() if isinstance(v, dict) and v), None)
                if first_result_key:
                    nav_map = {"management_summary_data": "Management Summary", "occupancy_report_data": "Occupancy Report", "offering_memo_data": "Offering Memorandum", "other_docs_data": "Other Document"}
                    st.session_state.analysis_nav = nav_map.get(first_result_key)
                else:
                    st.session_state.analysis_nav = None
                st.session_state.view = 'results'
                st.rerun()
            except requests.exceptions.HTTPError as http_err:
                st.error(f"API request failed with HTTP error: {http_err}")
                try: st.error(f"Error details from API: {http_err.response.json()}")
                except ValueError: st.error(f"Response content from API: {http_err.response.text}")
                st.session_state.analysis_results = None
            except requests.exceptions.RequestException as req_err: # Other requests errors
                st.error(f"API request failed: {req_err}")
                st.session_state.analysis_results = None
            except Exception as e_other: # Catch other potential errors like JSON parsing if response is not JSON
                st.error(f"An unexpected error occurred during API call or processing: {e_other}")
                st.session_state.analysis_results = None

    # =========================
    # ===== RESULTS VIEW (Multi-Docs) =====
    # =========================
    elif st.session_state.view == 'results':
        # Ensure sidebar is visible for results view
        # st.markdown(
        #     """<style>[data-testid="stSidebar"] { display: block; } </style>""", unsafe_allow_html=True,
        # )
        # Custom CSS for results display
        st.markdown(
            """
            <style>
                .stMarkdown p, .stMarkdown li { font-size: 1.1rem; line-height: 1.6; }
            </style>
            """, unsafe_allow_html=True
        )

        # Button in sidebar to start a new analysis for this flow
        if st.sidebar.button("Start New Multi-Doc Analysis", key="multi_doc_new_analysis_results_key"):
            st.session_state.view = 'upload'
            st.session_state.run_id = str(uuid.uuid4()) # New run ID
            st.session_state.analysis_results = None
            st.session_state.analysis_nav = None
            st.rerun()
        
        st.header("Multi-Document Analysis Results")
        if st.session_state.analysis_results:
            results = st.session_state.analysis_results
            available_pages = []
            page_details_map = {
                "Management Summary": {"api_key": "management_summary_data", "summary_key": "m_s_summary", "report_key": "full_report"},
                "Occupancy Report": {"api_key": "occupancy_report_data", "summary_key": "o_r_summary", "report_key": "full_report"},
                "Offering Memorandum": {"api_key": "offering_memo_data", "summary_key": "o_m_summary", "report_key": "full_report"},
                "Other Document": {"api_key": "other_docs_data", "summary_key": "o_d_summary", "report_key": "full_report"}
            }
            for display_name, details in page_details_map.items():
                # Check if the api_key exists and its value is a dictionary (implying data is present)
                if isinstance(results.get(details["api_key"]), dict):
                    available_pages.append(display_name)

            if not available_pages:
                st.warning("Analysis completed, but no data was returned in the expected format for any document type.")
            else:
                default_index_multi = 0
                if st.session_state.analysis_nav in available_pages:
                    default_index_multi = available_pages.index(st.session_state.analysis_nav)
                elif available_pages : # if analysis_nav is not set or invalid, default to first available
                    st.session_state.analysis_nav = available_pages[0]
                    # default_index_multi remains 0
                
                selected_page = st.radio(
                    "Select analysis to view:", options=available_pages, key="analysis_nav_main_radio_key", # Unique key
                    index=default_index_multi, horizontal=True
                )
                # Update session state if radio button changes the selection
                if selected_page != st.session_state.analysis_nav :
                    st.session_state.analysis_nav = selected_page
                    # st.rerun() # Optional: uncomment if changing radio selection needs immediate full page effect

                st.markdown("---")
                selected_page_details = page_details_map.get(selected_page)
                if selected_page_details:
                    st.subheader(f"{selected_page} Analysis")
                    page_data = results.get(selected_page_details["api_key"], {}) # Default to empty dict
                    summary_content = str(page_data.get(selected_page_details["summary_key"], "No summary available."))
                    full_report_content = str(page_data.get(selected_page_details["report_key"], "No full report available."))
                    # Escape $ for markdown
                    escaped_summary = summary_content.replace("$", "\\$")
                    escaped_full_report = full_report_content.replace("$", "\\$")
                    st.markdown("**Summary:**"); st.markdown(escaped_summary); st.markdown("---")
                    with st.expander("View Full Report"): st.markdown(escaped_full_report)
                else: st.error("An error occurred displaying the selected analysis.")
        else: # No analysis_results in session state
            st.warning("No analysis results available. Go back to upload documents.")
            if st.button("Back to Multi-Doc Upload", key="back_to_multi_upload_key"):
                st.session_state.view = 'upload'; st.rerun()

# =======================================
# ===== COMMERCIAL RENT ROLL ANALYSIS FLOW =====
# =======================================
elif st.session_state.selected_flow == "Commercial Rent Roll Analysis":
    st.title("Cactus AI - Commercial Rent Roll Analysis")
    st.write("Upload your commercial rent roll document for analysis.")
    # Ensure sidebar is visible for this flow (it's controlled by the radio button selection now)
    # st.markdown(
    #     """<style>[data-testid="stSidebar"] { display: block; } </style>""", unsafe_allow_html=True,
    # )

    # =========================
    # ===== UPLOAD VIEW (Rent Roll) =====
    # =========================
    if st.session_state.view_rent_roll == 'upload_rr':
        st.session_state.rent_roll_analysis_results = None # Reset previous results on new upload attempt

        s3_run_folder_rr = f"{S3_BASE_FOLDER}/{st.session_state.run_id}/multi_docs" # Specific subfolder - CHANGED

        uploaded_rent_roll_file = st.file_uploader(
            "Upload Commercial Rent Roll Document (PDF/Excel/XLS)",
            type=ALLOWED_EXTENSIONS, key="rent_roll_file_upload_key" # Unique key
        )
        st.markdown("---")

        # Check if the API URL for rent roll is configured
        if API_BASE_URL_COMMERCIAL_RENT_ROLL is None:
             st.warning("Commercial Rent Roll Analysis is not available. The API URL (API_BASE_URL_COMMERCIAL_RENT_ROLL) is not configured in .streamlit/secrets.toml.")
             # Disable button if URL is missing
             run_button_disabled_rr = True
        else:
            run_button_disabled_rr = (
                s3_client is None or
                not uploaded_rent_roll_file # Also disable if no file is staged
            )
        
        if st.button("Run Rent Roll Analysis", type="primary", disabled=run_button_disabled_rr, key="run_rent_roll_button_key"):
            # Explicit checks, though button should be disabled by `run_button_disabled_rr`
            if API_BASE_URL_COMMERCIAL_RENT_ROLL is None: # Should not happen if button logic is correct
                st.error("Commercial Rent Roll API URL is not configured."); st.stop()
            if not uploaded_rent_roll_file: # Should not happen
                st.warning("Please upload a rent roll document."); st.stop()
            if s3_client is None: # Should not happen
                st.error("S3 Client could not be initialized."); st.stop()

            s3_key_rr = ""
            if is_allowed_file(uploaded_rent_roll_file.name):
                with st.spinner(f"Uploading {uploaded_rent_roll_file.name}..."):
                    s3_key_rr = upload_to_s3(uploaded_rent_roll_file, S3_BUCKET_NAME, s3_run_folder_rr, s3_client)
            else: # Should be caught by file_uploader type, but as a fallback
                st.warning(f"Invalid file type: {uploaded_rent_roll_file.name}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"); st.stop()

            if not s3_key_rr: # If upload_to_s3 returned empty (error)
                st.error("File upload failed. Cannot proceed with analysis."); st.stop()

            api_url_rr = f"{API_BASE_URL_COMMERCIAL_RENT_ROLL}/{API_ENDPOINT_ROUTE_RENT_ROLL}"
            payload_rr = {"doc_url": s3_key_rr, "run_id": st.session_state.run_id} # Include run_id - CHANGED KEY

            st.info("Calling Rent Roll Backend...")
            try:
                with st.spinner("Performing rent roll analysis... This may take a moment."):
                    response_rr = requests.post(api_url_rr, json=payload_rr, timeout=300) # 5 min timeout
                    response_rr.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
                st.success("Rent Roll Analysis Complete!")
                st.session_state.rent_roll_analysis_results = response_rr.json()
                st.session_state.view_rent_roll = 'results_rr'
                st.rerun()
            except requests.exceptions.HTTPError as http_err:
                st.error(f"API request failed with HTTP error: {http_err}")
                try: st.error(f"Error details from API: {http_err.response.json()}")
                except ValueError: st.error(f"Response content from API: {http_err.response.text}") # If response is not JSON
                st.session_state.rent_roll_analysis_results = None
            except requests.exceptions.RequestException as req_err: # Catches other non-HTTP errors (e.g., connection error)
                st.error(f"API request failed: {req_err}")
                st.session_state.rent_roll_analysis_results = None
            except Exception as e_other: # Catch other potential errors (e.g., JSON parsing if API returns non-JSON on success)
                st.error(f"An unexpected error occurred: {e_other}")
                st.session_state.rent_roll_analysis_results = None
        
    # =========================
    # ===== RESULTS VIEW (Rent Roll) =====
    # =========================
    elif st.session_state.view_rent_roll == 'results_rr':
        # Button in sidebar to start new analysis for this flow
        if st.sidebar.button("Start New Rent Roll Analysis", key="rent_roll_new_analysis_results_key"):
            st.session_state.view_rent_roll = 'upload_rr'
            st.session_state.run_id = str(uuid.uuid4()) # New run ID
            st.session_state.rent_roll_analysis_results = None
            st.rerun()

        st.header("Commercial Rent Roll Analysis Results")
        results_rr = st.session_state.rent_roll_analysis_results

        if results_rr:
            if results_rr.get("status") == "success" and "rent_roll_json_data" in results_rr:
                data_to_display = results_rr["rent_roll_json_data"]
                if isinstance(data_to_display, list) and data_to_display:
                    try:
                        df = pd.DataFrame(data_to_display)
                        st.dataframe(df, hide_index=True) # Use hide_index for a cleaner table
                    except Exception as e: # Catch potential errors during DataFrame creation
                        st.error(f"Error displaying data as table: {e}")
                        st.write("Raw data received from API:")
                        st.json(data_to_display) # Show raw json for debugging
                elif isinstance(data_to_display, list) and not data_to_display: # Empty list
                    st.info("Analysis successful, but no rent roll line items were returned.")
                else: # Data is not a list or has an unexpected structure
                    st.warning("Rent roll data received from API is not in the expected list format.")
                    st.write("Raw data received from API:")
                    st.json(data_to_display) # Show what was received
            else: # Status not "success" or key "rent_roll_json_data" missing
                st.error(f"Analysis did not return a successful status or expected data. Status: {results_rr.get('status', 'N/A')}")
                st.write("Full API response:")
                st.json(results_rr) # Show raw json for debugging
        else: # No rent_roll_analysis_results in session state
            st.warning("No rent roll analysis results available.")
            if st.button("Back to Rent Roll Upload", key="back_to_rr_upload_key"):
                st.session_state.view_rent_roll = 'upload_rr'
                st.rerun()