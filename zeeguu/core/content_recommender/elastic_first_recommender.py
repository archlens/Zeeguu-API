"""
    Recommender that tries elastic first
    If it fails, falls back on the mixed recommender

"""
import traceback

import elasticsearch

from zeeguu.core import logp as log

from .elastic_recommender import (
    article_recommendations_for_user as elastic_article_recommendations_for_user,
    article_search_for_user as elastic_article_search_for_user,
)

from .mysql_recommender import (
    article_search_for_user as mixed_article_search_for_user,
    article_recommendations_for_user as mixed_article_recommendations_for_user,
)

ES_DOWN_MESSAGE = ">>>>>>>>>>>>>> ElasticSearch seems to be down. Falling back on MySQL recommendations"


def article_recommendations_for_user(
    user,
    count,
    es_scale="3d",
    es_decay=0.8,
    es_weight=4.2,
):
    try:

        return elastic_article_recommendations_for_user(
            user,
            count,
            es_scale,
            es_decay,
            es_weight,
        )

    except elasticsearch.exceptions.ConnectionError:
        log(ES_DOWN_MESSAGE)
        log(print(traceback.format_exc()))

    return mixed_article_recommendations_for_user(user, count)


def article_search_for_user(user, count, search_terms):
    try:

        return elastic_article_search_for_user(
            user,
            count,
            search_terms,
            es_scale="365d",
            es_decay=0.8,
            es_weight=4.2,
        )

    except elasticsearch.exceptions.ConnectionError:
        log(ES_DOWN_MESSAGE)
        log(print(traceback.format_exc()))

    return mixed_article_search_for_user(user, count, search_terms)
