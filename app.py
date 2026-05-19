import streamlit as st
import requests
import google.generativeai as genai
from supabase import create_client, Client

# --- Setup & Configuration ---
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# Initialize Clients
genai.configure(api_key=GEMINI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram API Error: {e}")

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
            # 1. Send details to your Telegram
            send_telegram_message(
                f"🚨 *New Chatbot User*\n*Name:* {name}\n*WS:* {ws_number}\n*Email:* {email}"
            )
            
            # 2. Attempt to record to Supabase
            try:
                supabase.table("users").insert({
                    "name": name,
                    "ws_number": ws_number,
                    "email": email
                }).execute()
            except Exception as e:
                print(f"Supabase Insert Error: {e}") 
            
            # 3. Save to session and move to chat interface
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

        system_instructions = """
        You are a strict coding assistant. You ONLY answer programming errors, debugging questions, and code logic. 
        If the user asks ANYTHING else (general questions, chit-chat, non-coding requests), you must reply with EXACTLY this string and nothing else: FORWARD_TO_HUMAN
        """
        
        full_prompt = f"{system_instructions}\n\nUser query: {prompt}"
        
        with st.chat_message("assistant"):
            try:
                response = model.generate_content(full_prompt)
                reply = response.text.strip()
                
                # Trigger Telegram fallback
                if reply == 'FORWARD_TO_HUMAN':
                    fallback_msg = "I only handle code errors. Your query has been forwarded to the administrator."
                    st.markdown(fallback_msg)
                    st.session_state.messages.append({"role": "assistant", "content": fallback_msg})
                    
                    # Send the query to your Telegram
                    tele_msg = f"⚠️ *Non-Coding Query*\n*User:* {st.session_state.user_info['name']} ({st.session_state.user_info['ws']})\n*Query:* {prompt}"
                    send_telegram_message(tele_msg)
                else:
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                st.error("Error connecting to Google API. Please check your API key.")
