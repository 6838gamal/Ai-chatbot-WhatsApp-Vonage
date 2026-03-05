import os
import requests
import uvicorn
from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# استيراد المكتبة حسب التوثيق الذي يعمل لديك
from vonage import Vonage, Auth, HttpClientOptions
from vonage_messages.models import WhatsappText

load_dotenv()

# --- الإعدادات ---
ALLOWED_NUMBER = "967774440982"
APP_ID = os.getenv("VONAGE_APPLICATION_ID")
PRIVATE_KEY_PATH = os.getenv("VONAGE_PRIVATE_KEY_PATH", "private.key")
SANDBOX_NUMBER = os.getenv("VONAGE_SANDBOX_NUMBER", "14157386102")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI()
base_dir = os.path.dirname(os.path.realpath(__file__))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

# --- إعداد Vonage ---
options = HttpClientOptions(api_host="messages-sandbox.nexmo.com")
auth = Auth(application_id=APP_ID, private_key=PRIVATE_KEY_PATH)
vonage_client = Vonage(auth=auth, http_client_options=options)

# --- وظيفة Gemini ---
def get_gemini_response(user_input: str) -> str:
    # أبقينا على النسخة 2.5 فلاش
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": user_input}]}]
    }
    
    try:
        res = requests.post(url, json=payload, timeout=15)
        res_data = res.json()
        
        # هذا السطر مهم جداً لنعرف سبب الفشل في الـ Logs
        if res.status_code != 200:
            print(f"❌ Gemini Error Details: {res_data}") 
            return "عذراً، واجهت مشكلة في معالجة الرد الذكي."
            
        return res_data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return "عذراً، حدث خطأ في الاتصال."

# --- وظيفة الإرسال ---
def send_whatsapp(to_number: str, message_text: str):
    clean_to = to_number.replace("+", "").strip()
    clean_from = SANDBOX_NUMBER.replace("+", "").strip()
    
    try:
        msg = WhatsappText(from_=clean_from, to=clean_to, text=message_text)
        response = vonage_client.messages.send(msg)
        print(f"✅ Message Sent! UUID: {response.message_uuid}")
    except Exception as e:
        print(f"❌ Vonage Send Error: {e}")

# --- المسارات ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/inbound")
async def webhook(request: Request):
    try:
        data = await request.json()
        sender = data.get("from", "").replace("+", "").strip()
        text = data.get("text") or data.get("message", {}).get("content", {}).get("text")
        
        if sender == ALLOWED_NUMBER and text:
            reply = get_gemini_response(text)
            send_whatsapp(sender, reply)
    except Exception as e:
        print(f"Webhook Error: {e}")
    return Response(status_code=200)

@app.post("/send_message")
async def web_send(message: str = Form(...)):
    send_whatsapp(ALLOWED_NUMBER, message)
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
