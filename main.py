import os
import requests
import json
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# استيراد مكتبة Vonage الرسمية
from vonage import Vonage, Auth
from vonage_messages.models import WhatsappText

load_dotenv()

# --- الإعدادات ---
# الرقم المسموح به (بدون علامة + وبدون مسافات)
ALLOWED_NUMBER = "967774440982"

VONAGE_API_KEY = os.getenv("VONAGE_API_KEY")
VONAGE_API_SECRET = os.getenv("VONAGE_API_SECRET")
VONAGE_SANDBOX_NUMBER = os.getenv("VONAGE_SANDBOX_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# إعداد عميل Vonage
auth = Auth(api_key=VONAGE_API_KEY, api_secret=VONAGE_API_SECRET)
vonage_client = Vonage(auth=auth)

# رابط Gemini 2.5 Flash
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

app = FastAPI(title="WhatsApp Gemini 2.5 Bot")
templates = Jinja2Templates(directory="templates")

def get_gemini_response(user_input: str) -> str:
    """الحصول على رد من Gemini 2.5"""
    payload = {
        "contents": [{"parts": [{"text": user_input}]}],
        "system_instruction": {"parts": [{"text": "أنت مساعد ذكي ولطيف تتواصل عبر واتساب باللغة العربية."}]}
    }
    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "عذرًا، واجهت مشكلة في معالجة الرد الذكي."

def send_whatsapp(to_number: str, message_text: str):
    """إرسال رسالة واتساب مع تنظيف الرقم"""
    # تنظيف الرقم من أي رموز مثل + ليتوافق مع Pattern المكتبة
    clean_number = to_number.replace("+", "").replace(" ", "").strip()
    
    # حماية: الإرسال فقط للرقم المعتمد
    if clean_number != ALLOWED_NUMBER:
        print(f"Blocked: Attempt to send to {clean_number}")
        return

    try:
        message = WhatsappText(
            from_=VONAGE_SANDBOX_NUMBER,
            to=clean_number,
            text=message_text
        )
        response = vonage_client.messages.send(message)
        print(f"Success! Message UUID: {response.message_uuid}")
    except Exception as e:
        print(f"Vonage API Error: {e}")

# --- المسارات (Routes) ---

@app.post("/webhook")
async def whatsapp_webhook(req: Request):
    """استقبال الرسائل من واتساب"""
    try:
        data = await req.json()
        user_number = data.get("from", "").replace("+", "").strip()
        user_text = data.get("message", {}).get("content", {}).get("text")
        
        # الرد فقط إذا كان المرسل هو الرقم المعتمد
        if user_number == ALLOWED_NUMBER and user_text:
            reply = get_gemini_response(user_text)
            send_whatsapp(user_number, reply)
            
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "error"}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/send_message")
async def web_send(message: str = Form(...)):
    # الرقم مثبت مسبقاً في الدالة
    send_whatsapp(ALLOWED_NUMBER, message)
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    # استخدام المنفذ المخصص من Render
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
