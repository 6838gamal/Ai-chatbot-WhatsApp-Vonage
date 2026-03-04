import os
import requests
import json
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# استيراد مكتبة Vonage الجديدة
from vonage import Vonage, Auth
from vonage_messages.models import WhatsappText

load_dotenv()

# --- الإعدادات ---
VONAGE_API_KEY = os.getenv("VONAGE_API_KEY")
VONAGE_API_SECRET = os.getenv("VONAGE_API_SECRET")
VONAGE_SANDBOX_NUMBER = os.getenv("VONAGE_SANDBOX_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# إعداد عميل Vonage الرسمي
auth = Auth(api_key=VONAGE_API_KEY, api_secret=VONAGE_API_SECRET)
vonage_client = Vonage(auth=auth)

# رابط Gemini 2.5 Flash
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

app = FastAPI(title="WhatsApp Gemini 2.5 Bot")
templates = Jinja2Templates(directory="templates")

# --- دالة الذكاء الاصطناعي (Gemini 2.5) ---
def get_gemini_2_5_response(user_input: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": user_input}]}],
        "system_instruction": {"parts": [{"text": "أنت مساعد ذكي ولطيف تتواصل عبر واتساب."}]}
    }
    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=15)
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "عذرًا، حدث خطأ في الاتصال بالذكاء الاصطناعي."

# --- دالة إرسال الواتساب باستخدام المكتبة الرسمية ---
def send_whatsapp(to_number: str, message_text: str):
    try:
        # إنشاء كائن الرسالة الخاص بـ Whatsapp
        message = WhatsappText(
            from_=VONAGE_SANDBOX_NUMBER,
            to=to_number,
            text=message_text
        )
        
        # إرسال الرسالة عبر عميل Vonage (Messages API)
        response = vonage_client.messages.send(message)
        print(f"Message Sent! ID: {response.message_uuid}")
    except Exception as e:
        print(f"Vonage Library Error: {e}")

# --- المسارات (Endpoints) ---

@app.post("/webhook")
async def whatsapp_webhook(req: Request):
    try:
        data = await req.json()
        # استخراج البيانات حسب هيكل Vonage المعتاد
        user_number = data.get("from")
        user_text = data.get("message", {}).get("content", {}).get("text")
        
        if user_number and user_text:
            reply = get_gemini_2_5_response(user_text)
            send_whatsapp(user_number, reply)
            
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error"}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/send_message")
async def web_send(number: str = Form(...), message: str = Form(...)):
    send_whatsapp(number, message)
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
