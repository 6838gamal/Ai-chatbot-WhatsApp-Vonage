import os
import requests
import uvicorn
from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# الاستيراد الصحيح حسب التوثيق الذي أرسلته
from vonage import Vonage, Auth, HttpClientOptions
from vonage_messages.models import WhatsappText

load_dotenv()

# --- الإعدادات ---
ALLOWED_NUMBER = "967774440982"
APP_ID = os.getenv("VONAGE_APPLICATION_ID")
PRIVATE_KEY_PATH = os.getenv("VONAGE_PRIVATE_KEY_PATH", "private.key")
SANDBOX_NUMBER = os.getenv("VONAGE_SANDBOX_NUMBER", "14157386102")

app = FastAPI()
base_dir = os.path.dirname(os.path.realpath(__file__))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

# --- إعداد Vonage (بالطريقة الصحيحة الموثقة) ---
# استخدام HttpClientOptions لتوجيه الطلبات إلى الساندبوكس
options = HttpClientOptions(api_host="messages-sandbox.nexmo.com")

# التوثيق باستخدام التطبيق (Application ID + Private Key)
auth = Auth(
    application_id=APP_ID, 
    private_key=PRIVATE_KEY_PATH
)

# إنشاء العميل
vonage_client = Vonage(auth=auth, http_client_options=options)

# --- إعداد Gemini 2.5 Flash ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

def get_gemini_response(user_input: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": user_input}]}],
        "system_instruction": {"parts": [{"text": "أنت مساعد ذكي ولطيف تتواصل مع الرقم 967774440982."}]}
    }
    try:
        res = requests.post(GEMINI_URL, json=payload, timeout=10)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "عذراً، واجهت مشكلة في معالجة الرد."

def send_whatsapp(to_number: str, message_text: str):
    clean_to = to_number.replace("+", "").replace(" ", "").strip()
    clean_from = SANDBOX_NUMBER.replace("+", "").replace(" ", "").strip()
    
    try:
        msg = WhatsappText(from_=clean_from, to=clean_to, text=message_text)
        # الإرسال عبر خاصية messages كما في التوثيق
        response = vonage_client.messages.send(msg)
        print(f"✅ تم الإرسال بنجاح! UUID: {response.message_uuid}")
    except Exception as e:
        print(f"❌ فشل إرسال واتساب: {e}")

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
