from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)

APP_SETTINGS = 'settings'
app.config.from_object(APP_SETTINGS)

db = SQLAlchemy(app)

import motdplayer
motdplayer.init(app, db)

import motdplayer_applications
motdplayer_applications.init(app, db)

db.create_all()
db.session.commit()

app.run(debug=True)
