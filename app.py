from flask import Flask, render_template, request
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.discovery import build
from dotenv import load_dotenv
import re
import ollama
import os

dotenv_path = "C:\\Users\\burak\\OneDrive\\Desktop\\videoSum\\myenv\\.env"
load_dotenv(dotenv_path=dotenv_path)

API_KEY = os.getenv("API_KEY")
app = Flask(__name__)

def get_video_id(url):
    """YouTube pulls video ID from URL"""
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)
    return match.group(1) if match else None

def get_video_details(video_id):
    """Fetches video title, channel name and description with YouTube API"""
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    request = youtube.videos().list(part="snippet", id=video_id)
    response = request.execute()
    return response['items'][0]['snippet']

def get_transcript(video_id):
    """Receives the subtitles of the video and detects the language"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)  

        try:
            transcript = transcript_list.find_transcript(['tr'])  
            return " ".join([t['text'] for t in transcript.fetch()]), "tr"
        except:
            pass  

        try:
            transcript = transcript_list.find_transcript(['en', 'auto'])
            return " ".join([t['text'] for t in transcript.fetch()]), transcript.language_code
        except:
            pass  

        return None, None  

    except (TranscriptsDisabled, NoTranscriptFound):
        return None, None  

def summarize_with_ollama(text, lang):
    """Ollama kullanarak videonun özetini oluşturur"""
    try:
        prompt = f"""
        Aşağıdaki videonun {lang.upper()} dilindeki tam transkriptini detaylıca özetle:
        - En önemli noktaları kısa ve net olarak sun.
        - Konunun genel anlamını bozmadan, gereksiz detayları çıkar.
        - Temel argümanları ve sonuçları vurgula.
        - Videonun ana mesajını özetle ve belirtilen hedef kitlenin ilgisini çekecek şekilde sun.
        - Videonun içeriğiyle ilgili olası sorular veya tartışma konuları ekle.
        
        Transcript: {text}
        """
        
        response = ollama.chat(
            model='llama3',
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content']

    except Exception as e:
        return f"Özetleme Hatası: {str(e)}"

def analyze_with_ollama(summary, lang):
    """Ollama kullanarak videoyu verilen dilde analiz eder"""
    try:
        prompt = f"""
        Aşağıdaki video özeti {lang.upper()} dilinde. Lütfen detaylı analiz et:
        1. Anahtar fikirler ve ana noktalar.
        2. Olası önyargılar veya eksik bakış açıları.
        3. Daha fazla araştırılabilecek ilgili konular.
        4. Sunulan argümanların eleştirisi.
        5. Ek bilgi veya bağlamın gerekli olduğu yerler.
        6. Videonun kaynaklarının ve kanıtlarının güvenilirliği.
        7. Videonun hedef kitlesi ve hedeflerine uygun olup olmadığı.
        
        Özet: {summary}
        """
        
        response = ollama.chat(
            model='llama3',
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content']

    except Exception as e:
        return f"Analysis Error: {str(e)}"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        video_id = get_video_id(url)

        try:
            transcript, lang = get_transcript(video_id)
            if transcript is None:
                return render_template('index.html', error="No subtitles found for this video.")

            summary = summarize_with_ollama(transcript, lang)

            ai_analysis = analyze_with_ollama(summary, lang)

            details = get_video_details(video_id)

            return render_template('result.html', 
                                   title=details['title'],
                                   channel=details['channelTitle'],
                                   description=details['description'],
                                   summary=summary,
                                   transcript=transcript,
                                   ai_analysis=ai_analysis,
                                   lang=lang)

        except Exception as e:
            return render_template('index.html', error=f"Hata: {str(e)}")

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
