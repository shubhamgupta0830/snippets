from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import openai
import os
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Set your OpenAI API key
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Database model
class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    headline = db.Column(db.String(200), nullable=False)
    short_summary = db.Column(db.String(500), nullable=False)
    detailed_summary = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=False)

def get_article_content(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    article = ' '.join([p.text for p in soup.find_all('p')])
    return article

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/summarize', methods=['POST'])
def summarize():
    data = request.json
    url = data['url']
    num_paragraphs = data.get('num_paragraphs', 5)
    chars_per_paragraph = data.get('chars_per_paragraph', 150)
    
    article_text = get_article_content(url)
    
    # Generate detailed summary
    summary_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes articles."},
            {"role": "user", "content": f"Summarize the following article in {num_paragraphs} paragraphs. Each paragraph should be approximately {chars_per_paragraph} characters long and cover a core point of the article. Only talk about the topic that has maximum content. Don't include anything that isn't related to the core article. Ensure each paragraph is a complete thought and doesn't end mid-sentence:\n\n{article_text}"}
        ],
        max_tokens=num_paragraphs * chars_per_paragraph*2 // 4
    )
    
    detailed_summary = summary_response.choices[0].message['content'].strip().split('\n\n')
    
    # Generate a short summary (150 characters)
    short_summary_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes articles."},
            {"role": "user", "content": f"Provide a concise summary (150 characters) for the following article:\n\n{article_text}"}
        ],
        max_tokens=30  # Limit to around 150 characters
    )
    
    short_summary = short_summary_response.choices[0].message['content'].strip()
    
    # Generate headline
    headline_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates catchy headlines for articles."},
            {"role": "user", "content": f"Generate a catchy headline for the following article summary:\n\n{short_summary}"}
        ],
        max_tokens=50
    )
    
    headline = headline_response.choices[0].message['content'].strip()

    # For this example, we'll use a placeholder image URL
    image_url = "https://via.placeholder.com/512"

    # Save to database
    new_summary = Summary(
        url=url,
        headline=headline,
        short_summary=short_summary,
        detailed_summary='\n\n'.join(detailed_summary),
        image_url=image_url
    )
    db.session.add(new_summary)
    db.session.commit()

    return jsonify({
        "id": new_summary.id,
        "url": url,
        "summary": detailed_summary,
        "headline": headline,
        "short_summary": short_summary,
        "image_url": image_url
    })

@app.route('/api/summaries', methods=['GET'])
def get_summaries():
    summaries = Summary.query.order_by(Summary.id.desc()).all()
    return jsonify([{
        "id": s.id,
        "url": s.url,
        "summary": s.detailed_summary.split('\n\n'),
        "headline": s.headline,
        "short_summary": s.short_summary,
        "image_url": s.image_url
    } for s in summaries])

@app.route('/api/summary', methods=['POST'])
def create_summary():
    data = request.json
    new_summary = Summary(
        url=data['url'],
        headline=data['headline'],
        short_summary=data['short_summary'],
        detailed_summary='\n\n'.join(data['summary']),
        image_url=data['image_url']
    )
    db.session.add(new_summary)
    db.session.commit()
    return jsonify({
        "id": new_summary.id,
        "url": new_summary.url,
        "summary": new_summary.detailed_summary.split('\n\n'),
        "headline": new_summary.headline,
        "short_summary": new_summary.short_summary,
        "image_url": new_summary.image_url
    }), 201

@app.route('/api/summary/<int:summary_id>', methods=['DELETE'])
def delete_summary(summary_id):
    summary = Summary.query.get_or_404(summary_id)
    db.session.delete(summary)
    db.session.commit()
    return jsonify({"message": f"Summary with id {summary_id} has been deleted"}), 200

@app.route('/api/clear', methods=['POST'])
def clear_summaries():
    Summary.query.delete()
    db.session.commit()
    return jsonify({"message": "All summaries cleared"})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5002)