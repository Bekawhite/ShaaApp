# SHA_Connect.py
# Kisumu County Referral Hospital - SHA Awareness Platform
# Fully integrated: multilingual UI, FAQs & chatbot (OpenAI optional),
# SMS/Voice (Twilio optional), persistent local caching, outbox queue, analytics, partners, feedback, reminders, dashboard.
#
# Usage:
# 1. put this file in a folder
# 2. create a ./data folder (the app will create it automatically)
# 3. set credentials in Streamlit secrets or environment variables:
#    - For Twilio (optional): in Streamlit secrets
#        [twilio]
#        account_sid = "ACxxxxx"
#        auth_token = "xxxx"
#        from_number = "+1...."
#    - For OpenAI (optional): in Streamlit secrets
#        [openai]
#        api_key = "sk-..."
#
# Run: streamlit run SHA_Connect.py

import streamlit as st
import pandas as pd
import numpy as np
import datetime
import os
import json
import traceback

# Optional dependencies (import safely)
try:
    from twilio.rest import Client as TwilioClient
except Exception:
    TwilioClient = None

try:
    import openai
except Exception:
    openai = None

try:
    from googletrans import Translator as GTTranslator
except Exception:
    GTTranslator = None

# ---------------------------
# Configuration & data paths
# ---------------------------
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

PARTNERS_FILE = os.path.join(DATA_DIR, "partners.json")
MESSAGES_FILE = os.path.join(DATA_DIR, "message_logs.json")
FEEDBACK_FILE = os.path.join(DATA_DIR, "feedback.json")
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")
OUTBOX_FILE = os.path.join(DATA_DIR, "outbox.json")
MESSAGE_LOG_FILE = MESSAGES_FILE  # Alias for consistency

# ---------------------------
# Helpers: JSON persistence
# ---------------------------
def save_df_to_file(df: pd.DataFrame, path: str):
    try:
        # to_json with force_ascii=False preserves unicode (local languages)
        df.to_json(path, orient="records", force_ascii=False, date_format="iso")
    except Exception:
        # fallback using python json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

def load_df_from_file(path: str, columns=None):
    if not os.path.isfile(path):
        if columns:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame()
    try:
        df = pd.read_json(path, orient="records")
        if columns:
            # ensure expected columns exist
            for c in columns:
                if c not in df.columns:
                    df[c] = ""
            return df[columns]
        return df
    except Exception:
        try:
            with open(path, "r", encoding="utf-8") as f:
                records = json.load(f)
            df = pd.DataFrame(records)
            if columns:
                for c in columns:
                    if c not in df.columns:
                        df[c] = ""
                return df[columns]
            return df
        except Exception:
            return pd.DataFrame()

# ---------------------------
# App UI / startup
# ---------------------------
st.set_page_config(page_title="SHA Connect — Kisumu County Referral Hospital", layout="wide")

# Initialize session state for language if not exists
if 'selected_language' not in st.session_state:
    st.session_state.selected_language = "English"

# Sidebar navigation
st.sidebar.title("Navigation")
PAGES = [
    "Home",
    "FAQs & Chatbot",
    "Multilingual Messages",
    "Outreach Partners",
    "Community Feedback",
    "Notifications & Reminders",
    "Campaign Dashboard",
    "Outbox",
    "Settings"
]
choice = st.sidebar.radio("Go to:", PAGES)

language_options = ["English", "Swahili", "Luo", "Luhya"]
# Update language selection in session state
new_language = st.sidebar.selectbox("Choose Language:", language_options, 
                                   index=language_options.index(st.session_state.selected_language) 
                                   if st.session_state.selected_language in language_options else 0)
st.session_state.selected_language = new_language

# Set page title with translation
page_titles = {
    "English": "SHA Connect — Kisumu County Referral Hospital",
    "Swahili": "SHA Unganisha — Hospitali ya Riferi ya Kaunti ya Kisumu",
    "Luo": "SHA Connect — Kisumu County Referral Hospital",
    "Luhya": "SHA Khumanyana — Hospitali ya Riferi ya Kaunti ya Kisumu"
}

st.title(page_titles.get(st.session_state.selected_language, "SHA Connect — Kisumu County Referral Hospital"))

# ---------------------------
# Load persisted data into session state
# ---------------------------
if "partners_df" not in st.session_state:
    st.session_state.partners_df = load_df_from_file(PARTNERS_FILE, columns=["Name", "Role", "Language", "Contact", "Campaign Assigned"])

if "message_logs" not in st.session_state:
    st.session_state.message_logs = load_df_from_file(MESSAGES_FILE, columns=["Recipient", "Message", "Language", "Date Sent", "Type", "Status"])

if "feedback_df" not in st.session_state:
    st.session_state.feedback_df = load_df_from_file(FEEDBACK_FILE, columns=["Name", "Message", "Language", "Date Submitted"])

if "reminders_df" not in st.session_state:
    st.session_state.reminders_df = load_df_from_file(REMINDERS_FILE, columns=["Task", "Due Date", "Assigned To", "Status"])

if "outbox_df" not in st.session_state:
    st.session_state.outbox_df = load_df_from_file(OUTBOX_FILE, columns=["Recipient", "Message", "Language", "Date Created", "Type", "Attempts", "Status"])

