import os
from app import app, db
with app.app_context():
    print(os.path.abspath(db.engine.url.database))
