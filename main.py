import os
import time
import requests
from threading import Thread
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "Bot aktif ve calisiyor!"

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

BOT_TOKEN = "8951343304:AAEEhyKFAPlFhJg9pp6AUsoM1EUnvKZoNNM"
AGNES_API_KEY = "sk-mzWSliOu65udCf0Wgwr06GK3Koa9cLHTPJnEASpANeEUP79U"

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

user_states = {}
user_sessions = {}

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print("Mesaj gönderme hatası:", e)

def send_video_to_user(chat_id, video_url, video_id, prompt_text=""):
    text = f"🎬 Yeni Video Hazır!\n\n📝 Prompt: {prompt_text}\n\n🆔 Video ID: {video_id}\n\n⬇️ İzle / İndir:\n{video_url}"
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text
        }, timeout=10)
    except Exception as e:
        print("Kullanıcı mesajı hatası:", e)

def generate_video(session, prompt_text):
    images_base64 = []
    for photo_url in session['photos']:
        try:
            img_data = requests.get(photo_url, timeout=15).content
            import base64
            b64 = "data:image/jpeg;base64," + base64.b64encode(img_data).decode("utf-8")
            images_base64.append(b64)
        except Exception as e:
            return None, f"Fotoğraf indirme hatası: {e}"

    if not images_base64:
        return None, "Hiçbir fotoğraf indirilemedi."

    payload = {
        "model": "agnes-video-2.5-flash",
        "prompt": prompt_text,
        "mode": "reference",
        "seconds": str(session.get('seconds', '8')),
        "size": "720P",
        "aspect_ratio": session.get('aspect', '9:16'),
        "images": images_base64,
        "n": 1
    }

    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        res = requests.post("https://apihub.agnes-ai.com/v1/videos", json=payload, headers=headers, timeout=20)
        
        if res.status_code != 200 and res.status_code != 201:
            return None, f"HTTP Kod: {res.status_code} - Yanıt: {res.text}"
            
        data = res.json()
        video_id = data.get("video_id") or data.get("id")
        if not video_id:
            return None, f"ID dönmedi, yanıt: {res.text}"
            
        return video_id, None
    except Exception as e:
        return None, f"Bağlantı/İstek hatası: {str(e)}"

def poll_agnes(video_id):
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Accept": "application/json"
    }
    
    for _ in range(60):
        time.sleep(5)
        try:
            res = requests.get(f"https://apihub.agnes-ai.com/agnesapi?video_id={video_id}&model_name=agnes-video-2.5-flash", headers=headers, timeout=15)
            data = res.json()
            video_url = data.get("video_url") or data.get("url") or data.get("video")
            if video_url:
                return video_url
        except:
            continue
    return None

def process_queue(chat_id, session):
    prompts = session['prompts']
    total = len(prompts)
    
    for index, prompt_text in enumerate(prompts, 1):
        send_message(chat_id, f"⏳ *[{index}/{total}]* Video üretimi başlatıldı...\nPrompt: _{prompt_text[:100]}..._")
        
        video_id, error_detail = generate_video(session, prompt_text)
        if video_id:
            send_message(chat_id, f"🎬 Video kuyrukta (ID: `{video_id}`). İşleniyor...")
            video_url = poll_agnes(video_id)
            
            if video_url:
                send_message(chat_id, f"✅ *[{index}/{total}]* Video hazır!")
                send_video_to_user(chat_id, video_url, video_id, prompt_text)
            else:
                send_message(chat_id, f"❌ *[{index}/{total}]* Video zaman aşımına uğradı.")
        else:
            send_message(chat_id, f"❌ *[{index}/{total}]* Agnes AI reddetti!\n*Sebep:* `{error_detail}`")
            
        if index < total:
            send_message(chat_id, "⏱️ Bir sonraki prompt için 1 dakika bekleniyor...")
            time.sleep(60)
            
    send_message(chat_id, "🎉 *Tüm işlem tamamlandı!* Yeni video için /start yazabilirsin.")