# ---------------------------
# FAQ data
# ---------------------------
faqs = {
    "What is SHA?": "SHA stands for Social Health Authority, which provides health services and benefits.",
    "How can I register for SHA?": "You can register at your nearest health center or via the SHA portal.",
    "Which services are covered?": "SHA covers preventive care, maternal care, and essential treatments.",
    "Is SHA free or do I need to pay?": "Some services are free, but others may require a small contribution depending on the package.",
    "Who is eligible for SHA?": "All Kenyan citizens and residents are eligible to register for SHA.",
    "Can I use SHA in any hospital?": "Yes, SHA can be used in all public hospitals and selected private facilities.",
    "Does SHA cover emergencies?": "Yes, SHA covers emergency medical care.",
    "Can I register my children under SHA?": "Yes, dependents such as children and spouses can be included.",
    "How do I check if I am registered?": "You can check your registration status online or at a health center.",
    "What should I do if I lose my SHA card?": "Visit your nearest health center or SHA office to request a replacement."
}

# ---------------------------
# Translation utilities and custom translations
# ---------------------------
faq_translations = {
    "English": {
        "What is SHA?": "SHA stands for Social Health Authority, which provides health services and benefits.",
        "How can I register for SHA?": "You can register at your nearest health center or via the SHA portal.",
        "Which services are covered?": "SHA covers preventive care, maternal care, and essential treatments.",
        "Is SHA free or do I need to pay?": "Some services are free, but others may require a small contribution depending on the package.",
        "Who is eligible for SHA?": "All Kenyan citizens and residents are eligible to register for SHA.",
        "Can I use SHA in any hospital?": "Yes, SHA can be used in all public hospitals and selected private facilities.",
        "Does SHA cover emergencies?": "Yes, SHA covers emergency medical care.",
        "Can I register my children under SHA?": "Yes, dependents such as children and spouses can be included.",
        "How do I check if I am registered?": "You can check your registration status online or at a health center.",
        "What should I do if I lose my SHA card?": "Visit your nearest health center or SHA office to request a replacement.",
        "Thank you for your feedback!": "Thank you for your feedback!",
        "Home": "Home",
        "FAQs & Chatbot": "FAQs & Chatbot",
        "Multilingual Messages": "Multilingual Messages",
        "Outreach Partners": "Outreach Partners",
        "Community Feedback": "Community Feedback",
        "Notifications & Reminders": "Notifications & Reminders",
        "Campaign Dashboard": "Campaign Dashboard",
        "Outbox": "Outbox",
        "Settings": "Settings",
        "Send": "Send",
        "Submit": "Submit",
        "Add": "Add",
        "Search": "Search",
        "Process All Messages": "Process All Messages",
        "Retry Failed Only": "Retry Failed Only",
        "Clear All Failed": "Clear All Failed",
        "Save All Data Now": "Save All Data Now",
        "Reload All Data": "Reload All Data"
    },

    "Swahili": {
        "SHA ni nini?": "SHA inamaanisha Mamlaka ya Afya ya Jamii, ambayo inatoa huduma na manufaa ya afya.",
        "Ninawezaje kujisajili kwa SHA?": "Unaweza kujisajili katika kituo cha afya kilicho karibu nawe au kupitia tovuti ya SHA.",
        "Huduma zipi zinashughulikiwa?": "SHA inagharamia huduma za kinga, huduma za uzazi, na matibabu muhimu.",
        "Je, SHA ni bure au nahitaji kulipa?": "Baadhi ya huduma ni bure, lakini zingine zinahitaji mchango mdogo kulingana na kifurushi.",
        "Nani anastahiki kwa SHA?": "Raia wote wa Kenya na wakaazi wanastahiki kujisajili kwa SHA.",
        "Je, naweza kutumia SHA katika hospitali yoyote?": "Ndiyo, SHA inatumika katika hospitali zote za umma na vituo binafsi vilivyochaguliwa.",
        "Je, SHA inashughulikia dharura?": "Ndiyo, SHA inashughulikia huduma za dharura za matibabu.",
        "Naweza kusajili watoto wangu chini ya SHA?": "Ndiyo, wategemezi kama watoto na wenzi wanaweza kuingizwa.",
        "Ninawezaje kujua kama nimesajiliwa?": "Unaweza kuangalia hali ya usajili mtandaoni au katika kituo cha afya.",
        "Nifanye nini nikikosa kadi ya SHA?": "Tembelea kituo cha afya kilicho karibu nawe au ofisi ya SHA kuomba kadi mpya.",
        "Asante kwa maoni yako!": "Asante kwa maoni yako!",
        "Home": "Nyumbani",
        "FAQs & Chatbot": "Maswali Yanayoulizwa Mara Kwa Mara & Msaidizi",
        "Multilingual Messages": "Ujumbe wa Lugha Nyingi",
        "Outreach Partners": "Washirika wa Ufikiaji",
        "Community Feedback": "Maoni ya Jamii",
        "Notifications & Reminders": "Arifa na Vikumbusho",
        "Campaign Dashboard": "Dashibodi ya Kampeni",
        "Outbox": "Kikasha cha Kutuma",
        "Settings": "Mipangilio",
        "Send": "Tuma",
        "Submit": "Wasilisha",
        "Add": "Ongeza",
        "Search": "Tafuta",
        "Process All Messages": "Fanyia Kazi Ujumbe Wote",
        "Retry Failed Only": "Jaribu Tena Ushindwaji Pekee",
        "Clear All Failed": "Futa Yaliyoshindwa Yote",
        "Save All Data Now": "Hifadhi Data Yote Sasa",
        "Reload All Data": "Pakia Upya Data Yote"
    },

    "Luo": {
        "SHA en ang'o?": "SHA en Social Health Authority, ma orit gi dhok yi mondo giko gi bedo mag dhok.",
        "Nadi inyalo bedo e SHA?": "Inyalo registr kendo e health center maduong' gi e SHA portal.",
        "Nadi tiende ma SHA oyudo?": "SHA en giko mag preventive care, maternal care, kod treatments ma nyaka.",
        "SHA en nono kata inyalo chulogi?": "Kitiyo moko en nono, to moko nyalo kawo chul kata matin machielo.",
        "Ng'a ma inyalo bedo gi SHA?": "Jodak Kenya duto gi joma nigi res ngima inyalo bedo gi SHA.",
        "Inyalo tiyo gi SHA e hospital moro amora?": "Ee, inyalo tiyo gi SHA e hospitala duto ma ja-State gi moko ma obedo approved.",
        "SHA biro orito emergencies?": "Ee, SHA biro konyo e ndalo ma emergency.",
        "Nadi inyalo keto nyithindo e SHA?": "Ee, nyithindo gi mon ma inyalo keto e kaka dependents.",
        "Nadi inyalo ng'eyo ka abedo registered?": "Inyalo temo ka in registered online kata e health center.",
        "Nadi anyalo yudo kadi ma obiro ka aluwo?": "Dhi e health center maduong' kata SHA office mondo inyal goyo kadi manyien.",
        "Erokamano kuom paro ni!": "Awuoyo gi nyalo walo!",
        "Home": "Ot",
        "FAQs & Chatbot": "Penj Kendo Kendo & Mony Kwer",
        "Multilingual Messages": "Tik ma lwongo moko",
        "Outreach Partners": "Joot ma onyiso",
        "Community Feedback": "Paro ma joot",
        "Notifications & Reminders": "Pwony kod gwoko",
        "Campaign Dashboard": "Dashboard ma Campaign",
        "Outbox": "Outbox",
        "Settings": "Golo moko",
        "Send": "Oro",
        "Submit": "Iro",
        "Add": "Medo",
        "Search": "Yien",
        "Process All Messages": "Timo Tik Duto",
        "Retry Failed Only": "Temo Manyien ma Omedo",
        "Clear All Failed": "Weche ma Omedo Duto",
        "Save All Data Now": "Goyo Data Duto Sani",
        "Reload All Data": "Lo Data Duto Manyien"
    },

    "Luhya": {
        "SHA nindi?": "SHA ni Social Health Authority, ebuya amagara netaweire.",
        "Wekha okhulikhila ku SHA nindi?": "Olwikhilire kuhealth center oba e SHA portal.",
        "Nindi ebisese ebyo SHA ibuyire?": "SHA ibuyire preventive care, maternal care, ne essential treatments.",
        "SHA nibere bukhaya nende mbela?": "Ebisese bimu nibere bukhaya, naye ebirala bulikhilanga obusolo butiti.",
        "Niwenyefwa wosi bali nende SHA?": "Abandu bosi be Kenya nende abakhaya nibasungulwa khukhila ku SHA.",
        "Nisena khukozesa SHA mu hospital esio yosi?": "Ee, SHA nibakhozesa mu hospitala yosi yebukhaya nende bimu bia private bibakhulile.",
        "SHA ibachuranga emergency?": "Ee, SHA ibachuranga obulala obwa emergency.",
        "Nisena khusangila abana bange mu SHA?": "Ee, abana nende musakhulu nibasambwa khuli dependents.",
        "Nisena khwiyanza khukhwola obwikhilile bwanje?": "Wena khwiyanza khukhwola online oba mu health center.",
        "Nisena khwiyanza khwibula khadi ya SHA?": "Leka health center oba SHA office khukhwola khadi emupi.",
        "Webale muno okhu": "Webale muno okhu",
        "Home": "Emukaro",
        "FAQs & Chatbot": "Ebibulo Ebikhongo & Omusaidizi",
        "Multilingual Messages": "Ebifuma ebilwanga mubulayi",
        "Outreach Partners": "Abasaidizi bokusania",
        "Community Feedback": "Ebiro byomukaro",
        "Notifications & Reminders": "Ebimanyisio nende ebikumbusho",
        "Campaign Dashboard": "Dashboard yomukhung'ano",
        "Outbox": "Ebilayi okhuruma",
        "Settings": "Ebiandikhwo",
        "Send": "Ruma",
        "Submit": "Ebisia",
        "Add": "Ongeza",
        "Search": "Khwenya",
        "Process All Messages": "Khola ebifuma ebiosi",
        "Retry Failed Only": "Elinga ebiosi ebifwile",
        "Clear All Failed": "Sasania ebiosi ebifwile",
        "Save All Data Now": "Tega data yosi sani",
        "Reload All Data": "Lola data yosi manyasi"
    }
}

