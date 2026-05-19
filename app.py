import streamlit as st
import smtplib
from email.mime.text import MIMEText
import google.generativeai as genai
from supabase import create_client, Client

# --- Setup & Configuration ---
# Pulling secrets securely from Streamlit Cloud Secrets (DO NOT hardcode keys here!)
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
ADMIN_EMAIL = st.secrets["ADMIN_EMAIL"]
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]

# Initialize Clients
genai.configure(api_key=GEMINI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = ADMIN_EMAIL
    
    # Using Gmail SMTP
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, ADMIN_EMAIL, msg.as_string())
    except Exception as e:
        print(f"Failed to send email. Check your App Password. Error: {e}")

# --- User Interface ---
st.title("Carsem Code Error Assistant")

# 1. Ask for User Details first
if 'user_info' not in st.session_state:
    st.info("Please enter your details to start the chat.")
    with st.form("user_form"):
        name = st.text_input("Name")
        ws_number = st.text_input("WS Number")
        email = st.text_input("Carsem Email")
        submit = st.form_submit_button("Start Chat")
        
        if submit and name and ws_number and email:
            # 1. Send details to you via email first (most reliable)
            send_email(
                "New Chatbot User Registered", 
                f"Name: {name}\nWS: {ws_number}\nEmail: {email}"
            )
            
            # 2. Attempt to record to Supabase, but bypass quietly if it fails
            try:
                supabase.table("users").insert({
                    "name": name,
                    "ws_number": ws_number,
                    "email": email
                }).execute()
            except Exception as e:
                # Log the error quietly in the background, don't stop the user
                print(f"Supabase Insert Error: {e}") 
            
            # 3. Save to session and move to chat interface regardless of DB success
            st.session_state.user_info = {"name": name, "ws": ws_number, "email": email}
            st.rerun()

# 2. The Chatbot Interface
else:
    st.write(f"Welcome, **{st.session_state.user_info['name']}**! Paste your code error below.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Paste your code error here..."):
        # Show user message
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Prompt engineering to restrict Gemini to coding only
        system_instructions = """
        You are a strict coding assistant. You ONLY answer programming errors, debugging questions, and code logic. 
        If the user asks ANYTHING else (general questions, chit-chat, non-coding requests), you must reply with EXACTLY this string and nothing else: FORWARD_TO_HUMAN
        """
        
        full_prompt = f"{system_instructions}\n\nUser query: {prompt}"
        
        with st.chat_message("assistant"):
            try:
                response = model.generate_content(full_prompt)
                reply = response.text.strip()
                
                # If Gemini detects it's not a coding issue, trigger the email
                if reply == 'FORWARD_TO_HUMAN':
                    fallback_msg = "I only handle code errors. Your query has been forwarded to the administrator."
                    st.markdown(fallback_msg)
                    st.session_state.messages.append({"role": "assistant", "content": fallback_msg})
                    
                    # Send the actual query to your email
                    email_body = f"User: {st.session_state.user_info['name']} (WS: {st.session_state.user_info['ws']})\nCarsem Email: {st.session_state.user_info['email']}\n\nQuery: {prompt}"
                    send_email("Non-Coding Query Forwarded", email_body)
                else:
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                st.error("Error connecting to Google API. Please check your API key.")
