import json
import os
from flask import Flask
from app.routes.main_routes import _load_manual_html

app = Flask(__name__)
app.root_path = os.path.abspath('app')
with app.app_context():
    html = _load_manual_html()
    with open('/tmp/rendered.html', 'w') as f:
        f.write(html)