def safe_translate(text: str, lang: str) -> str:
    """
    FAQ translation helper:
    - If text exists in chosen language: return it
    - Else, return the original text
    """
    if not text:
        return text
    return faq_translations.get(lang, {}).get(text, text)

# ---------------------------
# Configuration checkers
# ---------------------------
def twilio_configured():
    try:
        return (st.secrets.has_key("twilio") and 
                st.secrets["twilio"]["account_sid"] and 
                st.secrets["twilio"]["auth_token"] and 
                st.secrets["twilio"]["from_number"])
    except:
        return False

def openai_configured():
    try:
        return (st.secrets.has_key("openai") and 
                st.secrets["openai"]["api_key"])
    except:
        return False

def configure_openai_api():
    if openai_configured() and openai:
        openai.api_key = st.secrets["openai"]["api_key"]
        return True
    return False

# ---------------------------
# Twilio functions
# ---------------------------
def safe_send_sms(to_number, message):
    if not twilio_configured() or TwilioClient is None:
        return False, "Twilio not configured"
    
    try:
        client = TwilioClient(st.secrets["twilio"]["account_sid"], st.secrets["twilio"]["auth_token"])
        message = client.messages.create(
            body=message,
            from_=st.secrets["twilio"]["from_number"],
            to=to_number
        )
        return True, f"SMS sent: {message.sid}"
    except Exception as e:
        return False, f"Twilio error: {str(e)}"

