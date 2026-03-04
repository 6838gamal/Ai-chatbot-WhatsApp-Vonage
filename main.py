import os
import requests
import uvicorn
from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# استيراد مكتبة Vonage الحديثة
from vonage import Auth, Vonage
from vonage_messages.models import WhatsappText

load_dotenv()

# --- الإعدادات الثابتة ---
ALLOWED_NUMBER = "967774440982"

# إعداد التوثيق باستخدام التطبيق (Application-based) حسب توثيق 2026
auth = Auth(
    application_id=os.getenv("VONAGE_APPLICATION_ID"),
    private_key=os.getenv("VONAGE_PRIVATE_KEY_PATH"), # يجب أن يكون ملف private.key في المجلد
)
vonage_client = Vonage(auth)

# إعداد Gemini 2.5 Flash
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def get_gemini_response(user_input: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": user_input}]}],
        "system_instruction": {"parts": [{"text": "أنت مساعد ذكي ولطيف تتواصل مع الرقم 967774440982."}]}
    }
    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=15)
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "عذراً، حدث خطأ في معالجة الرد."

def send_whatsapp(to_number: str, text: str):
    # تنظيف الرقم من أي رموز زائدة
    clean_number = to_number.replace("+", "").replace(" ", "").strip()
    
    if clean_number != ALLOWED_NUMBER:
        print(f"🚫 محاولة محظورة للرقم: {clean_number}")
        return

    try:
        # إرسال الرسالة باستخدام الموديل الرسمي
        msg = WhatsappText(
            from_=os.getenv("VONAGE_SANDBOX_NUMBER"), 
            to=clean_number,
            text=text
        )
        vonage_client.messages.send(msg)
        print(f"✅ تم إرسال الرد إلى {clean_number}")
    except Exception as e:
        print(f"❌ خطأ Vonage: {e}")

# --- المسارات (Endpoints) ---

@app.post("/inbound")
async def inbound(request: Request):
    """استقبال رسائل الواتساب"""
    data = await request.json()
    
    # استخراج البيانات (حسب هيكل Vonage Sandbox)
    sender = data.get("from")
    message_text = data.get("message", {}).get("content", {}).get("text")
    
    # إذا لم ينجح الهيكل الأول، نجرب الهيكل البديل المباشر
    if not message_text:
        message_text = data.get("text")

    clean_sender = sender.replace("+", "").strip() if sender else ""

    if clean_sender == ALLOWED_NUMBER:
        reply = get_gemini_response(message_text)
        send_whatsapp(clean_sender, reply)
    
    return Response(status_code=200)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/send_message")
async def web_send(message: str = Form(...)):
    send_whatsapp(ALLOWED_NUMBER, message)
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    # تشغيل السيرفر على منفذ Render الافتراضي
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
