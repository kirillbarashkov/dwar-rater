import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from app import app

if __name__ == '__main__':
    port = int(os.environ.get('APP_HTTP_PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)