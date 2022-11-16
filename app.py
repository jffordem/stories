from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import json, os
from config import config

__doc__ = """
This is meant to run in pythonanywhere.com and use their built-in mysql database.

mysql> create database stories;

Set up the .env file properly.

C:> flask db_create
C:> flask db_load_stories
C:> flask run

If things get really sideways, can reset db and start over.
C:> flask db_reset
C:> flask db_load_stories
"""

db_conn = 'mysql+mysqlconnector://{user}:{passwd}@{host}/{database}'.format(
    user=config['MYSQL_USER'],
    passwd=config['MYSQL_PASS'],
    host=config['MYSQL_SERVER'],
    database=config['MYSQL_DATABASE'])

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_conn
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = config['SECRET_KEY']

db = SQLAlchemy(app)

class Stories(db.Model):
    __tablename__ = 'stories'

    story_id = db.Column(db.Integer, primary_key=True) # pylint: disable=maybe-no-member
    title = db.Column(db.String(length=64)) # pylint: disable=maybe-no-member
    description = db.Column(db.String(length=1024)) # pylint: disable=maybe-no-member

    # IRL you'd use something like flask-marshmallow to marshall SQLAlchemy/json.
    def toDict(self):
        return {
            'story_id': self.story_id,
            'title': self.title,
            'description': self.description
        }

class Pages(db.Model):
    __tablename__ = 'pages'

    page_id = db.Column(db.Integer, primary_key=True) # pylint: disable=maybe-no-member
    story_id = db.Column(db.Integer, db.ForeignKey('stories.story_id')) # pylint: disable=maybe-no-member
    text = db.Column(db.String(length=8192)) # pylint: disable=maybe-no-member
    outcome = db.Column(db.Integer) # pylint: disable=maybe-no-member
    story = db.relationship('Stories') # pylint: disable=maybe-no-member

    # IRL you'd use something like flask-marshmallow to marshall SQLAlchemy/json.
    def toDict(self):
        return {
            'page_id': self.page_id,
            'story_id': self.story_id,
            'text': self.text
        }

class Choices(db.Model):
    __tablename__ = 'choices'

    choice_id = db.Column(db.Integer, primary_key=True) # pylint: disable=maybe-no-member
    story_id = db.Column(db.Integer, db.ForeignKey('stories.story_id')) # pylint: disable=maybe-no-member
    page_id = db.Column(db.Integer, db.ForeignKey('pages.page_id')) # pylint: disable=maybe-no-member
    text = db.Column(db.String(length=256)) # pylint: disable=maybe-no-member
    to_page = db.Column(db.Integer) # pylint: disable=maybe-no-member
    story = db.relationship('Stories') # pylint: disable=maybe-no-member
    page = db.relationship('Pages') # pylint: disable=maybe-no-member

    # IRL you'd use something like flask-marshmallow to marshall SQLAlchemy/json.
    def toDict(self):
        return {
            'choice_id': self.choice_id,
            'story_id': self.story_id,
            'page_id': self.page_id,
            'text': self.text,
            'to_page': self.to_page
        }

def outcomeFromResult(result):
    if result == 'success': return 1
    if result == 'failure': return -1
    return 0

def resultFromOutcome(outcome):
    if outcome < 0: return 'failure'
    if outcome > 0: return 'success'
    return ''

def tryGetValue(d, k, default=''):
    if k in d:
        return d[k]
    return default

def getPage(story_id, page_id):
    if page_id == 0:
        return Pages.query.filter_by(story_id=story_id).first()
    else:
        return Pages.query.filter_by(story_id=story_id, page_id=page_id).first()

@app.route('/')
def show_projects():
    return render_template('index.html', stories=Stories.query.all())

@app.route('/story/<int:story_id>/<int:page_id>', methods=['GET'])
def read_story(story_id, page_id):
    story = Stories.query.filter_by(story_id=story_id).first()
    page = getPage(story_id, page_id)
    result = resultFromOutcome(page.outcome)
    choices = Choices.query.filter_by(story_id=story_id, page_id=page.page_id).all()
    return render_template("story.html", 
        story=story,
        page=page,
        result=result,
        choices=choices)

def loadStory(jsonFile):
    with open(jsonFile) as f:
        story = json.load(f)
        story_row = Stories(title=story['name'], description=story['description'])
        db.session.add(story_row) # pylint: disable=maybe-no-member
        db.session.commit() # pylint: disable=maybe-no-member
        db.session.refresh(story_row) # pylint: disable=maybe-no-member
        page_index_to_id_map = dict()
        for page in story['pages']:
            index = page['index']
            text = page['text']
            outcome = outcomeFromResult(tryGetValue(page, 'result'))
            page_row = Pages(story_id=story_row.story_id, text=text, outcome=outcome)
            db.session.add(page_row) # pylint: disable=maybe-no-member
            db.session.commit() # pylint: disable=maybe-no-member
            db.session.refresh(page_row) # pylint: disable=maybe-no-member
            page_index_to_id_map[index] = page_row.page_id
        for page in story['pages']:
            index = page['index']
            page_id = page_index_to_id_map[index]
            for choice, to_page in page['choices'].items():
                if to_page == 0: continue
                to_page_id = page_index_to_id_map[to_page]
                choice_row = Choices(story_id=story_row.story_id, page_id=page_id, text=choice, to_page=to_page_id)
                db.session.add(choice_row) # pylint: disable=maybe-no-member
                db.session.commit() # pylint: disable=maybe-no-member

@app.cli.command('db_create')
def dbCreate():
    db.create_all()
    print('Created database tables')

@app.cli.command('db_reset')
def dbReset():
    db.drop_all()
    db.create_all()
    print('Reset database tables')

@app.cli.command('db_load_stories')
def dbLoadStories():
    loadStory("static/kolb.json")
    loadStory("static/zork.json")
    print("Stories loaded")
