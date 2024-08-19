from flask import Flask, send_file, render_template, request, jsonify
import os
import csv
from datetime import datetime
import json

app = Flask(__name__)

@app.route('/')
def index():
    with open('readings.json', 'r') as f:
        readings = json.load(f)
    return render_template('index.html', readings=readings)

@app.route('/week/<week>')
def week_view(week):
    pdf_file = f'{week}.pdf'
    return render_template('pdf_viewer.html', pdf=pdf_file)

@app.route('/get_pdf/<filename>')
def get_pdf(filename):
    file_path = os.path.join('pdfs', filename)
    if os.path.exists(file_path):
        return send_file(file_path, mimetype='application/pdf')
    else:
        return "PDF file not found", 404

@app.route('/annotate/<week>', methods=['POST'])
def annotate(week):
    annotation_data = request.json
    file_path = f'annotations/{week}.csv'
    os.makedirs('annotations', exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Add timestamp
    
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
            timestamp,  # Include timestamp
            annotation_data.get('parent_id', ''),  # Include parent ID for replies
            'active'  # Mark as active initially
        ])
    return jsonify({'status': 'success'})

@app.route('/delete_annotation/<week>', methods=['POST'])
def delete_annotation(week):
    annotation_data = request.json
    file_path = f'annotations/{week}.csv'
    annotations = []

    # Load all annotations and mark the matching one as deleted
    if os.path.exists(file_path):
        with open(file_path, mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                if (
                    int(row[0]) == annotation_data['page'] and
                    row[1] == annotation_data['type'] and
                    abs(float(row[2]) - float(annotation_data['left'])) < 0.01 and
                    abs(float(row[3]) - float(annotation_data['top'])) < 0.01 and
                    float(row[4]) == float(annotation_data['width']) and
                    float(row[5]) == float(annotation_data['height']) and
                    row[7] == annotation_data['author']  # Match the author name
                ):
                    row[-1] = 'deleted'  # Mark as deleted
                annotations.append(row)  # Ensure the row is added back to the list even if deleted

    # Write back the updated annotations
    with open(file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(annotations)

    return jsonify({'status': 'success'})


@app.route('/load_annotations/<week>/<int:page>')
def load_annotations(week, page):
    file_path = f'annotations/{week}.csv'
    annotations = []
    
    if os.path.exists(file_path):
        with open(file_path, mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) >= 11 and int(row[0]) == page and row[10] == 'active':  # Ensure the row is active
                    annotations.append({
                        'type': row[1],
                        'left': row[2],
                        'top': row[3],
                        'width': row[4],
                        'height': row[5],
                        'comment': row[6],
                        'author': row[7],
                        'timestamp': row[8],  # Include the timestamp
                        'parent_id': row[9]  # Include parent ID if available
                    })
    return jsonify({'annotations': annotations})

if __name__ == '__main__':
    app.run(debug=True)
