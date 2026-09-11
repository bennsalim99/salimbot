import os
import time
import requests
from threading import Thread
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "Bot aktif ve çalışıyor!"

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

BOT_TOKEN = "8951343304:AAEEhyKFAPlFhJg9pp6AUsoM1EUnvKZoNNM"
AGNES_API_KEY = "sk-mzWSliOu65udCf0Wgwr06GK3Koa9cLHTPJnEASpANeEUP79U"
CHAT_ID = "-1004316545825"

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
    requests.post(f"{BASE_URL}/sendMessage", json=payload)

def send_video_to_channel(video_url, video_id, prompt_text=""):
    text = f"🎬 *Sıralı Benzero AI Videosu Hazır!*\n\n📝 *Prompt:* {prompt_text}\n\n🆔 *Video ID:* `{video_id}`\n\n⬇️ *İzle / İndir:*\n{video_url}"
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })

def generate_video(session, prompt_text):
    images_base64 = []
    for photo_url in session['photos']:
        img_data = requests.get(photo_url).content
        import base64
        b64 = "data:image/jpeg;base64," + base64.b64encode(img_data).decode("utf-8")
        images_base64.append(b64)

    payload = {
        "model": "agnes-video-2.5-flash",
        "prompt": prompt_text,
        "negative_prompt": session['neg_prompt'],
        "mode": "reference",
        "seconds": session['seconds'],
        "size": "720P",
        "aspect_ratio": session['aspect'],
        "images": images_base64,
        "n": 1
    }

    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    res = requests.post("https://apihub.agnes-ai.com/v1/videos", json=payload, headers=headers)
    try:
        data = res.json()
        return data.get("video_id") or data.get("id")
    except:
        return None

def poll_agnes(video_id):
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Accept": "application/json"
    }
    
    for _ in range(60):
        time.sleep(5)
        res = requests.get(f"https://apihub.agnes-ai.com/agnesapi?video_id={video_id}&model_name=agnes-video-2.5-flash", headers=headers)
        try:
            data = res.json()
        except:
            continue
        
        video_url = data.get("video_url") or data.get("url") or data.get("video")
        if video_url:
            return video_url
    return None

def process_queue(chat_id, session):
    prompts = session['prompts']
    total = len(prompts)
    
    for index, prompt_text in enumerate(prompts, 1):
        send_message(chat_id, f"⏳ *[{index}/{total}]* Sıradaki video üretiliyor...\nPrompt: _{prompt_text}_")
        
        video_id = generate_video(session, prompt_text)
        if video_id:
            send_message(chat_id, f"🎬 Video kuyruğa alındı (ID: `{video_id}`). İşleniyor...")
            video_url = poll_agnes(video_id)
            
            if video_url:
                send_message(chat_id, f"✅ *[{index}/{total}]* Video tamamlandı ve kanala gönderildi!")
                send_video_to_channel(video_url, video_id, prompt_text)
            else:
                send_message(chat_id, f"❌ *[{index}/{total}]* Video zaman aşımına uğradı.")
        else:
            send_message(chat_id, f"❌ *[{index}/{total}]* Agnes AI isteği reddetti.")
            
        # Eğer son videoda değilsek, sonraki videoya geçmeden önce 1 dakika bekle
        if index < total:
            send_message(chat_id, f"⏱️ Sıradaki video için 1 dakika bekleniyor...")
            time.sleep(60)
            
    send_message(chat_id, "🎉 *Tüm sıradaki videolar başarıyla tamamlandı!* Yeni bir işleme başlamak için /start yazabilirsin.")

