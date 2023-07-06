import os.path
import re

from flask import request

from zeeguu.api.api import api
from zeeguu.api.api.utils.route_wrappers import cross_domain, with_session

from zeeguu.api.app import app

DATA_FOLDER = os.environ.get("ZEEGUU_DATA_FOLDER")


@api.route("/text_to_speech", methods=("POST",))
@cross_domain
@with_session
def tts():
    import zeeguu.core
    from zeeguu.core.model import UserWord, Language

    db_session = zeeguu.core.db.session

    text_to_pronounce = request.form.get("text", "")
    language_id = request.form.get("language_id", "")

    if not text_to_pronounce:
        return ""

    user_word = UserWord.find_or_create(
        db_session, text_to_pronounce, Language.find_or_create(language_id)
    )

    audio_file_path = _file_name_for_user_word(user_word, language_id)

    if not os.path.isfile(DATA_FOLDER + audio_file_path):
        _save_speech_to_file(user_word.word, language_id, audio_file_path)

    print(audio_file_path)
    return audio_file_path


@api.route("/mp3_of_full_article", methods=("POST",))
@cross_domain
@with_session
def mp3_of_full_article():
    print("in mp3_of_full_article")
    import zeeguu.core
    from zeeguu.core.model import UserWord, Language

    db_session = zeeguu.core.db.session

    text_to_pronounce = request.form.get("text", "")
    language_id = request.form.get("language_id", "")
    article_id = request.form.get("article_id", "")

    print("ID:" + article_id)
    print("LANG ID:" + language_id)

    if (not text_to_pronounce) or (not article_id) or (not language_id):
        return ""

    audio_file_path = _file_name_for_full_article(
        text_to_pronounce, language_id, article_id
    )

    if not os.path.isfile(DATA_FOLDER + audio_file_path):
        _save_speech_to_file(text_to_pronounce, language_id, audio_file_path)

    print(audio_file_path)
    return audio_file_path


def _save_speech_to_file(text_to_speak, language_id, audio_file_path):
    from google.cloud import texttospeech

    # Instantiates a client
    client = texttospeech.TextToSpeechClient()

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=text_to_speak)

    # Build the voice request
    voice = texttospeech.VoiceSelectionParams(
        language_code=_code_from_id(language_id), name=_voice_for_id(language_id)
    )

    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # The response's audio_content is binary.
    with open(DATA_FOLDER + audio_file_path, "wb") as out:
        # Write the response to the output file.
        out.write(response.audio_content)


def _file_name_for_user_word(user_word, language_id):
    word_without_special_chars = re.sub("[^A-Za-z0-9]+", "_", user_word.word)
    return f"/speech/{language_id}_{user_word.id}_{word_without_special_chars}.mp3"


def _file_name_for_full_article(full_article_text, language_id, article_id):
    # create md5 hash of the user_word and return it
    import hashlib

    m = hashlib.md5()
    m.update(full_article_text.encode("utf-8"))
    return f"/speech/art_{article_id}_{language_id}_{m.hexdigest()}.mp3"


LANGUAGE_CODES = {
    "da": "da-DK",
    "fr": "fr-FR",
    "en": "en-US",
    "nl": "nl-NL",
}

VOICE_IDS = {
    "da": "da-DK-Wavenet-D",
    "fr": "fr-FR-Neural2-C",
    "en": "en-US",
    "nl": "nl-NL-Wavenet-B",
}


def _code_from_id(language_id):
    if LANGUAGE_CODES.get(language_id):
        return LANGUAGE_CODES[language_id]
    return "en-US"


def _voice_for_id(language_id):
    if VOICE_IDS.get(language_id):
        return VOICE_IDS[language_id]
    return "en-US"