def safe_make_call(to_number, message):
    if not twilio_configured() or TwilioClient is None:
        return False, "Twilio not configured"
    
    try:
        client = TwilioClient(st.secrets["twilio"]["account_sid"], st.secrets["twilio"]["auth_token"])
        # For voice calls, we'd typically use TwiML, but this is a simplified version
        # In a real implementation, you'd create a TwiML response and point to it
        call = client.calls.create(
            twiml=f'<Response><Say>{message}</Say></Response>',
            from_=st.secrets["twilio"]["from_number"],
            to=to_number
        )
        return True, f"Call initiated: {call.sid}"
    except Exception as e:
        return False, f"Twilio error: {str(e)}"

# ---------------------------
# Outbox management (with Status column + UI tables + Process Button)
# ---------------------------
def add_to_outbox(recipient, message, language, msg_type="sms"):
    row = {
        "Recipient": recipient,
        "Message": message,
        "Language": language,
        "Date Created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Type": msg_type,
        "Attempts": 0,
        "Status": "Pending",
    }
    st.session_state.outbox_df = pd.concat(
        [st.session_state.outbox_df, pd.DataFrame([row])], ignore_index=True
    )
    save_df_to_file(st.session_state.outbox_df, OUTBOX_FILE)
    st.success("Message queued to outbox.")

def process_outbox(max_attempts=3):
    if st.session_state.outbox_df.empty:
        st.info("Outbox is empty.")
        return []

    results = []
    for idx, row in st.session_state.outbox_df.copy().iterrows():
        attempts = int(row.get("Attempts", 0))

        if attempts >= max_attempts:
            st.session_state.outbox_df.at[idx, "Status"] = "Failed"
            results.append((idx, False, "max attempts reached"))
            continue

        recipient = row["Recipient"]
        message = row["Message"]
        msg_type = row.get("Type", "sms")
        language = row.get("Language", "English")

        # Try to send
        if msg_type == "sms":
            ok, info = safe_send_sms(recipient, message)
        else:
            ok, info = safe_make_call(recipient, message)

        # Update attempts
        st.session_state.outbox_df.at[idx, "Attempts"] = attempts + 1

        if ok:
            # Success -> log + remove from outbox
            sent_row = {
                "Recipient": recipient,
                "Message": message,
                "Language": language,
                "Date Sent": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Type": msg_type,
                "Status": "Sent",
            }
            st.session_state.message_logs = pd.concat(
                [st.session_state.message_logs, pd.DataFrame([sent_row])],
                ignore_index=True,
            )
            st.session_state.outbox_df = st.session_state.outbox_df.drop(idx)
            results.append((idx, True, info))
        else:
            # Still retrying or permanently failed
            if attempts + 1 < max_attempts:
                st.session_state.outbox_df.at[idx, "Status"] = "Retrying"
            else:
                st.session_state.outbox_df.at[idx, "Status"] = "Failed"
            results.append((idx, False, info))

    # Save state
    save_df_to_file(st.session_state.outbox_df, OUTBOX_FILE)
    save_df_to_file(st.session_state.message_logs, MESSAGES_FILE)
    return results

# ---------------------------
# Utility: persist all main tables
# ---------------------------
def persist_all():
    save_df_to_file(st.session_state.partners_df, PARTNERS_FILE)
    save_df_to_file(st.session_state.message_logs, MESSAGES_FILE)
    save_df_to_file(st.session_state.feedback_df, FEEDBACK_FILE)
    save_df_to_file(st.session_state.reminders_df, REMINDERS_FILE)
    save_df_to_file(st.session_state.outbox_df, OUTBOX_FILE)

# ---------------------------
# Pages / Functionality
# ---------------------------
if choice == "Home":
    st.subheader(safe_translate("Home", st.session_state.selected_language))
    st.markdown(safe_translate("""
    - Learn about SHA services.
    - Access resources and community outreach events.
    - Use the sidebar to navigate: FAQs & Chatbot, Messaging, Partners, Feedback, Reminders, Dashboard.
    """, st.session_state.selected_language))
    st.info(safe_translate("App caches data locally in ./data — this helps in areas with intermittent internet. Use the Outbox page to re-send queued messages when network is back.", st.session_state.selected_language))

