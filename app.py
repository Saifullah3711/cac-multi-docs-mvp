import streamlit as st
import boto3
import requests
import uuid
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

if 'view' not in st.session_state:
    st.session_state.view = 'upload'
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'analysis_nav' not in st.session_state:
    st.session_state.analysis_nav = None
if 'run_id' not in st.session_state:
    st.session_state.run_id = str(uuid.uuid4())
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

try:
    AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
    AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
    AWS_REGION = st.secrets["AWS_REGION"]
    S3_BUCKET_NAME = st.secrets["S3_BUCKET_NAME"]
    API_BASE_URL = st.secrets["API_BASE_URL"].rstrip('/')
    AUTH_USERNAME = st.secrets["AUTH_USERNAME"]
    AUTH_PASSWORD = st.secrets["AUTH_PASSWORD"]
except KeyError as e:
    st.error(f"Missing secret: {e}. Please configure .streamlit/secrets.toml correctly.")
    st.stop()

API_ENDPOINT_ROUTE = "cactus-ai-multi-docs-smart-analysis"
S3_BASE_FOLDER = "USER#2/ai-agent-rentroll-parser"
ALLOWED_EXTENSIONS = ['pdf', 'xlsx', 'xls']

def check_login():
    st.title("Login - Cactus AI Analysis")
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")

        login_pressed = st.button("Login", key="login_button", use_container_width=True)

    if login_pressed:
        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.view = 'upload'
            st.rerun()
        else:
            with col2:
                st.error("Incorrect username or password")

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

s3_client = None
if st.session_state.authenticated:
    s3_client = get_s3_client()

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

if not st.session_state.authenticated:
    check_login()
