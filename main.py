import os
import requests
import uvicorn
import json
from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# مكتبات Vonage
from vonage import Auth, Vonage
from vonage_messages.models import WhatsappText

load_dotenv()

# --- الإعدادات ---
ALLOWED_NUMBER = "967774440982"

app = FastAPI()
base_dir = os.path.dirname(os.path.realpath(__file__))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

# --- إعداد Vonage مع تصيد خطأ المفتاح ---
try:
    auth = Auth(
        application_id=os.getenv("VONAGE_APPLICATION_ID"),
        private_key=os.getenv("VONAGE_PRIVATE_KEY_PATH", "private.key"),
    )
    vonage_client = Vonage(auth)
    print("✅ تم إعداد عميل Vonage بنجاح")
except Exception as e:
    print(f"❌ فشل إعداد Vonage (تأكد من ملف private.key): {e}")

# --- وظائف المعالجة مع تصيد الأخطاء ---

def get_gemini_response(user_input: str) -> str:
    """الحصول على رد Gemini مع صيد أخطاء الشبكة أو المفتاح"""
    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": user_input}]}],
        "system_instruction": {"parts": [{"text": "أنت مساعد ذكي."}]}
    }
    
    try:
        print(f"🤖 جاري طلب الرد من Gemini للرسالة: {user_input[:20]}...")
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status() # سيولد خطأ إذا كانت النتيجة ليست 200
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except requests.exceptions.HTTPError as err:
        print(f"❌ خطأ HTTP من Gemini: {err.response.status_code} - {err.response.text}")
        return "عذراً، لدي مشكلة في الاتصال بمخي الذكي (API Error)."
    except Exception as e:
        print(f"❌ خطأ غير متوقع في Gemini: {e}")
        return "عذراً، حدث خطأ تقني غير متوقع."

def send_whatsapp(to_number: str, message_text: str):
    """إرسال واتساب مع صيد أخطاء الإرسال (Invalid Sender, Session, etc)"""
    clean_to = to_number.replace("+", "").replace(" ", "").strip()
    from_num = os.getenv("VONAGE_SANDBOX_NUMBER", "14157386102").replace("+", "").strip()
    
    print(f"📤 محاولة إرسال رسالة من {from_num} إلى {clean_to}")
    
    try:
        msg = WhatsappText(from_=from_num, to=clean_to, text=message_text)
        response = vonage_client.messages.send(msg)
        print(f"🚀 تم قبول الرسالة من Vonage! معرف الرسالة: {response.message_uuid}")
    except Exception as e:
        print("--- ❌ فشل إرسال رسالة الواتساب ---")
        print(f"السبب التقني: {str(e)}")
        # إذا كان الخطأ من Vonage سيعطي تفاصيل إضافية
        if "422" in str(e):
            print("💡 نصيحة: خطأ 422 يعني غالباً أن الرقم 'From' خطأ أو الجلسة (Session) انتهت.")
        print("-------------------------------")

# --- المسارات (Endpoints) ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/inbound")
async def webhook(request: Request):
    """استقبال الرسائل مع صيد أخطاء البيانات القادمة"""
    try:
        body = await request.json()
        print(f"📩 رسالة جديدة قادمة: {json.dumps(body, indent=2)}")
        
        sender = body.get("from", "").replace("+", "").strip()
        text = body.get("text") or body.get("message", {}).get("content", {}).get("text")
        
        if sender == ALLOWED_NUMBER and text:
            reply = get_gemini_response(text)
            send_whatsapp(sender, reply)
        else:
            print(f"⚠️ تجاهل رسالة من {sender} (ليست من الرقم المسموح أو نص فارغ)")
            
    except Exception as e:
        print(f"❌ خطأ في معالجة الـ Webhook: {e}")
        
    return Response(status_code=200)

@app.post("/send_message")
async def web_send(message: str = Form(...)):
    print(f"🌐 طلب إرسال من واجهة الويب...")
    send_whatsapp(ALLOWED_NUMBER, message)
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