# ---------------------------
# FAQs & Chatbot
# ---------------------------
elif choice == "FAQs & Chatbot":
    st.subheader(safe_translate("FAQs", st.session_state.selected_language))
    for q, a in faqs.items():
        with st.expander(safe_translate(q, st.session_state.selected_language)):
            st.write(safe_translate(a, st.session_state.selected_language))

    st.subheader(safe_translate("Ask the Chatbot", st.session_state.selected_language))
    user_input = st.text_input(safe_translate("Type your question here:", st.session_state.selected_language))
    if st.button(safe_translate("Get Answer", st.session_state.selected_language)):
        if not user_input:
            st.warning(safe_translate("Please enter a question.", st.session_state.selected_language))
        else:
            # Prefer OpenAI if configured and available
            if openai and configure_openai_api():
                try:
                    # Use ChatCompletion (gpt-3.5-turbo or gpt-4 depending on user)
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "system", "content": "You are a helpful assistant for SHA health services in Kisumu. Keep answers short and local-language friendly."},
                                  {"role": "user", "content": user_input}]
                    )
                    answer = response.choices[0].message.content.strip()
                    st.markdown(f"**{safe_translate('Chatbot (AI) Response:', st.session_state.selected_language)}** {safe_translate(answer, st.session_state.selected_language)}")
                except Exception as e:
                    st.error(f"OpenAI error: {e}")
                    # fallback to simple keyword-based reply
                    fallback = "Sorry, I couldn't fetch an AI response. Here is a simple answer attempt."
                    for q, a in faqs.items():
                        if user_input.lower() in q.lower() or user_input.lower() in a.lower():
                            fallback = a
                            break
                    st.markdown(f"**{safe_translate('Chatbot (Fallback):', st.session_state.selected_language)}** {safe_translate(fallback, st.session_state.selected_language)}")
            else:
                # simple keyword-based chatbot
                response = "Sorry, I don't have an answer for that yet."
                for q, a in faqs.items():
                    if user_input.lower() in q.lower() or user_input.lower() in a.lower():
                        response = a
                        break
                st.markdown(f"**{safe_translate('Chatbot Response:', st.session_state.selected_language)}** {safe_translate(response, st.session_state.selected_language)}")

# ---------------------------
# Multilingual Messages (SMS/Voice)
# ---------------------------
elif choice == "Multilingual Messages":
    st.subheader(safe_translate("Multilingual Messages", st.session_state.selected_language))
    if not twilio_configured() or TwilioClient is None:
        st.warning(safe_translate("⚠️ Twilio not configured or library missing. Messages will be queued to Outbox if 'Send' is attempted. "
                   "To enable live SMS/Voice, set Twilio credentials in Streamlit secrets or environment variables and install twilio library.", st.session_state.selected_language))

    # Recipient + message input
    recipient = st.text_input(safe_translate("Recipient phone number (with country code):", st.session_state.selected_language))
    msg_text = st.text_area(safe_translate("Message text", st.session_state.selected_language))

    # Language + message type
    col1, col2 = st.columns(2)
    with col1:
        msg_type = st.selectbox(safe_translate("Message Type", st.session_state.selected_language), ["sms", "voice"])
    with col2:
        msg_lang = st.selectbox(safe_translate("Message Language", st.session_state.selected_language), language_options, index=0)

    # Send button
    if st.button(safe_translate("Send", st.session_state.selected_language)):
        if not recipient or not msg_text:
            st.warning(safe_translate("⚠️ Please enter recipient and message.", st.session_state.selected_language))
        else:
            translated = safe_translate(msg_text, msg_lang)

            if msg_type == "sms":
                ok, info = safe_send_sms(recipient, translated) if twilio_configured() and TwilioClient else (False, "Twilio not configured")
                if ok:
                    st.success(f"✅ {safe_translate('SMS sent:', st.session_state.selected_language)} {info}")
                    log_row = {
                        "Recipient": recipient,
                        "Message": translated,
                        "Language": msg_lang,
                        "Date Sent": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Type": "sms",
                        "Status": "Sent"
                    }
                    st.session_state.message_logs = pd.concat([st.session_state.message_logs, pd.DataFrame([log_row])], ignore_index=True)
                    save_df_to_file(st.session_state.message_logs, MESSAGES_FILE)
                else:
                    st.error(f"❌ {safe_translate('Send failed:', st.session_state.selected_language)} {info} — {safe_translate('queued to Outbox.', st.session_state.selected_language)}")
                    add_to_outbox(recipient, translated, msg_lang, msg_type="sms")

            else:  # voice call
                ok, info = safe_make_call(recipient, translated) if twilio_configured() and TwilioClient else (False, "Twilio not configured")
                if ok:
                    st.success(f"📞 {safe_translate('Voice call initiated:', st.session_state.selected_language)} {info}")
                    log_row = {
                        "Recipient": recipient,
                        "Message": translated,
                        "Language": msg_lang,
                        "Date Sent": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Type": "voice",
                        "Status": "Sent"
                    }
                    st.session_state.message_logs = pd.concat([st.session_state.message_logs, pd.DataFrame([log_row])], ignore_index=True)
                    save_df_to_file(st.session_state.message_logs, MESSAGES_FILE)
                else:
                    st.error(f"❌ {safe_translate('Voice send failed:', st.session_state.selected_language)} {info} — {safe_translate('queued to Outbox.', st.session_state.selected_language)}")
                    add_to_outbox(recipient, translated, msg_lang, msg_type="voice")

    # Note about translations
    st.caption(safe_translate("ℹ️ Messages will use FAQ translations if available, otherwise Google Translate will be used for free text.", st.session_state.selected_language))

    # Recent messages log
    st.markdown(f"#### {safe_translate('Recent Messages', st.session_state.selected_language)}")
    if not st.session_state.message_logs.empty:
        st.dataframe(st.session_state.message_logs.sort_values("Date Sent", ascending=False).head(15))
    else:
        st.info(safe_translate("No messages logged yet.", st.session_state.selected_language))