def check_updates():
    offset = 0
    print("Bot dinlemeye basladi...")
    while True:
        try:
            res = requests.get(f"{BASE_URL}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=40)
            data = res.json()
            
            if data.get("ok"):
                for result in data.get("result", []):
                    offset = result["update_id"] + 1
                    
                    if "callback_query" in result:
                        cq = result["callback_query"]
                        chat_id = cq["message"]["chat"]["id"]
                        data_val = cq["data"]
                        
                        if chat_id not in user_sessions:
                            user_sessions[chat_id] = {"photos": [], "prompts": [], "seconds": "8", "aspect": "9:16"}

                        if data_val == "photos_done":
                            if len(user_sessions[chat_id]["photos"]) > 0:
                                user_states[chat_id] = "WAITING_PROMPTS"
                                send_message(chat_id, "✍️ *2. Adım:* Üretilmesini istediğin detaylı promptu yaz:")
                            else:
                                send_message(chat_id, "⚠️ Lütfen önce en az 1 adet fotoğraf gönder.")
                        
                        elif data_val.startswith("sec_"):
                            sec = data_val.replace("sec_", "")
                            user_sessions[chat_id]["seconds"] = sec
                            user_states[chat_id] = "WAITING_ASPECT"
                            keyboard = {
                                "inline_keyboard": [
                                    [{"text": "📱 9:16 Dikey", "callback_data": "asp_9:16"}, {"text": "💻 16:9 Yatay", "callback_data": "asp_16:9"}],
                                    [{"text": "⏹️ 1:1 Kare", "callback_data": "asp_1:1"}]
                                ]
                            }
                            send_message(chat_id, f"✅ Süre: *{sec} saniye*\n\n📐 *3. Adım:* En / Boy oranını seç:", reply_markup=keyboard)

                        elif data_val.startswith("asp_"):
                            asp = data_val.replace("asp_", "")
                            user_sessions[chat_id]["aspect"] = asp
                            user_states[chat_id] = "PROCESSING"
                            send_message(chat_id, "🚀 *Tüm ayarlar kaydedildi!* Video üretilmeye başlanıyor...")
                            
                            session = user_sessions[chat_id]
                            t_q = Thread(target=process_queue, args=(chat_id, session))
                            t_q.start()
                            
                            user_states.pop(chat_id, None)
                            user_sessions.pop(chat_id, None)
                        continue

                    message = result.get("message", {})
                    if not message:
                        continue
                        
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "").strip()
                    
                    if text.startswith("/start"):
                        user_states[chat_id] = "WAITING_PHOTO"
                        user_sessions[chat_id] = {"photos": [], "prompts": [], "seconds": "8", "aspect": "9:16"}
                        
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "✅ Fotoğraflar Tamam, Devam Et ➡️", "callback_data": "photos_done"}]
                            ]
                        }
                        send_message(chat_id, "🎬 *Benzero AI Video Botuna Hoş Geldin!*\n\n📸 *1. Adım:* Referans fotoğraflarını **toplu olarak** gönder.\n\nTüm fotoğraflar yüklenince yukarıdaki **Fotoğraflar Tamam** butonuna tıkla:", reply_markup=keyboard)
                        continue
                        
                    current_state = user_states.get(chat_id, "NONE")
                    
                    if current_state == "NONE":
                        send_message(chat_id, "⚠️ Oturumunuz zaman aşımına uğradı veya bot yeniden başladı. Lütfen yeniden başlamak için **/start** yazın.")
                        continue

                    if current_state == "WAITING_PHOTO":
                        file_id = None
                        if "photo" in message:
                            file_id = message["photo"][-1]["file_id"]
                        elif "document" in message:
                            file_id = message["document"]["file_id"]

                        if file_id:
                            if chat_id not in user_sessions:
                                user_sessions[chat_id] = {"photos": [], "prompts": [], "seconds": "8", "aspect": "9:16"}
                            
                            file_res = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
                            file_path = file_res["result"]["file_path"]
                            photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                            
                            if photo_url not in user_sessions[chat_id]["photos"]:
                                user_sessions[chat_id]["photos"].append(photo_url)

                    elif current_state == "WAITING_PROMPTS":
                        if text:
                            if chat_id not in user_sessions:
                                user_sessions[chat_id] = {"photos": [], "prompts": [], "seconds": "8", "aspect": "9:16"}
                            user_sessions[chat_id]["prompts"] = [text]
                            user_states[chat_id] = "WAITING_SECONDS"
                            keyboard = {
                                "inline_keyboard": [
                                    [{"text": "4 sn", "callback_data": "sec_4"}, {"text": "5 sn", "callback_data": "sec_5"}, {"text": "8 sn", "callback_data": "sec_8"}],
                                    [{"text": "10 sn", "callback_data": "sec_10"}, {"text": "12 sn", "callback_data": "sec_12"}, {"text": "18 sn", "callback_data": "sec_18"}]
                                ]
                            }
                            send_message(chat_id, f"✅ *Prompt başarıyla kaydedildi.*\n\n⏱️ *3. Adım:* Video süresini seç:", reply_markup=keyboard)
                        else:
                            send_message(chat_id, "⚠️ Lütfen geçerli bir prompt yaz.")

        except Exception as e:
            print("Hata:", e)
            time.sleep(5)

if __name__ == "__main__":
    t = Thread(target=check_updates)
    t.start()
    run_web()
