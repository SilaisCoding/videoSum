from flask import Flask, render_template, request
from youtube_transcript_api import YouTubeTranscriptApi
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from googleapiclient.discovery import build
import re
import os

app = Flask(__name__)
API_KEY = "YOUR_API_KEY"  # Buraya kendi API anahtarınızı girin

def get_video_id(url):
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)
    return match.group(1) if match else None

def get_video_details(video_id):
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    request = youtube.videos().list(part="snippet", id=video_id)
    response = request.execute()
    return response['items'][0]['snippet']

def summarize_text(text, sentences_count=5):
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, sentences_count)
    return " ".join([str(sentence) for sentence in summary])

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        video_id = get_video_id(url)
        
        try:
            # Transkript al
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            text = " ".join([t['text'] for t in transcript])
            
            # Video detayları
            details = get_video_details(video_id)
            
            # Özetleme
            summary = summarize_text(text)
            
            return render_template('result.html', 
                                 title=details['title'],
                                 channel=details['channelTitle'],
                                 description=details['description'],
                                 summary=summary,
                                 transcript=text)
        
        except Exception as e:
            error = f"Hata oluştu: {str(e)}"
            return render_template('index.html', error=error)
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)