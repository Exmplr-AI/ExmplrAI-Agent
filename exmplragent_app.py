import streamlit as st
from openai import OpenAI
import requests
import json


# Configuration: Exmplr API and OpenAI
API_BASE_URL = st.secrets["EXMPLR_API_URL"]
API_KEY = st.secrets["EXMPLR_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

if not API_BASE_URL or not API_KEY:
    raise ValueError("EXMPLR_API_URL or EXMPLR_API_KEY environment variable is not set.")

HEADERS = {"apikey": API_KEY, "Content-Type": "application/json"}

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Streamlit Configurations
st.set_page_config(page_title="Exmplr Conversational Agent", layout="wide")
st.markdown(
    "<style>body { background-color: #fff; color: #000; font-family: Arial, sans-serif; }</style>",
    unsafe_allow_html=True,
)

# Title and Description
st.title("Exmplr Conversational Agent")
st.write("A conversational agent for querying clinical trials and demographic data using Exmplr APIs.")

# Initialize Session State for Messages and Parameters
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "params" not in st.session_state:
    st.session_state["params"] = {
        "search_query": None, "size": 10, "from": 0, "paged_request": True, "age_from": "0", "age_to": "100",
        "gender": None, "race": None, "ethnicity": None, "intervention_type": None, "study": None, "location": None,
        "study_posted_from_year": None, "study_posted_to_year": None, "allocation": None, "sponsor_type": None,
        "sponsor": None, "show_only_results": True, "searched_for_condition_intervention": None, "intervention": None,
        "weight_scheme": "reference_citations", "exclusion_crit_text": None, "phase": None, "status_of_study": None
    }

# Retrieve parameters from session state
params_dict = st.session_state["params"]

# Display chat history
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input box for user message
if prompt := st.chat_input("Ask me about clinical trials..."):
    # Append user message to session state
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Use GPT-4 to extract parameters from the user's query
    system_prompt = (
        "You are a clinical trial assistant. The user is asking about clinical trials. "
        "Extract a disease name from the user's query and generate a JSON payload for the Exmplr API. "
        "Ensure the JSON object includes all the following fields, even if set to null: \n"
        "search_query (disease name), size (default 10), from (default 0), paged_request (default true), "
        "age_from (default '0'), age_to (default '100'), gender, race, ethnicity, intervention_type, study, location, "
        "study_posted_from_year, study_posted_to_year, allocation, sponsor_type, sponsor, show_only_results (default true), "
        "searched_for_condition_intervention, intervention, weight_scheme (default 'reference_citations'), "
        "exclusion_crit_text, phase, and status_of_study. Ensure weight_scheme is always included. "
        "If the query does not specify a disease, generate a valid default value for search_query."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
        )
        params = response.choices[0].message.content
        params_dict.update(json.loads(params))  # Update session state with extracted parameters
        st.session_state["params"] = params_dict

        # st.write("Payload being sent to the API:", params_dict)

        # Fetch results
        with st.spinner("Fetching results..."):
            api_response = requests.post(f"{API_BASE_URL}/listoftrialswithfilters", headers=HEADERS, json=params_dict)
            if api_response.status_code == 200:
                data = api_response.json()
                trials = data.get("hits", {}).get("hits", [])

                if trials:
                    num_trials = data.get("hits", {}).get("total", {}).get("value", 0)
                    api_result = f"### I found {num_trials} trials. Here are the top results:\n"
                    for idx, trial in enumerate(trials[:5], start=1):
                        api_result += (
                            f"**{idx}. {trial['_source']['brief_title']}**\n"
                            f"- **Status:** {trial['_source']['overall_status']}\n"
                            f"- **Phase:** {trial['_source'].get('phase', 'N/A')}\n"
                            f"- **Conditions:** {', '.join(trial['_source']['condition'])}\n"
                            f"- **Sponsor:** {trial['_source'].get('lead_sponsor', {}).get('agency', 'N/A')}\n"
                            f"---\n"
                        )
                    st.markdown(api_result)

                    # Interactive Suggestions
                    with st.container():
                        st.write("Would you like to refine your search?")
                        col1, col2, col3 = st.columns(3)

                        # Phase Selection Dropdown
                        with col1:
                            selected_phase = st.selectbox("Choose a phase to filter:", ["", "Phase 1", "Phase 2", "Phase 3", "Phase 4"])
                            if st.button("Apply Phase Filter"):
                                if selected_phase:
                                    params_dict["phase"] = selected_phase
                                    st.session_state["params"] = params_dict
                                    st.session_state["messages"].append(
                                        {"role": "assistant", "content": f"Phase filter applied: {selected_phase}"}
                                    )
                                    # Re-run the query
                                    st.experimental_rerun()

                        # View More Results Button
                        with col2:
                            if st.button("View More Results"):
                                params_dict["from"] += 5  # Adjust to load next set of results
                                st.session_state["params"] = params_dict
                                st.session_state["messages"].append(
                                    {"role": "assistant", "content": "Loading more results..."}
                                )
                                # Re-run the query
                                st.experimental_rerun()

                        # Location Change Input
                        with col3:
                            new_location = st.text_input("Enter a new location to refine your search:")
                            if st.button("Apply Location Filter"):
                                if new_location:
                                    params_dict["location"] = new_location
                                    st.session_state["params"] = params_dict
                                    st.session_state["messages"].append(
                                        {"role": "assistant", "content": f"Location filter applied: {new_location}"}
                                    )
                                    # Re-run the query
                                    st.experimental_rerun()
                else:
                    st.warning("No trials found for the given query.")
            else:
                st.error(f"API Error: {api_response.status_code}")
    except Exception as e:
        st.error(f"Error processing your request: {str(e)}")
