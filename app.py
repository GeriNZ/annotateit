from flask import Flask, send_file, render_template, request, jsonify, url_for
import os
import csv
from datetime import datetime
import json
from flask_cors import CORS
from dotenv import load_dotenv
import requests
from flask_mail import Mail, Message

load_dotenv(override=True)

app = Flask(__name__)
CORS(app)

app.config['DEBUG'] = os.environ.get('FLASK_DEBUG')



# Configure the mail server (e.g., using Gmail as an SMTP server)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')  # Add your email to the .env file
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')  # Add your email password to the .env file
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')  # The default sender email

mail = Mail(app)



def send_to_google_sheets(data):
    google_script_url = "https://script.google.com/macros/s/AKfycbwBqh4G_Tkven7f0HjBvZTjTmApsqD4-V8_4kCsMO41t5pCxj4_J8O6M6HDOiRWVTCvIA/exec"
    print(f"Using Google Script URL: {google_script_url}")  # Ensure you have the Google Script URL in your .env
    try:
        response = requests.post(google_script_url, json=data)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending to Google Sheets: {e}")
        return {"status": "failure", "error": str(e)}

def load_readings(course):
    with open(f'readings_{course}.json', 'r') as f:
        return json.load(f)
    
@app.route('/user_guide')
def user_guide():
    return render_template('user_guide.html')



@app.route('/')
def course_selection():
    return render_template('course_selection.html')

@app.route('/course/<course>')
def index(course):
    readings = load_readings(course)
    return render_template('index.html', readings=readings, course=course)

@app.route('/course/<course>/week/<week>')
def week_view(course, week):
    pdf_file = f'{week}.pdf'
    return render_template('pdf_viewer.html', pdf=pdf_file, course=course)

@app.route('/get_pdf/<course>/<filename>')
def get_pdf(course, filename):
    file_path = os.path.join('pdfs', course, filename)
    if os.path.exists(file_path):
        return send_file(file_path, mimetype='application/pdf')
    else:
        return "PDF file not found", 404

@app.route('/annotate/<course>/<week>', methods=['POST'])
def annotate(course, week):
    annotation_data = request.json
    file_path = os.path.join('annotations', course, f'{week}.csv')
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Save annotation to CSV
    with open(file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            annotation_data['page'],
            annotation_data['type'],
            annotation_data['left'],
            annotation_data['top'],
            annotation_data['width'],
            annotation_data['height'],
            annotation_data.get('comment', ''),
            annotation_data.get('author', ''),
            timestamp,
            annotation_data.get('parent_id', ''),
            'active'
        ])

    # Prepare data for Google Sheets with full annotation details
    google_data = {
        "course": course,
        "week": week,
        "studentName": annotation_data.get('author', ''),
        "page": annotation_data['page'],
        "left": annotation_data['left'],       # Adding left coordinate
        "top": annotation_data['top'],         # Adding top coordinate
        "width": annotation_data['width'],     # Adding width of the annotation
        "height": annotation_data['height'],   # Adding height of the annotation
        "comment": annotation_data.get('comment', ''),
        "timestamp": timestamp,
        "status": "active" , 
        "parent_id": annotation_data.get('parent_id', '')
        
    }
    
    # Send data to Google Sheets
    google_response = send_to_google_sheets(google_data)

    # Define a mapping of course identifiers to their full names
    course_full_names = {
        'mass_communication': 'COMS 2202 Principles of Mass Communication',
        'communication_studies': 'COMS 2001 Communication Studies',
        'communication_technology': 'COMS 2501 Communication and Technology'
    }

    # Get the full course name based on the course identifier
    course_name = course_full_names.get(course, course)  # Default to course if not found in mapping

    # Send email if email address is provided
    if annotation_data.get('email'):
        week_number = week  # Get the week number from the URL parameter
        
        msg = Message(f'Your Comment on the Reading from Week {week_number} - {course_name}',
                    sender=os.getenv('MAIL_DEFAULT_SENDER'),
                    recipients=[annotation_data['email']])
        
        msg.body = f"""
        Hello {annotation_data['author']},
        
        You made the following comment at {timestamp}:
        
        "{annotation_data['comment']}"
        
        Course: {course_name}
        Week: {week_number}
        Page: {annotation_data['page']}
        
        
        Thank you for your participation!
        With any questions, please don't reply to this email, but email me at geraldine.bengsch@sta.uwi.edu instead. Thanks!
        """
        
        try:
            mail.send(msg)
            print("Email sent successfully")
        except Exception as e:
            print(f"Error sending email: {e}")


    return jsonify({'status': 'success', 'google_response': google_response})


@app.route('/delete_annotation/<course>/<week>', methods=['POST'])
def delete_annotation(course, week):
    annotation_data = request.json

    # Send request to Google Sheets to update status to "deleted"
    google_data = {
        "course": course,
        "week": week,
        "studentName": annotation_data.get('author', ''),
        "page": annotation_data['page'],
        "left": annotation_data['left'],
        "top": annotation_data['top'],
        "width": annotation_data['width'],
        "height": annotation_data['height'],
        "status": "deleted",  # Mark the status as deleted
    }

    # Send the updated status to Google Sheets
    google_response = send_to_google_sheets(google_data)

    return jsonify({'status': 'success', 'google_response': google_response})



import requests

@app.route('/load_annotations/<course>/<week>/<int:page>')
def load_annotations(course, week, page):
    google_script_url = "https://script.google.com/macros/s/AKfycbwBqh4G_Tkven7f0HjBvZTjTmApsqD4-V8_4kCsMO41t5pCxj4_J8O6M6HDOiRWVTCvIA/exec"
    
    try:
        # Log the request parameters
        print(f"Request to Google Script: Course: {course}, Week: {week}, Page: {page}")
        
        # Fetch annotations from Google Sheets via Google Apps Script
        params = {
            "course": course,
            "week": week,
            "page": page
        }
        
        response = requests.get(google_script_url, params=params)
        response.raise_for_status()  # Raise an exception if the request fails
        
        # Log the response from Google Apps Script
        print(f"Google Apps Script Response: {response.text}")
        
        annotations = response.json().get('annotations', [])
        print(f"Loaded annotations from Google Sheets: {annotations}")
        
        return jsonify({'annotations': annotations})
    
    except requests.exceptions.RequestException as e:
        # Log the error and return a 500 error response
        print(f"Error fetching annotations from Google Sheets: {e}")
        return jsonify({'error': 'Unable to fetch annotations'}), 500



if __name__ == '__main__':
    # Use the PORT environment variable provided by Cloud Run
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
