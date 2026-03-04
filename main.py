import os
import requests
import uvicorn
from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# مكتبات Vonage الرسمية
from vonage import Auth, Vonage
from vonage_messages.models import WhatsappText

load_dotenv()

# --- الإعدادات ---
ALLOWED_NUMBER = "967774440982"

# إعداد التوثيق (يجب تشفير الـ Private Key أو رفعه كملف)
base_dir = os.path.dirname(os.path.realpath(__file__))
private_key_path = os.path.join(base_dir, "private.key")

auth = Auth(
    application_id=os.getenv("VONAGE_APPLICATION_ID"),
    private_key=private_key_path,
)
vonage_client = Vonage(auth)

# إعداد Gemini 2.5 Flash
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

app = FastAPI()

# إعداد المسار المطلق للمجلد لضمان تحميل الصفحة على Render
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

# --- الوظائف المساعدة ---

def get_gemini_response(user_input: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": user_input}]}],
        "system_instruction": {"parts": [{"text": "أنت مساعد ذكي تتواصل مع الرقم 967774440982 فقط."}]}
    }
    try:
        res = requests.post(GEMINI_URL, json=payload, timeout=15)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "عذراً، واجهت مشكلة في معالجة طلبك."

def send_whatsapp(to_number: str, message_text: str):
    clean_number = to_number.replace("+", "").replace(" ", "").strip()
    if clean_number != ALLOWED_NUMBER:
        return
    try:
        msg = WhatsappText(
            from_=os.getenv("VONAGE_SANDBOX_NUMBER"),
            to=clean_number,
            text=message_text
        )
        vonage_client.messages.send(msg)
    except Exception as e:
        print(f"Error sending: {e}")

# --- المسارات (Endpoints) ---

@app.get("/", response_class=HTMLResponse)
async def render_home(request: Request):
    """عرض الصفحة الرئيسية"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/inbound")
async def handle_v_webhook(request: Request):
    """استقبال رسائل واتساب"""
    try:
        data = await request.json()
        sender = data.get("from", "").replace("+", "").strip()
        text = data.get("text") or data.get("message", {}).get("content", {}).get("text")
        
        if sender == ALLOWED_NUMBER and text:
            reply = get_gemini_response(text)
            send_whatsapp(sender, reply)
    except:
        pass
    return Response(status_code=200)

@app.post("/send_message")
async def web_manual_send(message: str = Form(...)):
    """إرسال من واجهة الويب"""
    send_whatsapp(ALLOWED_NUMBER, message)
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
