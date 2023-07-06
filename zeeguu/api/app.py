# -*- coding: utf8 -*-
from zeeguu.core.configuration.configuration import load_configuration_or_abort
from flask_cors import CORS
from flask import Flask
import flask
import time

# apimux is quite noisy; supress it's output
import logging
from apimux.log import logger

logger.setLevel(logging.CRITICAL)


# *** Creating and starting the App *** #
app = Flask("Zeeguu-API")
CORS(app)

load_configuration_or_abort(
    app,
    "ZEEGUU_CONFIG",
    [  # first three are required by core
        "MAX_SESSION",
        "SQLALCHEMY_DATABASE_URI",
        "SQLALCHEMY_TRACK_MODIFICATIONS",
        # next three are required by API when
        # run locally
        "DEBUG",
        "HOST",
        "SECRET_KEY",
        # the following are required by the API
        # for user account creation & password recovery
        "INVITATION_CODES",
        "SMTP_EMAIL",
    ],
)

# The zeeguu.core.model  module relies on an app being injected from outside
# ----------------------------------------------------------------------
import zeeguu.core

zeeguu.core.app = app
import zeeguu.core.model

assert zeeguu.core.model
# -----------------

from .endpoints import api

app.register_blueprint(api)

# try:
#     import flask_monitoringdashboard as dashboard
#     from .custom_fmd_graphs import daily_visitors

#     dashboard.config.init_from(envvar="FLASK_MONITORING_DASHBOARD_CONFIG")

#     from zeeguu.core.model import Session

#     dashboard.config.get_group_by = lambda: Session.find(request=flask.request).user_id
#     dashboard.bind(app=app)
#     daily_visitors(dashboard)
#     print("Started the Flask Monitoring Dashboard")

# except Exception as e:
#     import traceback

#     traceback.print_exc()
#     print("flask_monitornig_dashboard package is not present. Running w/o FMD.")

try:
    from zeeguu.api.machine_specific import machine_specific_config

    machine_specific_config(app)
except ModuleNotFoundError as e:
    print("no machine specific code found")


start = time.time()

from zeeguu.core.nlp_pipeline import SpacyWrappers

end = time.time()
print("Loaded the spacy models in " + str(end - start) + " seconds")
