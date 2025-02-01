from flask import Flask, render_template, request
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.discovery import build
from dotenv import load_dotenv
import re
import ollama
import os

dotenv_path = "Write your .env file path here"
load_dotenv(dotenv_path=dotenv_path)
API_KEY = os.getenv("API_KEY")

app = Flask(__name__)

def get_video_id(url):
    """Extracts YouTube video ID from URL"""
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)
    return match.group(1) if match else None

def get_video_details(video_id):
    """Fetches video title, channel name, and description using the YouTube API"""
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    request = youtube.videos().list(part="snippet", id=video_id)
    response = request.execute()
    return response['items'][0]['snippet']

def get_transcript(video_id):
    """Retrieves the transcript of the video and detects the language"""
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
    """Uses Ollama to generate a detailed summary of the video"""
    try:
        prompt = f"""
        Summarize the following {lang.upper()} transcript in detail:
        - Highlight the most important points concisely.
        - Maintain the overall meaning without unnecessary details.
        - Emphasize key arguments and conclusions.
        - Provide a clear overview of the main message.
        - Include potential questions or discussion topics related to the content.
        - Ensure the summary is engaging and relevant to the target audience.
        
        Transcript: {text}
        """
        response = ollama.chat(
            model='llama3',
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content']
    except Exception as e:
        return f"Summary Error: {str(e)}"

def analyze_with_ollama(summary, lang):
    """Uses Ollama to perform an in-depth analysis of the video"""
    try:
        prompt = f"""
        Analyze the following {lang.upper()} video summary in detail:
        1. Key ideas and main points.
        2. Potential biases or missing perspectives.
        3. Related topics that could be explored further.
        4. Critique of the arguments presented.
        5. Areas where additional context or information is needed.
        6. Reliability of the sources and evidence used in the video.
        7. Suitability of the video for its target audience and objectives.
        8. Suggestions for improving the clarity and impact of the content.
        
        Summary: {summary}
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
        if not video_id:
            return render_template('index.html', error="Invalid YouTube URL.")
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
            return render_template('index.html', error=f"Error: {str(e)}")
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)