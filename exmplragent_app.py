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

# Title and Description
st.title("Exmplr AI Conversational Agent")
st.write("Engage in a conversation about healthcare studies, treatments, and more.")

# Initialize Session State for Messages and Parameters
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Hi! How can I assist you today?"}
    ]
if "params" not in st.session_state:
    st.session_state["params"] = {
        "search_query": None, "size": 10, "from": 0, "paged_request": True, "age_from": "0", "age_to": "100",
        "gender": "All", "race": None, "ethnicity": None, "intervention_type": None, "study": None, "location": None,
        "study_posted_from_year": None, "study_posted_to_year": None, "allocation": None, "sponsor_type": None,
        "sponsor": None, "show_only_results": None, "searched_for_condition_intervention": None, "intervention": None,
        "weight_scheme": "reference_citations", "exclusion_crit_text": None, "phase": None, "status_of_study": None
    }

# System prompt for OpenAI
system_prompt = """
You are a clinical trial assistant. The user is asking about clinical trials. 
Extract the required parameters for the Exmplr API and return only a valid JSON object.

The JSON object must include the following fields (default values where applicable):
- search_query (disease name or topic)
- size (default 10)
- from (default 0)
- paged_request (default true)
- age_from (default "0")
- age_to (default "100")
- gender (default "All")
- race (default null)
- ethnicity (default null)
- intervention_type (default null)
- study (default null)
- location (default null)
- study_posted_from_year (default null)
- study_posted_to_year (default null)
- allocation (default null)
- sponsor_type (default null)
- sponsor (default null)
- show_only_results (default null)
- searched_for_condition_intervention (default null)
- intervention (default null)
- weight_scheme (default "reference_citations")
- exclusion_crit_text (default null)
- phase (default null)
- status_of_study (default null)

Always ensure the output is a valid JSON object. Do not include additional text or explanations.
"""

# Function to clean up parameters and capitalize values
def clean_params(params):
    for key, value in params.items():
        if value == "":
            params[key] = None  # Convert empty strings to null
        elif key == "location" and isinstance(value, str):
            params[key] = "United States" if value.lower() in ["us", "united states"] else value.title()
        elif isinstance(value, str):
            params[key] = value.capitalize()  # Capitalize string values
    return params

# Function to handle refined user queries
def handle_refined_query(refinement_prompt):
    try:
        # Use GPT to process the refinement prompt and extract new parameters
        conversation_context = [
            {"role": msg["role"], "content": msg["content"]} for msg in st.session_state["messages"]
        ]

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": system_prompt}] + conversation_context
        )

        # Extract and clean new parameters
        assistant_response = response.choices[0].message.content
        extracted_params = json.loads(assistant_response)
        st.session_state["params"].update(clean_params(extracted_params))

        # Log the refined parameters
        st.write("Updated Parameters for Refined Query:", st.session_state["params"])

        # Make the refined API call
        with st.spinner("Fetching refined healthcare study data..."):
            api_response = requests.post(
                f"{API_BASE_URL}/listoftrialswithfilters", headers=HEADERS, json=st.session_state["params"]
            )
            if api_response.status_code == 200:
                data = api_response.json()
                trials = data.get("hits", {}).get("hits", [])

                if trials:
                    num_trials = data.get("hits", {}).get("total", {}).get("value", 0)
                    trial_list = f"### Found {num_trials} studies. Here are some highlights:\n"
                    for idx, trial in enumerate(trials[:5], start=1):
                        trial_list += (
                            f"**{trial['_source']['brief_title']}**\n"
                            f"Status: {trial['_source']['overall_status']}, Phase: {trial['_source'].get('phase', 'N/A')}, Sponsor: {trial['_source'].get('lead_sponsor', {}).get('agency', 'N/A')}\n\n"
                        )
                    st.session_state["messages"].append({"role": "assistant", "content": trial_list})
                    with st.chat_message("assistant"):
                        st.markdown(trial_list)
                else:
                    st.warning("No studies found for the refined query.")
            else:
                st.error(f"API Error: {api_response.status_code} - {api_response.text}")
    except Exception as e:
        st.error(f"Error processing the refined query: {str(e)}")

# Display chat history
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input box for user message
if prompt := st.chat_input("What's on your mind today?"):
    # Append user message to session state
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        # Query OpenAI API
        conversation_context = [
            {"role": msg["role"], "content": msg["content"]} for msg in st.session_state["messages"]
        ]

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": system_prompt}] + conversation_context
        )

        # Extract the assistant's response
        assistant_response = response.choices[0].message.content

        # Append assistant response to chat
        st.session_state["messages"].append({"role": "assistant", "content": assistant_response})
        with st.chat_message("assistant"):
            st.markdown(assistant_response)

        # Parse the response as JSON
        try:
            extracted_params = json.loads(assistant_response)
            st.session_state["params"].update(clean_params(extracted_params))  # Update and clean API parameters

            # Call Exmplr API
            with st.spinner("Fetching healthcare study data..."):
                api_response = requests.post(
                    f"{API_BASE_URL}/listoftrialswithfilters", headers=HEADERS, json=st.session_state["params"]
                )
                if api_response.status_code == 200:
                    data = api_response.json()
                    trials = data.get("hits", {}).get("hits", [])

                    if trials:
                        num_trials = data.get("hits", {}).get("total", {}).get("value", 0)
                        trial_list = f"### Found {num_trials} studies. Here are some highlights:\n"
                        for idx, trial in enumerate(trials[:5], start=1):
                            trial_list += (
                                f"**{trial['_source']['brief_title']}**\n"
                                f"Status: {trial['_source']['overall_status']}, Phase: {trial['_source'].get('phase', 'N/A')}, Sponsor: {trial['_source'].get('lead_sponsor', {}).get('agency', 'N/A')}\n\n"
                            )
                        st.session_state["messages"].append({"role": "assistant", "content": trial_list})
                        with st.chat_message("assistant"):
                            st.markdown(trial_list)

                        # Ask follow-up question
                        follow_up = "Would you like to refine the search further, such as by location, phase, or a specific condition?"
                        st.session_state["messages"].append({"role": "assistant", "content": follow_up})
                        with st.chat_message("assistant"):
                            st.markdown(follow_up)

                    else:
                        st.warning("No studies found for the given query.")
                else:
                    st.error(f"API Error: {api_response.status_code} - {api_response.text}")

        except json.JSONDecodeError:
            st.error("The assistant's response could not be parsed as JSON. Please refine your query.")

    except Exception as e:
        st.error(f"Error processing your request: {str(e)}")