else:
    st.title("Cactus AI - Multi-Document Smart Analysis - Self Storage")
    st.write("Current support is only for self storage properties.")

    if st.session_state.view == 'upload':
        st.markdown(
            """
            <style>
                [data-testid="stSidebar"] { display: none; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.session_state.analysis_results = None
        st.session_state.analysis_nav = None
        st.session_state.run_id = str(uuid.uuid4())

        uploaded_files = {}
        s3_run_folder = f"{S3_BASE_FOLDER}/{st.session_state.run_id}"

        col1, col2 = st.columns(2)

        with col1:
            st.header("Management Summary")
            uploaded_files["management_summary"] = st.file_uploader(
                "Upload Management Summary (PDF/Excel)",
                type=ALLOWED_EXTENSIONS,
                key="mgmt_summary_upload"
            )

            st.header("Offering Memorandum")
            uploaded_files["offering_memo"] = st.file_uploader(
                "Upload Offering Memorandum (PDF/Excel)",
                type=ALLOWED_EXTENSIONS,
                key="offering_memo_upload"
            )

        with col2:
            st.header("Occupancy Report")
            uploaded_files["occupancy_report"] = st.file_uploader(
                "Upload Occupancy Report (PDF/Excel)",
                type=ALLOWED_EXTENSIONS,
                key="occupancy_report_upload"
            )

            st.header("Other Document")
            uploaded_files["other_docs"] = st.file_uploader(
                "Upload Other Document (PDF/Excel)",
                type=ALLOWED_EXTENSIONS,
                key="other_docs_upload"
            )

        st.markdown("---")

        if st.button("Run Smart Analysis", type="primary", disabled=(s3_client is None)):

            if not any(uploaded_files.values()):
                st.warning("Please upload at least one document before running the analysis.")
                st.stop()

            if s3_client is None:
                st.error("S3 Client not initialized. Cannot upload files or run analysis. Check credentials.")
                st.stop()

            s3_keys = {
                "management_summary_s3_key": "",
                "occupancy_report_s3_key": "",
                "offering_memo_s3_key": "",
                "other_docs_s3_key": ""
            }

            with st.spinner("Uploading files ..."):
                valid_uploads = False
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

            if not valid_uploads and any(uploaded_files.values()):
                 st.error("Upload failed for all provided files. Please check file types or S3 connection errors above.")
                 st.stop()
            elif not any(s3_keys.values()):
                st.warning("No valid documents were uploaded successfully. Cannot proceed with analysis.")
                st.stop()

            api_url = f"{API_BASE_URL}/{API_ENDPOINT_ROUTE}"
            payload = {**s3_keys, "property_type": "self_storage"}

            st.info(f"Calling Backend ...")

            try:
                with st.spinner("Performing smart analysis... This may take a moment."):
                    response = requests.post(api_url, json=payload, timeout=300)
                    response.raise_for_status()

                st.success("Analysis Complete!")
                analysis_results_data = response.json()

                st.session_state.analysis_results = analysis_results_data

                first_result_key = next((k for k, v in analysis_results_data.items() if v), None)
                if first_result_key:
                    nav_map = {
                        "management_summary_data": "Management Summary",
                        "occupancy_report_data": "Occupancy Report",
                        "offering_memo_data": "Offering Memorandum",
                        "other_docs_data": "Other Document"
                    }
                    st.session_state.analysis_nav = nav_map.get(first_result_key)
                else:
                    st.session_state.analysis_nav = None

                st.session_state.view = 'results'
                st.rerun()

            except requests.exceptions.RequestException as e:
                st.error(f"API request failed: {e}")
                if hasattr(e, 'response') and e.response is not None:
                     st.error(f"Response status code: {e.response.status_code}")
                     st.error(f"Response body: {e.response.text}")
                st.session_state.analysis_results = None
            except Exception as e:
                st.error(f"An unexpected error occurred during API call: {e}")
                st.session_state.analysis_results = None

    elif st.session_state.view == 'results':
        st.markdown(
            """
            <style>
                /* Make sidebar visible */
                [data-testid="stSidebar"] { 
                    display: block;
                }
                /* Increase font size for markdown content */
                .stMarkdown p, .stMarkdown li {
                    font-size: 1.1rem; /* Use rem for relative sizing */
                    line-height: 1.6;  /* Improve spacing between lines */
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        if st.sidebar.button("Start New Analysis", key="results_new_analysis"):
            st.session_state.view = 'upload'
            st.session_state.run_id = str(uuid.uuid4())
            st.rerun()
        if st.sidebar.button("Logout", key="results_logout"):
            st.session_state.authenticated = False
            st.session_state.view = 'upload'
            st.session_state.run_id = str(uuid.uuid4())
            st.session_state.analysis_results = None
            st.session_state.analysis_nav = None
            st.rerun()

        st.header("Analysis Results")

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
                if isinstance(results.get(details["api_key"]), dict):
                    available_pages.append(display_name)

            if not available_pages:
                st.warning("Analysis completed, but no data was returned in the expected format.")
            else:
                default_index = 0
                if st.session_state.analysis_nav in available_pages:
                    default_index = available_pages.index(st.session_state.analysis_nav)
                elif available_pages:
                    st.session_state.analysis_nav = available_pages[0]

                selected_page = st.radio(
                    "Select analysis to view:",
                    options=available_pages,
                    key="analysis_nav_main",
                    index=default_index,
                    horizontal=True
                )

                st.markdown("---")

                selected_page_details = page_details_map.get(selected_page)

                if selected_page_details:
                    st.subheader(f"{selected_page} Analysis")
                    page_data = results.get(selected_page_details["api_key"], {})

                    # Get summary and full report content, default to informative messages
                    summary_content = page_data.get(selected_page_details["summary_key"], "No summary available.")
                    full_report_content = page_data.get(selected_page_details["report_key"], "No full report available.")

                    # Re-add dollar sign escaping for both
                    escaped_summary = summary_content.replace("$", "\$")
                    escaped_full_report = full_report_content.replace("$", "\$")

                    # Display Summary
                    st.markdown("**Summary:**")
                    st.markdown(escaped_summary)
                    st.markdown("---")

                    # Display Full Report in an Expander
                    with st.expander("View Full Report"):
                        st.markdown(escaped_full_report)
                else:
                    st.error("An error occurred displaying the selected analysis.")

        else:
            st.warning("No analysis results available. Go back to upload documents.")
            if st.button("Back to Upload"):
                st.session_state.view = 'upload'
                st.rerun()