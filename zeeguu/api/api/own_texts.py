import flask
import sqlalchemy
from flask import request

from zeeguu.core.model import Article, Language, CohortArticleMap

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api, db_session

print("loading api/owntexts")


@api.route("/upload_own_text", methods=["POST"])
@cross_domain
@with_session
def upload_own_text():

    db_session.rollback()
    language = Language.find_or_create(request.form.get("language", ""))
    content = request.form.get("content", "")
    title = request.form.get("title", "")

    new_article_id = Article.create_from_upload(
        db_session, title, content, flask.g.user, language
    )

    return str(new_article_id)


@api.route("/own_texts", methods=["GET"])
@cross_domain
@with_session
def own_texts():
    r = [e.article_info() for e in Article.own_texts_for_user(flask.g.user)]
    return json_result(r)


@api.route("/delete_own_text/<id>", methods=["GET"])
@cross_domain
@with_session
def delete_own_text(id):

    try:
        a = Article.query.filter(Article.id == id).one()
        a.deleted = 1
        db_session.commit()

        CohortArticleMap.delete_all_for_article(db_session, id)

        return "OK"

    except sqlalchemy.orm.exc.NoResultFound:
        return "An article with that ID does not exist."


@api.route("/update_own_text/<article_id>", methods=["POST"])
@cross_domain
@with_session
def update_own_text(article_id):

    language = Language.find_or_create(request.form.get("language", ""))
    content = request.form.get("content", "")
    title = request.form.get("title", "")

    a = Article.query.filter(Article.id == article_id).one()
    a.update(language, content, title)

    db_session.add(a)
    db_session.commit()

    return "OK"