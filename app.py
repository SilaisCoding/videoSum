from flask import Flask, render_template, request, send_file
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.discovery import build
from dotenv import load_dotenv
import re
import ollama
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# Load environment variables
dotenv_path = "C:\\Users\\burak\\OneDrive\\Desktop\\videoSum\\myenv\\.env"
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

def clean_text(text):
    """
    Removes unsupported characters and ensures text is compatible with ReportLab.
    Also removes '**' markers around headings.
    """
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    return text

def create_pdf(title, channel, summary, ai_analysis, lang, output_path):
    """Creates a PDF file with the analysis results."""
    # Create a PDF document
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()

    heading_style = ParagraphStyle(
        name='HeadingStyle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        spaceAfter=20  
    )
    subheading_style = ParagraphStyle(
        name='SubheadingStyle',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
        spaceAfter=15  
    )

    story = []

    # Title and Channel
    title_style = styles["Title"]
    story.append(Paragraph(clean_text(title), title_style))
    channel_style = styles["Heading2"]
    story.append(Paragraph(f"Channel: {clean_text(channel)}", channel_style))
    story.append(Spacer(1, 20))  

    # Summary Section
    story.append(Paragraph("Summary", subheading_style))
    normal_style = styles["Normal"]
    
    # Split summary into lines and add extra spacing between numbered items
    previous_line_was_numbered = False
    for line in clean_text(summary).split('\n'):
        if re.match(r'^\d+\.', line):
            if previous_line_was_numbered:
                story.append(Spacer(1, 10))
            else:
                story.append(Spacer(1, 10))
            story.append(Paragraph(line, normal_style))
            previous_line_was_numbered = True
        else:
            if previous_line_was_numbered:
                story.append(Spacer(1, 10))
            story.append(Paragraph(line, normal_style))
            previous_line_was_numbered = False
    
    story.append(Spacer(1, 20))

    # AI Analysis Section
    story.append(Paragraph("AI Analysis", subheading_style))
    previous_line_was_numbered = False
    for line in clean_text(ai_analysis).split('\n'):
        if re.match(r'^\d+\.', line):
            if previous_line_was_numbered:
                story.append(Spacer(1, 10))
            else:
                story.append(Spacer(1, 10))
            story.append(Paragraph(line, normal_style))
            previous_line_was_numbered = True
        else:
            if previous_line_was_numbered:
                story.append(Spacer(1, 10))
            story.append(Paragraph(line, normal_style))
            previous_line_was_numbered = False

    # Build the PDF
    doc.build(story)

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

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    data = request.form
    title = data['title']
    channel = data['channel']
    summary = data['summary']
    ai_analysis = data['ai_analysis']
    lang = data['lang']

    # Create PDF
    pdf_path = "output.pdf"
    create_pdf(title, channel, summary, ai_analysis, lang, pdf_path)

    # Send PDF to user
    return send_file(pdf_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)