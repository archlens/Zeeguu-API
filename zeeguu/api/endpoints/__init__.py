import flask
import zeeguu.core
from .utils.route_wrappers import with_session
from .utils.json_result import json_result


api = flask.Blueprint("api", __name__)
db_session = zeeguu.core.db.session

print("loading api endpionts...")

# These files have to be imported after this line;
# They enrich the api object
from . import feature_toggles
from . import exercises
from . import sessions
from . import smartwatch
from . import system_languages
from . import translation
from . import activity_tracking
from . import bookmarks_and_words
from . import user
from . import user_statistics
from . import recommendations
from . import user_article
from . import user_articles
from . import user_languages
from .teacher_dashboard import *
from . import topics
from . import search
from . import article
from . import accounts
from . import speech
from . import own_texts
from .student import *
from .nlp import *