# ---------------------------
# Outreach Partners
# ---------------------------
elif choice == "Outreach Partners":
    st.subheader(safe_translate("Outreach Partners", st.session_state.selected_language))

    # Add Partner
    with st.expander(f"➕ {safe_translate('Add New Partner', st.session_state.selected_language)}"):
        name = st.text_input(safe_translate("Partner Name", st.session_state.selected_language))
        role = st.selectbox(safe_translate("Role", st.session_state.selected_language), ["Community Leader", "Influencer", "Volunteer"])
        langs = st.multiselect(safe_translate("Languages Spoken", st.session_state.selected_language), language_options)
        contact = st.text_input(safe_translate("Contact Info (phone/email)", st.session_state.selected_language))
        campaign = st.text_input(safe_translate("Campaign Assigned", st.session_state.selected_language))
        if st.button(safe_translate("Add", st.session_state.selected_language)):
            if not name:
                st.warning(safe_translate("Partner name is required.", st.session_state.selected_language))
            else:
                new_partner = {
                    "Name": name,
                    "Role": role,
                    "Language": ", ".join(langs),
                    "Contact": contact,
                    "Campaign Assigned": campaign
                }
                st.session_state.partners_df = pd.concat(
                    [st.session_state.partners_df, pd.DataFrame([new_partner])],
                    ignore_index=True
                )
                save_df_to_file(st.session_state.partners_df, PARTNERS_FILE)
                st.success(f"{safe_translate('Partner', st.session_state.selected_language)} {name} {safe_translate('added.', st.session_state.selected_language)}")

    # Show registered partners
    st.markdown(f"#### {safe_translate('Registered Partners', st.session_state.selected_language)}")
    if not st.session_state.partners_df.empty:
        st.dataframe(st.session_state.partners_df)
    else:
        st.info(safe_translate("No partners registered yet.", st.session_state.selected_language))

    # Search
    search = st.text_input(f"🔍 {safe_translate('Search', st.session_state.selected_language)} {safe_translate('partner by name', st.session_state.selected_language)}")
    if search:
        filtered = st.session_state.partners_df[
            st.session_state.partners_df["Name"].str.contains(search, case=False, na=False)
        ]
        st.dataframe(filtered)

    # --- New: Send Message to Partner ---
    if not st.session_state.partners_df.empty:
        st.markdown(f"### 📩 {safe_translate('Send Message to Partner', st.session_state.selected_language)}")
        partner_names = st.session_state.partners_df["Name"].tolist()
        selected_partner = st.selectbox(safe_translate("Select Partner", st.session_state.selected_language), partner_names)

        if selected_partner:
            partner_row = st.session_state.partners_df[
                st.session_state.partners_df["Name"] == selected_partner
            ].iloc[0]

            st.write(f"**{safe_translate('Role:', st.session_state.selected_language)}** {partner_row['Role']}")
            st.write(f"**{safe_translate('Contact:', st.session_state.selected_language)}** {partner_row['Contact']}")
            st.write(f"**{safe_translate('Languages:', st.session_state.selected_language)}** {partner_row['Language']}")

            msg_text = st.text_area(safe_translate("Message text", st.session_state.selected_language))
            msg_type = st.radio(safe_translate("Message Type", st.session_state.selected_language), ["sms", "voice"], horizontal=True)

            if st.button(safe_translate("Send Message", st.session_state.selected_language)):
                if not msg_text:
                    st.warning(safe_translate("⚠️ Please enter a message.", st.session_state.selected_language))
                else:
                    # Pick first language listed
                    preferred_lang = partner_row["Language"].split(",")[0].strip() if partner_row["Language"] else "English"
                    translated = safe_translate(msg_text, preferred_lang)

                    if msg_type == "sms":
                        ok, info = safe_send_sms(partner_row["Contact"], translated) if twilio_configured() and TwilioClient else (False, "Twilio not configured")
                        if ok:
                            st.success(f"✅ {safe_translate('SMS sent to', st.session_state.selected_language)} {partner_row['Name']}: {info}")
                        else:
                            st.error(f"❌ {safe_translate('Send failed:', st.session_state.selected_language)} {info} — {safe_translate('queued to Outbox.', st.session_state.selected_language)}")
                            add_to_outbox(partner_row["Contact"], translated, preferred_lang, msg_type="sms")
                    else:  # voice
                        ok, info = safe_make_call(partner_row["Contact"], translated) if twilio_configured() and TwilioClient else (False, "Twilio not configured")
                        if ok:
                            st.success(f"📞 {safe_translate('Voice call initiated to', st.session_state.selected_language)} {partner_row['Name']}: {info}")
                        else:
                            st.error(f"❌ {safe_translate('Voice send failed:', st.session_state.selected_language)} {info} — {safe_translate('queued to Outbox.', st.session_state.selected_language)}")
                            add_to_outbox(partner_row["Contact"], translated, preferred_lang, msg_type="voice")