def check_updates():
    offset = 0
    print("Sıralı bot aktif ve çalışıyor...")
    while True:
        try:
            res = requests.get(f"{BASE_URL}/getUpdates", params={"offset": offset, "timeout": 30})
            data = res.json()
            
            if data.get("ok"):
                for result in data.get("result", []):
                    offset = result["update_id"] + 1
                    
                    if "callback_query" in result:
                        cq = result["callback_query"]
                        chat_id = cq["message"]["chat"]["id"]
                        data_val = cq["data"]
                        
                        if chat_id in user_states:
                            state = user_states[chat_id]
                            
                            if state == "WAITING_SECONDS":
                                user_sessions[chat_id]['seconds'] = data_val
                                user_states[chat_id] = "WAITING_ASPECT"
                                
                                keyboard = {
                                    "inline_keyboard": [
                                        [{"text": "📱 9:16 Dikey", "callback_data": "9:16"}, {"text": "💻 16:9 Yatay", "callback_data": "16:9"}],
                                        [{"text": "⏹️ 1:1 Kare", "callback_data": "1:1"}]
                                    ]
                                }
                                send_message(chat_id, f"✅ Süre seçildi: *{data_val} saniye*.\n\nSon olarak video **En / Boy (Aspect Ratio)** oranını seçin:", reply_markup=keyboard)
                                
                            elif state == "WAITING_ASPECT":
                                user_sessions[chat_id]['aspect'] = data_val
                                user_states[chat_id] = "PROCESSING"
                                
                                send_message(chat_id, "🚀 Tüm ayarlar alındı! Sıralı üretim başlatılıyor...")
                                
                                session = user_sessions[chat_id]
                                
                                # Arka planda sırayla üretimi başlat
                                t_queue = Thread(target=process_queue, args=(chat_id, session))
                                t_queue.start()
                                
                                user_states.pop(chat_id, None)
                                user_sessions.pop(chat_id, None)
                        continue

                    message = result.get("message", {})
                    if not message:
                        continue
                        
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text") or message.get("caption") or ""
                    
                    if text == "/start":
                        user_states[chat_id] = "WAITING_PHOTO"
                        user_sessions[chat_id] = {"photos": [], "prompts": [], "neg_prompt": "", "seconds": "8", "aspect": "9:16"}
                        send_message(chat_id, "🎬 *Benzero AI Sıralı Video Botuna Hoş Geldiniz!*\n\n📸 Önce referans fotoğraflarını gönder (En fazla 5 tane).\n\nFotoğraflar bittiğinde sohbete herhangi bir şey (örneğin `devam` veya `bitti`) yaz.")
                        continue
                        
                    current_state = user_states.get(chat_id, "NONE")
                    
                    if current_state == "WAITING_PHOTO":
                        if "photo" in message:
                            photo_id = message["photo"][-1]["file_id"]
                            file_res = requests.get(f"{BASE_URL}/getFile?file_id={photo_id}").json()
                            file_path = file_res["result"]["file_path"]
                            photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                            
                            user_sessions[chat_id]["photos"].append(photo_url)
                            count = len(user_sessions[chat_id]["photos"])
                            send_message(chat_id, f"✅ Fotoğraf eklendi ({count}/5). Başka eklemek istiyorsan gönder, istemiyorsan **devam** yaz.")
                        else:
                            if len(user_sessions[chat_id]["photos"]) > 0:
                                user_states[chat_id] = "WAITING_PROMPTS"
                                send_message(chat_id, "✍️ Şimdi sırayla üretilmesini istediğin **tüm promptları alt alta** yaz:\n*(Örnek:\n1. Adam koşuyor\n2. Kadın gülüyor)*")
                            else:
                                send_message(chat_id, "⚠️ Lütfen önce en az 1 fotoğraf gönder.")
                                
                    elif current_state == "WAITING_PROMPTS":
                        # Satırlarına göre promptları ayır
                        lines = [line.strip() for line in text.split("\n") if line.strip()]
                        user_sessions[chat_id]["prompts"] = lines
                        user_states[chat_id] = "WAITING_NEG_PROMPT"
                        send_message(chat_id, f"✅ Toplam *{len(lines)}* prompt alındı.\n\n🚫 Şimdi **Negative Prompt** yaz (İstemiyorsan nokta `.` koy):")
                        
                    elif current_state == "WAITING_NEG_PROMPT":
                        user_sessions[chat_id]["neg_prompt"] = text if text != "." else ""
                        user_states[chat_id] = "WAITING_SECONDS"
                        
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "4s", "callback_data": "4"}, {"text": "5s", "callback_data": "5"}, {"text": "8s", "callback_data": "8"}, {"text": "10s", "callback_data": "10"}],
                                [{"text": "12s", "callback_data": "12"}, {"text": "15s", "callback_data": "15"}, {"text": "18s", "callback_data": "18"}]
                            ]
                        }
                        send_message(chat_id, "⏱️ Lütfen video **suresini** seçin:", reply_markup=keyboard)
                        
        except Exception as e:
            print("Hata:", e)
            time.sleep(5)

if __name__ == "__main__":
    t = Thread(target=check_updates)
    t.start()
    run_web()
