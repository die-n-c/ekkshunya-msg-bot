import os
import re
import html
import time
import requests
import datetime
import base64
import io
from flask import Flask, request, jsonify
import threading

# ==========================================
# 0. SERVERLESS CONFIGURATION
# ==========================================
PORT = int(os.environ.get("PORT", 8080))
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-my id")  

# Public networking layout for Render's free tier
WAHA_API_URL = "https://waha-whatsapp-engine.onrender.com"
WAHA_API_KEY = os.environ.get("WAHA_API_KEY", "mytoken")

# 🛠️ FIXED CONFIGURATION: Load the string explicitly from Render's environment panel
LOGO_BASE64 = os.environ.get("LOGO_BASE64")

# Temporary file storage path for history tracking
HEADLINE_FILE = "/tmp/last_headlines.txt"

WHATSAPP_DISTRIBUTION_LIST = [
    "918008415368@c.us",  
    "918527778966-1388598681@g.us",
    "919579301745@c.us",   
    "919160533864@c.us"   
]

# Debug logs to verify initialization settings upon boot
print("🤖 System profile initialized successfully.")
if LOGO_BASE64:
    print(f"📸 DEBUG: LOGO_BASE64 configuration loaded! Length: {len(LOGO_BASE64)} characters.")
else:
    print("⚠️ CRITICAL DEBUG: LOGO_BASE64 is completely EMPTY. Verify your Render Environment panel.")