# ---------------------------
# Community Feedback
# ---------------------------
elif choice == "Community Feedback":
    st.subheader(safe_translate("Community Feedback", st.session_state.selected_language))
    
    # Feedback form
    with st.form("feedback_form"):
        name = st.text_input(safe_translate("Your Name (optional)", st.session_state.selected_language))
        feedback = st.text_area(safe_translate("Your Feedback", st.session_state.selected_language), height=100)
        feedback_lang = st.selectbox(safe_translate("Language of Feedback", st.session_state.selected_language), language_options)
        submitted = st.form_submit_button(safe_translate("Submit Feedback", st.session_state.selected_language))
        
        if submitted:
            if not feedback:
                st.warning(safe_translate("Please enter your feedback.", st.session_state.selected_language))
            else:
                new_feedback = {
                    "Name": name if name else "Anonymous",
                    "Message": feedback,
                    "Language": feedback_lang,
                    "Date Submitted": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.feedback_df = pd.concat(
                    [st.session_state.feedback_df, pd.DataFrame([new_feedback])],
                    ignore_index=True
                )
                save_df_to_file(st.session_state.feedback_df, FEEDBACK_FILE)
                st.success(safe_translate("Thank you for your feedback!", st.session_state.selected_language))
    
    # View feedback
    st.markdown(f"#### {safe_translate('Recent Feedback', st.session_state.selected_language)}")
    if not st.session_state.feedback_df.empty:
        for _, row in st.session_state.feedback_df.sort_values("Date Submitted", ascending=False).head(10).iterrows():
            with st.expander(f"{row['Name']} - {row['Date Submitted']} - {row['Language']}"):
                st.write(row['Message'])
    else:
        st.info(safe_translate("No feedback submitted yet.", st.session_state.selected_language))

# ---------------------------
# Notifications & Reminders
# ---------------------------
elif choice == "Notifications & Reminders":
    st.subheader(safe_translate("Notifications & Reminders", st.session_state.selected_language))
    
    # Add reminder
    with st.expander(f"➕ {safe_translate('Add New Reminder', st.session_state.selected_language)}"):
        task = st.text_input(safe_translate("Task/Reminder", st.session_state.selected_language))
        due_date = st.date_input(safe_translate("Due Date", st.session_state.selected_language))
        assigned_to = st.text_input(safe_translate("Assigned To", st.session_state.selected_language))
        status = st.selectbox(safe_translate("Status", st.session_state.selected_language), ["Pending", "In Progress", "Completed"])
        
        if st.button(safe_translate("Add Reminder", st.session_state.selected_language)):
            if not task:
                st.warning(safe_translate("Please enter a task.", st.session_state.selected_language))
            else:
                new_reminder = {
                    "Task": task,
                    "Due Date": due_date.strftime("%Y-%m-%d"),
                    "Assigned To": assigned_to,
                    "Status": status
                }
                st.session_state.reminders_df = pd.concat(
                    [st.session_state.reminders_df, pd.DataFrame([new_reminder])],
                    ignore_index=True
                )
                save_df_to_file(st.session_state.reminders_df, REMINDERS_FILE)
                st.success(safe_translate("Reminder added!", st.session_state.selected_language))
    
    # View reminders
    st.markdown(f"#### {safe_translate('Current Reminders', st.session_state.selected_language)}")
    if not st.session_state.reminders_df.empty:
        # Filter by status
        status_filter = st.multiselect(
            safe_translate("Filter by Status", st.session_state.selected_language),
            options=["Pending", "In Progress", "Completed"],
            default=["Pending", "In Progress"]
        )
        
        filtered_reminders = st.session_state.reminders_df[
            st.session_state.reminders_df["Status"].isin(status_filter)
        ]
        
        if not filtered_reminders.empty:
            for _, row in filtered_reminders.iterrows():
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{row['Task']}**")
                    st.write(f"Assigned to: {row['Assigned To']}")
                with col2:
                    st.write(f"Due: {row['Due Date']}")
                    st.write(f"Status: {row['Status']}")
                with col3:
                    if st.button(safe_translate("Complete", st.session_state.selected_language), key=f"complete_{_}"):
                        st.session_state.reminders_df.at[_, "Status"] = "Completed"
                        save_df_to_file(st.session_state.reminders_df, REMINDERS_FILE)
                        st.experimental_rerun()
        else:
            st.info(safe_translate("No reminders match the selected filters.", st.session_state.selected_language))
    else:
        st.info(safe_translate("No reminders set yet.", st.session_state.selected_language))

# ---------------------------
# Campaign Dashboard
# ---------------------------
elif choice == "Campaign Dashboard":
    st.subheader(safe_translate("Campaign Dashboard", st.session_state.selected_language))
    
    # Statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(safe_translate("Total Partners", st.session_state.selected_language), len(st.session_state.partners_df))
    
    with col2:
        st.metric(safe_translate("Messages Sent", st.session_state.selected_language), len(st.session_state.message_logs))
    
    with col3:
        st.metric(safe_translate("Pending Feedback", st.session_state.selected_language), len(st.session_state.feedback_df))
    
    with col4:
        pending_reminders = len(st.session_state.reminders_df[st.session_state.reminders_df["Status"].isin(["Pending", "In Progress"])])
        st.metric(safe_translate("Active Reminders", st.session_state.selected_language), pending_reminders)
    
    # Message statistics by language
    st.markdown(f"#### {safe_translate('Messages by Language', st.session_state.selected_language)}")
    if not st.session_state.message_logs.empty:
        lang_counts = st.session_state.message_logs["Language"].value_counts()
        st.bar_chart(lang_counts)
    else:
        st.info(safe_translate("No message data available.", st.session_state.selected_language))
    
    # Recent activity
    st.markdown(f"#### {safe_translate('Recent Activity', st.session_state.selected_language)}")
    
    # Combine recent messages and feedback
    recent_activity = []
    
    if not st.session_state.message_logs.empty:
        for _, row in st.session_state.message_logs.sort_values("Date Sent", ascending=False).head(5).iterrows():
            recent_activity.append({
                "type": "Message",
                "date": row["Date Sent"],
                "details": f"{row['Type']} to {row['Recipient']} in {row['Language']}"
            })
    
    if not st.session_state.feedback_df.empty:
        for _, row in st.session_state.feedback_df.sort_values("Date Submitted", ascending=False).head(5).iterrows():
            recent_activity.append({
                "type": "Feedback",
                "date": row["Date Submitted"],
                "details": f"From {row['Name']} in {row['Language']}"
            })
    
    if recent_activity:
        # Sort by date
        recent_activity.sort(key=lambda x: x["date"], reverse=True)
        
        for activity in recent_activity[:10]:
            st.write(f"**{activity['type']}** - {activity['date']}: {activity['details']}")
    else:
        st.info(safe_translate("No recent activity.", st.session_state.selected_language))

# ---------------------------
# Outbox Management
# ---------------------------
elif choice == "Outbox":
    st.subheader(safe_translate("Outbox", st.session_state.selected_language))
    
    if not st.session_state.outbox_df.empty:
        st.info(safe_translate("Messages waiting to be sent. They will be retried automatically when you click 'Process'.", st.session_state.selected_language))
        
        # Show outbox table
        st.dataframe(st.session_state.outbox_df)
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button(safe_translate("Process All Messages", st.session_state.selected_language)):
                results = process_outbox()
                if results:
                    st.success(f"Processed {len([r for r in results if r[1]])} messages successfully.")
                    for idx, success, info in results:
                        if not success:
                            st.error(f"Message {idx}: {info}")
        
        with col2:
            if st.button(safe_translate("Retry Failed Only", st.session_state.selected_language)):
                # Mark failed messages as Pending for retry
                failed_mask = st.session_state.outbox_df["Status"] == "Failed"
                if failed_mask.any():
                    st.session_state.outbox_df.loc[failed_mask, "Status"] = "Pending"
                    st.session_state.outbox_df.loc[failed_mask, "Attempts"] = 0
                    save_df_to_file(st.session_state.outbox_df, OUTBOX_FILE)
                    st.success(f"Marked {failed_mask.sum()} failed messages for retry.")
                else:
                    st.info(safe_translate("No failed messages to retry.", st.session_state.selected_language))
        
        with col3:
            if st.button(safe_translate("Clear All Failed", st.session_state.selected_language)):
                failed_mask = st.session_state.outbox_df["Status"] == "Failed"
                if failed_mask.any():
                    st.session_state.outbox_df = st.session_state.outbox_df[~failed_mask]
                    save_df_to_file(st.session_state.outbox_df, OUTBOX_FILE)
                    st.success(f"Cleared {failed_mask.sum()} failed messages.")
                else:
                    st.info(safe_translate("No failed messages to clear.", st.session_state.selected_language))
    else:
        st.info(safe_translate("Outbox is empty.", st.session_state.selected_language))

# ---------------------------
# Settings
# ---------------------------
elif choice == "Settings":
    st.subheader(safe_translate("Settings", st.session_state.selected_language))
    
    # Configuration status
    st.markdown(f"#### {safe_translate('Service Status', st.session_state.selected_language)}")
    
    twilio_status = "✅ Configured" if twilio_configured() else "❌ Not Configured"
    openai_status = "✅ Configured" if openai_configured() else "❌ Not Configured"
    
    st.write(f"**Twilio:** {twilio_status}")
    st.write(f"**OpenAI:** {openai_status}")
    
    # Data management
    st.markdown(f"#### {safe_translate('Data Management', st.session_state.selected_language)}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(safe_translate("Save All Data Now", st.session_state.selected_language)):
            persist_all()
            st.success(safe_translate("All data saved successfully.", st.session_state.selected_language))
    
    with col2:
        if st.button(safe_translate("Reload All Data", st.session_state.selected_language)):
            st.session_state.partners_df = load_df_from_file(PARTNERS_FILE, columns=["Name", "Role", "Language", "Contact", "Campaign Assigned"])
            st.session_state.message_logs = load_df_from_file(MESSAGES_FILE, columns=["Recipient", "Message", "Language", "Date Sent", "Type", "Status"])
            st.session_state.feedback_df = load_df_from_file(FEEDBACK_FILE, columns=["Name", "Message", "Language", "Date Submitted"])
            st.session_state.reminders_df = load_df_from_file(REMINDERS_FILE, columns=["Task", "Due Date", "Assigned To", "Status"])
            st.session_state.outbox_df = load_df_from_file(OUTBOX_FILE, columns=["Recipient", "Message", "Language", "Date Created", "Type", "Attempts", "Status"])
            st.success(safe_translate("All data reloaded from disk.", st.session_state.selected_language))
    
    # Data export
    st.markdown(f"#### {safe_translate('Data Export', st.session_state.selected_language)}")
    
    if st.button(safe_translate("Export All Data as CSV", st.session_state.selected_language)):
        # Create a zip file with all data
        import zipfile
        import io
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            # Add each dataframe as a CSV
            zip_file.writestr("partners.csv", st.session_state.partners_df.to_csv(index=False))
            zip_file.writestr("messages.csv", st.session_state.message_logs.to_csv(index=False))
            zip_file.writestr("feedback.csv", st.session_state.feedback_df.to_csv(index=False))
            zip_file.writestr("reminders.csv", st.session_state.reminders_df.to_csv(index=False))
            zip_file.writestr("outbox.csv", st.session_state.outbox_df.to_csv(index=False))
        
        zip_buffer.seek(0)
        st.download_button(
            label=safe_translate("Download ZIP", st.session_state.selected_language),
            data=zip_buffer,
            file_name="sha_connect_data_export.zip",
            mime="application/zip"
        )

# ---------------------------
# Footer
# ---------------------------
st.sidebar.markdown("---")
st.sidebar.info(safe_translate("Kisumu County Referral Hospital - SHA Awareness Platform", st.session_state.selected_language))

# Auto-save on exit
import atexit
atexit.register(persist_all)
