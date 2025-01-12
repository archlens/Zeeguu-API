import re

from datetime import datetime
import time

import sqlalchemy
from langdetect import detect
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UnicodeText, Table
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound

import zeeguu.core
from zeeguu.core.content_retriever.url_downloader import download_url
from zeeguu.core.language.difficulty_estimator_factory import DifficultyEstimatorFactory
from zeeguu.core.util.encoding import datetime_to_json

db = zeeguu.core.db

article_topic_map = Table(
    "article_topic_map",
    db.Model.metadata,
    Column("article_id", Integer, ForeignKey("article.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)

MAX_CHAR_COUNT_IN_SUMMARY = 300

HTML_TAG_CLEANR = re.compile("<[^>]*>")


MULTIPLE_NEWLINES = re.compile("\n\s*\n")
# \n matches a line-feed (newline) character (ASCII 10)
# \s matches any whitespace character (equivalent to [\r\n\t\f\v  ])
# \n matches a line-feed (newline) character (ASCII 10)


"""
    Wed 23, Feb
    - added htmlContent - which should, from now on, be the favorite 
    content to be used when possible ; by default this is going to be 
    null; 

    April 15
    - added uploader_id - is set in the case in which a user uploads 
    their own text... 

"""


class Article(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    title = Column(String(512))
    authors = Column(UnicodeText)
    content = Column(UnicodeText())
    htmlContent = Column(UnicodeText())
    summary = Column(UnicodeText)
    word_count = Column(Integer)
    published_time = Column(DateTime)
    fk_difficulty = Column(Integer)
    broken = Column(Integer)
    deleted = Column(Integer)
    video = Column(Integer)

    from zeeguu.core.model.url import Url

    from zeeguu.core.model.feed import RSSFeed

    from zeeguu.core.model.language import Language

    rss_feed_id = Column(Integer, ForeignKey(RSSFeed.id))
    rss_feed = relationship(RSSFeed)

    url_id = Column(Integer, ForeignKey(Url.id), unique=True)
    url = relationship(Url)

    language_id = Column(Integer, ForeignKey(Language.id))
    language = relationship(Language)

    from zeeguu.core.model.user import User

    uploader_id = Column(Integer, ForeignKey(User.id))
    uploader = relationship(User)

    from zeeguu.core.model.topic import Topic

    topics = relationship(
        Topic, secondary="article_topic_map", backref=backref("articles")
    )

    # Few words in an article is very often not an
    # actual article but the caption for a video / comic.
    # Or maybe an article that's behind a paywall and
    # has only the first paragraph available
    MINIMUM_WORD_COUNT = 90

    def __init__(
        self,
        url,
        title,
        authors,
        content,
        summary,
        published_time,
        rss_feed,
        language,
        htmlContent="",
        uploader=None,
        found_by_user=0,  # tracks whether the user found this article (as opposed to us recommending it)
        broken=0,
        deleted=0,
        video=0,
    ):

        if not summary:
            summary = content[:MAX_CHAR_COUNT_IN_SUMMARY]

        self.url = url
        self.title = title
        self.authors = authors
        self.content = content
        self.htmlContent = htmlContent
        self.summary = summary
        self.published_time = published_time
        self.rss_feed = rss_feed
        self.language = language
        self.uploader = uploader
        self.userFound = found_by_user
        self.broken = broken
        self.deleted = deleted
        self.video = video

        self.convertHTML2TextIfNeeded()

        fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
        fk_difficulty = fk_estimator.estimate_difficulty(
            self.content, self.language, None
        )["grade"]

        # easier to store integer in the DB
        # otherwise we have to use Decimal, and it's not supported on all dbs
        self.fk_difficulty = fk_difficulty
        self.word_count = len(self.content.split())

    def __repr__(self):
        return f"<Article {self.title} (w: {self.word_count}, d: {self.fk_difficulty}) ({self.url})>"

    def vote_broken(self):
        # somebody could vote that this article is broken
        self.broken += 1

    def topics_as_string(self):
        topics = ""
        for topic in self.topics:
            topics += topic.title + " "
        return topics

    def contains_any_of(self, keywords: list):
        for each in keywords:
            if self.title.find(each) >= 0:
                return True
        return False

    def convertHTML2TextIfNeeded(self):
        # why this? because in some cases we might have htmlContent
        # but not content; and the following lines that compute
        # difficulty and length work on content
        if self.htmlContent and not self.content:
            self.content = re.sub(HTML_TAG_CLEANR, "", self.htmlContent)

    def update(self, language, content, htmlContent, title):
        self.language = language
        self.content = content
        self.title = title
        self.htmlContent = htmlContent

        self.convertHTML2TextIfNeeded()

        self.summary = content[:MAX_CHAR_COUNT_IN_SUMMARY]

        fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
        fk_difficulty = fk_estimator.estimate_difficulty(
            self.content, self.language, None
        )["grade"]

        self.fk_difficulty = fk_difficulty
        self.word_count = len(self.content.split())

    def article_info(self, with_content=False):
        """

            This is the data that is sent over the API
            to the Reader. Whatever the reader needs
            must be here.

        :return:
        """

        summary = self.content[:MAX_CHAR_COUNT_IN_SUMMARY]

        result_dict = dict(
            id=self.id,
            title=self.title,
            summary=summary,
            language=self.language.code,
            topics=self.topics_as_string(),
            video=self.video,
            metrics=dict(
                difficulty=self.fk_difficulty / 100, word_count=self.word_count
            ),
        )

        if self.authors:
            result_dict["authors"] = self.authors
        elif self.uploader:
            result_dict["authors"] = self.uploader.name
        else:
            result_dict["authors"] = ""

        if self.url:
            result_dict["url"] = self.url.as_string()

        if self.published_time:
            result_dict["published"] = datetime_to_json(self.published_time)

        if self.rss_feed:
            result_dict["feed_id"] = (self.rss_feed.id,)
            result_dict["icon_name"] = self.rss_feed.icon_name

            # TO DO: remove feed_image_url from RSSFeed --- this is here for compatibility
            # until the codebase is moved to zorg.
            if self.rss_feed.image_url:
                result_dict["feed_image_url"] = self.rss_feed.image_url.as_string()

        if with_content:
            result_dict["content"] = self.content
            result_dict["htmlContent"] = self.htmlContent

        result_dict["has_uploader"] = True if self.uploader_id else False

        return result_dict

    def article_info_for_teacher(self):
        from zeeguu.core.model import CohortArticleMap

        info = self.article_info()
        info["cohorts"] = CohortArticleMap.get_cohorts_for_article(self)

        return info

    def is_owned_by(self, user):
        return self.uploader_id == user.id

    def add_topic(self, topic):
        self.topics.append(topic)

    def add_search(self, search):
        self.searches.append(search)

    def remove_search(self, search):
        print("trying to remove a search term")
        self.searches.remove(search)

    def star_for_user(self, session, user, state=True):
        from zeeguu.core.model.user_article import UserArticle

        ua = UserArticle.find_or_create(session, user, self)
        ua.set_starred(state)
        session.add(ua)

    @classmethod
    def own_texts_for_user(cls, user, ignore_deleted=True):

        query = cls.query.filter(cls.uploader_id == user.id)

        if ignore_deleted:
            # by using > 0 we filter out both NULL and 0 values
            query = query.filter((cls.deleted == 0) | (cls.deleted.is_(None)))

        query = query.order_by(cls.id.desc())

        return query.all()

    @classmethod
    def create_clone(cls, session, source, uploader):
        # TODO: Why does this NOP the url?
        current_time = datetime.now()
        new_article = Article(
            None,
            source.title,
            None,
            source.content,
            source.summary,
            current_time,
            None,
            source.language,
            source.htmlContent,
            uploader,
        )
        session.add(new_article)

        session.commit()
        return new_article.id

    @classmethod
    def create_from_upload(
        cls, session, title, content, htmlContent, uploader, language
    ):

        current_time = datetime.now()
        new_article = Article(
            None,
            title,
            None,
            content,
            None,
            current_time,
            None,
            language,
            htmlContent,
            uploader,
        )
        session.add(new_article)

        session.commit()
        return new_article.id

    @classmethod
    def find_or_create(
        cls,
        session,
        _url: str,
        language=None,
        sleep_a_bit=False,
        htmlContent=None,
        title=None,
        authors: str = "",
    ):
        """

            If article for url found, return ID

            If not found,

                - if htmlContent is present, create article for that
                - if not, download and create article then return

        :param url:
        :return:
        """
        from zeeguu.core.model import Url, Article, Language

        url = Url.extract_canonical_url(_url)

        try:
            found = cls.find(url)
            if found:
                return found

            if htmlContent:
                text = re.sub(HTML_TAG_CLEANR, "", htmlContent)

                # replace many newlines with max two; in some
                # cases many newlines are left after stripping the html tags
                text = re.sub(MULTIPLE_NEWLINES, "\n\n", text)
                text = text.strip()

                summary = text[0:MAX_CHAR_COUNT_IN_SUMMARY]
                lang = detect(text)
            else:
                title, text, summary, lang, author_list = download_url(url, sleep_a_bit)
                authors = ", ".join(author_list or [])

            language = Language.find(lang)

            # Create new article and save it to DB
            url_object = Url.find_or_create(session, url)

            new_article = Article(
                url_object,
                title,
                authors,
                text,  # any article longer than this will be truncated...
                summary,
                datetime.now(),
                None,
                language,
                htmlContent,
            )
            session.add(new_article)
            session.commit()

            return new_article
        except sqlalchemy.exc.IntegrityError or sqlalchemy.exc.DatabaseError:
            for i in range(10):
                try:
                    session.rollback()
                    u = cls.find(url)
                    print("Found article by url after recovering from race")
                    return u
                except:
                    print("Exception of second degree in article..." + str(i))
                    time.sleep(0.3)
                    continue
                break

    @classmethod
    def find_by_id(cls, id: int):
        return Article.query.filter(Article.id == id).first()

    @classmethod
    def uploaded_by(cls, uploader_id: int):
        return Article.query.filter(Article.uploader_id == uploader_id).all()

    @classmethod
    def find(cls, url: str):
        """

            Find by url

        :return: object or None if not found
        """

        from zeeguu.core.model import Url

        try:
            url_object = Url.find(url)
            return (cls.query.filter(cls.url == url_object)).one()
        except NoResultFound:
            return None

    @classmethod
    def all_older_than(cls, days):
        import datetime

        today = datetime.date.today()
        long_ago = today - datetime.timedelta(days)
        try:
            return cls.query.filter(cls.published_time < long_ago).all()

        except NoResultFound:
            return []

    @classmethod
    def all_younger_than(cls, days):
        import datetime

        today = datetime.date.today()
        some_time_ago = today - datetime.timedelta(days)
        try:
            return cls.query.filter(cls.published_time > some_time_ago).all()

        except NoResultFound:
            return []

    @classmethod
    def exists(cls, article):
        try:
            cls.query.filter(cls.url == article.url).one()
            return True
        except NoResultFound:
            return False

    @classmethod
    def with_title_containing(cls, needle):
        return cls.query.filter(cls.title.like(f"%{needle}%")).all()
