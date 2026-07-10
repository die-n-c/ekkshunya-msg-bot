import os
import re
import html
import time
import requests
import datetime
import base64
from flask import Flask
import threading

# ==========================================
# 0. SERVERLESS CONFIGURATION
# ==========================================
PORT = int(os.environ.get("PORT", 8080))
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-my id")  

# Internal bridge layout (Since WAHA runs inside the same Render blueprint cluster)
WAHA_API_URL = "https://waha-whatsapp-engine.onrender.com"
WAHA_API_KEY = os.environ.get("WAHA_API_KEY", "mytoken")

LOGO_PATH = "logo.png"
HEADLINE_FILE = "/tmp/last_headlines.txt" # Kept in safe serverless temp space

WHATSAPP_DISTRIBUTION_LIST = [
    "918008415368@c.us",  
    "918527778966-1388598681@g.us",
    "919579301745@c.us",   
    "919160533864@c.us"   
]

# ==========================================
# 1. WHATSAPP DELIVERY ENGINE (WAHA PIPELINE)
# ==========================================
def send_to_my_whatsapp(text, recipient_id):
    if os.path.exists(LOGO_PATH):
        print(f"📱 Base64 pipeline preparing logo drop for: {recipient_id}")
        url = f"{WAHA_API_URL}/api/sendImage"
        headers = {"X-Api-Key": WAHA_API_KEY, "Content-Type": "application/json"}
        try:
            with open(LOGO_PATH, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            
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
            if response.status_code == 200 or response.status_code == 201:
                print(f"✅ WhatsApp image card delivered to {recipient_id}!")
                return
        except Exception as e:
            print(f"⚠️ Image track bounced: {e}. Dropping to text fallback...")

    # PLAIN TEXT FALLBACK
    url_text = f"{WAHA_API_URL}/api/sendText"
    headers_text = {"X-Api-Key": WAHA_API_KEY, "Content-Type": "application/json"}
    payload_text = {"chatId": recipient_id, "text": text, "session": "default"}
    try:
        response = requests.post(url_text, json=payload_text, headers=headers_text, timeout=12)
        if response.status_code == 201 or response.status_code == 200:
            print(f"✅ WhatsApp plain text fallback delivered to {recipient_id}!")
    except Exception as e:
        print(f"❌ WAHA text transmission exception: {e}")

# ==========================================
# 2. TELEGRAM POSTING PIPELINE
# ==========================================
def post_to_telegram(text, photo_path):
    print("📢 Connecting to Telegram Engine...")
    if not TELEGRAM_TOKEN:
        print("⚠️ Skipping Telegram: Token missing.")
        return

    if os.path.exists(photo_path):
        url = f"https://telegram.org{TELEGRAM_TOKEN}/sendPhoto"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': text, 'parse_mode': 'Markdown'}
        try:
            with open(photo_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                response = requests.post(url, data=payload, files=files, timeout=15)
            if response.status_code == 200:
                print("✅ Successfully posted image card to Telegram Channel!")
                return
        except Exception as e:
            print(f"⚠️ Telegram Image crash: {e}. Attempting text backup...")

    # TEXT ONLY BACKUP
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Successfully posted text message to Telegram Channel!")
    except Exception as e:
        print(f"❌ Telegram textual pipeline error: {e}")
# ==========================================
# 3. DYNAMIC CONTENT FETCHER (BRAVE SEARCH)
# ==========================================
def fetch_brave_content(query, result_type="snippet"):
    if not BRAVE_API_KEY:
        return None

    url = "https://brave.com" if result_type == "snippet" else "https://brave.com"
    headers = {"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"}
    params = {"q": query, "count": 3, "search_lang": "en", "country": "us"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            clean_html = lambda text: html.unescape(re.sub(r'<[^>]+>', '', text)) if text else ""

            if result_type == "news":
                results = data.get("results", [])
                stories = []
                for item in results[:3]:
                    title = clean_html(item.get("title", ""))
                    link = item.get("url", "")
                    if title and link:
                        stories.append(f"• {title}\n🔗 Link: {link}")
                return "\n\n".join(stories) if stories else None
            
            else:
                results = data.get("web", {}).get("results", [])
                if results and len(results) > 0:
                    raw_title = clean_html(results[0].get("title", ""))
                    raw_url = results[0].get("url", "")
                    clean_snippet = clean_html(results[0].get("description", ""))
                    
                    if len(clean_snippet) > 180:
                        clean_snippet = clean_snippet[:177] + "..."
                    return f"🔗 Source: [{raw_title}]({raw_url})\n\n💡 {clean_snippet}"
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
    theme, message, has_news = get_daily_content()
    
    if not message:
        print("⚠️ Content stream empty. Aborting.")
        return

    if has_news:
        previous_headlines = set()
        if os.path.exists(HEADLINE_FILE):
            try:
                with open(HEADLINE_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    previous_headlines = set(line.strip() for line in f if line.strip())
            except Exception: pass
        
        lines = message.split("\n")
        first_story_title = lines[2] if len(lines) > 2 else ""
        if first_story_title and first_story_title in previous_headlines:
            print("😴 Latest news already sent previously. Skipping broadcast.")
            return
        
        try:
            with open(HEADLINE_FILE, "a", encoding="utf-8", errors="ignore") as f:
                for line in lines:
                    if line.strip() and not line.startswith("🤖") and not line.startswith("💼"):
                        f.write(line.strip() + "\n")
            print("📝 Saved news headlines to temp file history tracker.")
        except Exception as e:
            print(f"⚠️ History tracking file append exception: {e}")

    try: post_to_telegram(message, LOGO_PATH)
    except Exception as e: print(f"❌ Telegram pipeline threw: {e}")
        
    print(f"🚀 Launching cluster broadcasts out to {len(WHATSAPP_DISTRIBUTION_LIST)} target contacts...")
    for recipient_id in WHATSAPP_DISTRIBUTION_LIST:
        try: send_to_my_whatsapp(message, recipient_id)
        except Exception as e: print(f"❌ WhatsApp target broadcast error for {recipient_id}: {e}")

# ==========================================
# 6. SERVER ENGINE & STEADY-STATE CLOCK TICKER
# ==========================================
app = Flask(__name__)

@app.route('/')
def keep_alive_ping_receiver():
    return "EkkShunya Messaging Engine is Active and Ready", 200
    
# 🛠️ ADD THIS TEST ROUTE RIGHT HERE:
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
