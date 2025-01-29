from flask import Flask, render_template, request
from youtube_transcript_api import YouTubeTranscriptApi
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from googleapiclient.discovery import build
from myenv import load_dotenv
import re
import ollama
import os

load_dotenv()

app = Flask(__name__)
API_KEY = os.getenv("API_KEY")

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

def analyze_with_llama(text):
    try:
        prompt = f"""
        Analyze the following video summary and provide:
        1. Key insights and main points
        2. Potential biases or missing perspectives
        3. Related topics for further research
        4. Critical analysis of arguments presented
        
        Summary: {text}
        """
        
        response = ollama.chat(
            model='llama3',
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content']
    
    except Exception as e:
        return f"AI Analysis Error: {str(e)}"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        video_id = get_video_id(url)
        
        try:
            # Get transcript
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            text = " ".join([t['text'] for t in transcript])
            
            # Summarize
            summary = summarize_text(text)
            
            # AI Analysis
            ai_analysis = analyze_with_llama(summary)
            
            # Get video details
            details = get_video_details(video_id)
            
            return render_template('result.html', 
                                title=details['title'],
                                channel=details['channelTitle'],
                                description=details['description'],
                                summary=summary,
                                transcript=text,
                                ai_analysis=ai_analysis)
        
        except Exception as e:
            error = f"Error: {str(e)}"
            return render_template('index.html', error=error)
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)