from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'message': 'Server is running'
    })

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': 'Hello! The server is reachable'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)