# ==========================================
# 1. WHATSAPP DELIVERY ENGINE (WAHA PIPELINE)
# ==========================================
def send_to_my_whatsapp(text, recipient_id):
    print(f"📱 Sending to {recipient_id}...")
    
    # Check if logo exists
    if os.path.exists(LOGO_PATH):
        print(f"📸 Logo found at: {LOGO_PATH}")
        url = f"{WAHA_API_URL}/api/sendImage"
        headers = {"X-Api-Key": WAHA_API_KEY, "Content-Type": "application/json"}
        
        try:
            with open(LOGO_PATH, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                print(f"📸 Base64 string length: {len(b64)}")
            
            payload = {
                "session": "default",
                "chatId": recipient_id,
                "file": {
                    "mimetype": "image/png",
                    "data": b64,
                    "filename": "logo.png"
                },
                "caption": str(text)
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            print(f"🔍 WAHA Response Status: {response.status_code}")
            print(f"🔍 WAHA Response Body: {response.text[:200]}")
            
            if response.status_code in [200, 201]:
                print(f"✅ WhatsApp image card delivered to {recipient_id}!")
                return True
            else:
                print(f"⚠️ WAHA Image send failed (Status {response.status_code}): {response.text}")
        except Exception as e:
            print(f"⚠️ WAHA Image track bounced: {e}")
            import traceback
            traceback.print_exc()

    # PLAIN TEXT FALLBACK
    url_text = f"{WAHA_API_URL}/api/sendText"
    headers_text = {"X-Api-Key": WAHA_API_KEY, "Content-Type": "application/json"}
    payload_text = {"chatId": recipient_id, "text": text, "session": "default"}
    try:
        response = requests.post(url_text, json=payload_text, headers=headers_text, timeout=12)
        if response.status_code in [200, 201]:
            print(f"✅ WhatsApp plain text fallback delivered to {recipient_id}!")
            return True
        else:
            print(f"❌ WAHA Text send failed (Status {response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ WAHA text transmission exception: {e}")
    
    return False
# ==========================================
# 2. TELEGRAM POSTING PIPELINE
# ==========================================
def post_to_telegram(text, is_error=False):
    logo_b64_string = os.environ.get("LOGO_BASE64")
    print("📢 --- ENTERING post_to_telegram ---", flush=True)
    
    if not TELEGRAM_TOKEN:
        print("⚠️ Skipping Telegram: Token missing.", flush=True)
        return

    final_text = text
    if is_error:
        final_text = f"🚨 *WHATSAPP BROADCAST FAILED*\n\n{text}"

    # 📸 IN-MEMORY BASE64 IMAGE PIPELINE
    if logo_b64_string and not is_error:
        try:
            print("📸 INFO: Reconstituting Base64 string directly inside memory...", flush=True)
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            
            payload = {
                'chat_id': str(TELEGRAM_CHAT_ID), 
                'caption': final_text, 
                'parse_mode': 'Markdown'
            }
            
            raw_image_bytes = base64.b64decode(logo_b64_string)
            image_memory_file = io.BytesIO(raw_image_bytes)
            files = {'photo': ('logo.png', image_memory_file, 'image/png')}
            
            response = requests.post(url, data=payload, files=files, timeout=20)
            print(f"🔍 DEBUG: Telegram Image Response Status: {response.status_code}", flush=True)
            
            if response.status_code == 200:
                print("✅ SUCCESS: Base64 image card successfully posted to Telegram Channel!", flush=True)
                return
                
            elif response.status_code == 400 and "parse" in response.text.lower():
                print("⚠️ Telegram rejected Markdown format. Retrying photo with plain text caption...", flush=True)
                payload.pop('parse_mode', None)  
                image_memory_file.seek(0)  
                
                response = requests.post(url, data=payload, files=files, timeout=20)
                if response.status_code == 200:
                    print("✅ SUCCESS: Image card posted using plain text fallback!", flush=True)
                    return

            print(f"❌ FAIL: Telegram photo post rejected. Response details: {response.text}", flush=True)
        except Exception as e:
            print(f"❌ EXCEPTION during Base64 memory pipeline image send: {e}", flush=True)
    else:
        if is_error:
            print("⚠️ Skipping image because is_error=True", flush=True)
        else:
            print("⚠️ Skipping image: LOGO_BASE64 environment variable is missing on Render.", flush=True)

    # 📝 TEXT ONLY BACKUP PATHWAY
    print("📝 Shifting to text-only transmission pathway...", flush=True)
    url_text = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload_text = {
        'chat_id': str(TELEGRAM_CHAT_ID), 
        'text': final_text, 
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url_text, json=payload_text, timeout=10)
        
        if response.status_code == 400 and "parse" in response.text.lower():
            print("⚠️ Text Markdown broke parsing constraints. Retrying as plain text...", flush=True)
            payload_text.pop('parse_mode', None)
            response = requests.post(url_text, json=payload_text, timeout=10)
            
        if response.status_code == 200:
            print("✅ Text transaction successful.", flush=True)
        else:
            print(f"❌ Text send completely rejected by Telegram: {response.text}", flush=True)
    except Exception as e:
        print(f"❌ Text transmission layer experienced hard crash: {e}", flush=True)


# ==========================================
# 3. DYNAMIC CONTENT FETCHER (BRAVE SEARCH)
# ==========================================
def fetch_brave_content(query, result_type="snippet"):
    """
    Fetches fresh content from Brave Search API.
    """
    if not BRAVE_API_KEY or BRAVE_API_KEY == "YOUR_BRAVE_SEARCH_API_KEY_HERE":
        return None

    url = "https://api.search.brave.com/res/v1/web/search"
    if result_type == "news":
        url = "https://api.search.brave.com/res/v1/news/search"

    headers = {
        "X-Subscription-Token": BRAVE_API_KEY,
        "Accept-Encoding": "gzip",
        "Accept": "application/json"
    }
    
    params = {
        "q": query,
        "count": 3,
        "search_lang": "en",
        "country": "us"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            
            def clean_html(text):
                if not text:
                    return ""
                text = re.sub(r'<[^>]+>', '', text)
                return html.unescape(text)

            if result_type == "news":
                results = data.get("results", [])
                stories = []
                for item in results[:3]:
                    title = clean_html(item.get("title", ""))
                    link = item.get("url", "")
                    snippet = clean_html(item.get("description", ""))
                    if title and link:
                        stories.append({"title": title, "link": link})
                return stories
            
            else: 
                results = data.get("web", {}).get("results", [])
                if results:
                    raw_title = results[0].get("title", "")
                    raw_url = results[0].get("url", "")
                    raw_snippet = results[0].get("description", "")
                    
                    clean_title = clean_html(raw_title)
                    clean_snippet = clean_html(raw_snippet)
                    
                    clickable_title = f"[{clean_title}]({raw_url})"
                    
                    if len(clean_snippet) > 180:
                        clean_snippet = clean_snippet[:177] + "..."
                    
                    return f"🔗 Source: {clickable_title}\n\n💡 {clean_snippet}"
        
        return None
    except Exception as e:
        print(f"⚠️ Brave Search Error: {e}")
        return None

# ==========================================
# 4. ROTATIONAL CALENDAR LOGIC
# ==========================================
def get_daily_content():
    now = datetime.datetime.now()
    day_name = now.strftime("%A")
    formatted_date = now.strftime("%d %b %Y")
    header = f"⏰ *{day_name} - {formatted_date}*\n\n"
    
    if day_name == "Monday":
        stories = fetch_brave_content("top technology news last 24 hours", result_type="news")
        signature = "💼 *EkkShunya News - Connecting the World. ekkshunya.com*"
        if stories:
            return "Latest Tech News", f"{header}🤖 **Latest Tech News**\n\n{stories}\n\n{signature}", True
        return "Latest Tech News", f"{header}🤖 **Latest Tech News**\n\n😴 No fresh news found from Brave Search today.\n\n{signature}", False

    elif day_name == "Tuesday":
        content = fetch_brave_content("new AI tool or tech productivity tip 2026", "snippet")
        signature = "🤖 *EkkShunya AI - Automating the Future. ekkshunya.com*"
        msg = content if content else "💡 Learn one new shortcut today! (Search unavailable)"
        return "Tech or AI Tip", f"{header}🤖 *Tech or AI Tip*\n\n{msg}\n\n{signature}", False

    elif day_name == "Wednesday":
        content = fetch_brave_content("best career advice or financial tip for tech professionals 2026", "snippet")
        signature = "💰 *EkkShunya Wealth - Building Smart Careers. ekkshunya.com*"
        msg = content if content else "📈 Invest in your skills."
        return "Money or Career Tip", f"{header}💼 *Money or Career Tip*\n\n{msg}\n\n{signature}", False

    elif day_name == "Thursday":
        content = fetch_brave_content("interesting science fact or tech discovery this week", "snippet")
        signature = "🔬 *EkkShunya Science - Discovering the Unknown. ekkshunya.com*"
        msg = content if content else "🧠 Did you know? The first bug was a moth."
        return "Fun Fact or Science", f"{header}🔬 *Fun Fact or Science*\n\n{msg}\n\n{signature}", False

    elif day_name == "Friday":
        content = fetch_brave_content("productivity hack for developers or remote workers 2026", "snippet")
        signature = "⚡ *EkkShunya Flow - Mastering Efficiency. ekkshunya.com*"
        msg = content if content else "✅ End the week strong."
        return "Productivity Hack", f"{header}⚡ *Productivity Hack*\n\n{msg}\n\n{signature}", False

    elif day_name == "Saturday":
        content = fetch_brave_content("tech riddle or computer science quiz question with answer", "snippet")
        signature = "🧩 *EkkShunya Mind - Challenging Your Logic. ekkshunya.com*"
        msg = content if content else "🎯 I have keys but no locks."
        return "Quiz or Puzzle", f"{header}🧩 *Quiz or Puzzle*\n\n{msg}\n\n{signature}", False

    else: # Sunday
        content = fetch_brave_content("gratitude prompt or reflection question for Sunday", "snippet")
        signature = "🌱 *EkkShunya Soul - Reflecting & Recharging. ekkshunya.com*"
        msg = content if content else "✨ What are you grateful for?"
        return "Reflection or Gratitude Prompt", f"{header}🌱 *Reflection or Gratitude Prompt*\n\n{msg}\n\n{signature}", False

# ==========================================
# 5. CORE EXECUTION STEP CONTROL
# ==========================================
def execute_broadcast():
    print("🚀 Triggering daily distribution process pipeline...")
    
    try:
        theme, message, has_news = get_daily_content()
        print(f"DEBUG: Content fetched. Theme: '{theme}', Has News: {has_news}")
        if message:
            print(f"DEBUG: Message snippet preview (first 100 chars):\n{message[:100]}")
    except Exception as e:
        print(f"❌ CRITICAL: get_daily_content() crashed: {e}")
        post_to_telegram(f"CRITICAL ERROR: Content generation failed: {e}", LOGO_PATH, is_error=True)
        return
    
    if not message:
        print("⚠️ Content stream empty or returned None. Aborting distribution loop.")
        return

    # Removed Headline History Logic (Fresh content every time)

    success_count = 0
    error_messages = []
    
    print(f"🚀 Launching cluster broadcasts out to {len(WHATSAPP_DISTRIBUTION_LIST)} target contacts...")
    for recipient_id in WHATSAPP_DISTRIBUTION_LIST:
        print(f"📱 Forwarding payload packet directly to user row: {recipient_id}")
        try: 
            if send_to_my_whatsapp(message, recipient_id):
                success_count += 1
            else:
                error_messages.append(f"Failed to send to {recipient_id}")
        except Exception as e: 
            error_messages.append(f"Exception for {recipient_id}: {e}")
            print(f"❌ WhatsApp target broadcast error for {recipient_id}: {e}")
    
    print(f"🏁 Full distribution processing loop completed. Success: {success_count}/{len(WHATSAPP_DISTRIBUTION_LIST)}")

       # DETERMINE WHAT TO SEND TO TELEGRAM
    if success_count == 0 and error_messages:
        # ALL FAILED
        error_report = f"🚨 *WHATSAPP BROADCAST FAILED* (0/{len(WHATSAPP_DISTRIBUTION_LIST)} sent)\n\n"
        error_report += "The following message was prepared but WhatsApp failed to deliver:\n\n"
        error_report += "---\n"
        error_report += message
        error_report += "\n---\n\n"
        error_report += "Failed recipients:\n"
        for err in error_messages:
            error_report += f"• {err}\n"
        
        # ✅ Fixed Call
        post_to_telegram(error_report, is_error=True)
        
    elif success_count < len(WHATSAPP_DISTRIBUTION_LIST):
        # PARTIAL SUCCESS
        warning_msg = f"⚠️ *Partial Success*: Sent {success_count}/{len(WHATSAPP_DISTRIBUTION_LIST)}\n\n"
        warning_msg += "Failed recipients:\n"
        for err in error_messages:
            warning_msg += f"• {err}\n"
        warning_msg += "\n---\n\n"
        
        # ✅ Fixed Call
        post_to_telegram(warning_msg + message, is_error=True)
    else:
        # FULL SUCCESS
        # ✅ Fixed Call
        post_to_telegram(message, is_error=False)
# ==========================================
# 6. SERVER ENGINE & STEADY-STATE CLOCK TICKER
# ==========================================
app = Flask(__name__)

@app.route('/')
def keep_alive_ping_receiver():
    return "EkkShunya Messaging Engine is Active and Ready", 200
    
@app.route('/test-broadcast')
def manual_test_trigger():
    print("⚡ Manual test triggered via web browser! Executing delivery engine...")
    try:
        execute_broadcast()
        return "SUCCESS: Broadcast execution complete! Check your WhatsApp and Telegram channels.", 200
    except Exception as e:
        print(f"❌ Manual test crashed: {e}")
        return f"ERROR: The execution pipeline failed with error: {e}", 500

def clock_execution_loop():
    print("⏰ Background scheduling thread operational loop...")
    has_run_today = False
    
    while True:
        now = datetime.datetime.now()
        if now.hour == 9 and now.minute == 0:
            if not has_run_today:
                execute_broadcast()
                has_run_today = True
        elif now.hour == 10:
            has_run_today = False 
            
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=clock_execution_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
