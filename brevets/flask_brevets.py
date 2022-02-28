"""
Replacement for RUSA ACP brevet time calculator
(see https://rusa.org/octime_acp.html)

"""

import os
import flask
from flask import request
from werkzeug.exceptions import BadRequest
from pymongo import MongoClient  # Database
from bson import json_util
import arrow  # Replacement for datetime, based on moment.js
import acp_times  # Brevet time calculations
import config

import logging

###
# Globals
###

app = flask.Flask(__name__)
CONFIG = config.configuration()

client = MongoClient('mongodb://' + os.environ['MONGODB_HOSTNAME'], 27017)
db = client.brevets_database
brevet = db.calc_collection

###
# Pages
###


@app.route("/")
@app.route("/index")
def index():
    app.logger.debug("Main page entry")
    return flask.render_template('calc.html')


@app.errorhandler(404)
def page_not_found(error):
    app.logger.debug("Page not found")
    return flask.render_template('404.html'), 404


###############
#
# AJAX request handlers
#   These return JSON, rather than rendering pages.
#
###############
@app.route("/_calc_times")
def _calc_times():
    """
    Calculates open/close times from miles, using rules
    described at https://rusa.org/octime_alg.html.
    Expects: number of kilometers, brevet distance, date and time of start.
    """
    app.logger.debug("Got a JSON GET request")
    km = request.args.get('km', 999, type=float)
    app.logger.debug("km={}".format(km))
    br = request.args.get('brevet_dist_km', 200, type=int)
    app.logger.debug(f"brevet={br}")
    begin = request.args.get('begin_date', "2021-01-01T00:00", type=str)
    app.logger.debug(f"begin={begin}")
    app.logger.debug("request.args: {}".format(request.args))

    open_time = acp_times.open_time(km, br, arrow.get(begin)).format('YYYY-MM-DDTHH:mm')
    close_time = acp_times.close_time(km, br, arrow.get(begin)).format('YYYY-MM-DDTHH:mm')
    result = {"open": open_time, "close": close_time}
    return flask.jsonify(result=result)


@app.route("/_insert", methods=['POST'])
def _insert():

    app.logger.debug("Got a JSON POST request")
    
    # Check if valid json
    try:
        data = request.json
        if not all(x in data.keys() for x in ['brevet_dist_km', 'begin_date', 'table']):
            raise BadRequest("Data does not contain expected keys")
        if not any((x['km'] != None or x['miles'] != None) for x in data['table']):
            raise BadRequest("Empty table")
    except BadRequest as exc:
        app.logger.debug(f"Exception: {exc}")
        return flask.jsonify(error=str(exc)), 400

    
    app.logger.debug(f"brevet_dist_km: {data['brevet_dist_km']}")
    app.logger.debug(f"begin_date: {data['begin_date']}")
    #app.logger.debug(f"request.json: {request.json}")
    app.logger.debug(f"request.mimetype: {request.mimetype}")
    app.logger.debug(f"request.content_type: {request.content_type}")
    
    
    # Check that the table isn't empty (i.e. has distances)
    # empty = True  # To be falsified
    # for control in data['table']:
        # if control['km'] != None or control['miles'] != None:
            # empty = False
            # break
    # if empty == True:
        # app.logger.debug("Empty input")
        # return flask.jsonify(error="Empty input"), 400
    
    brevet.drop()
    brevet.insert_one(data)
    
    return flask.jsonify(success=True)


@app.route("/_fetch")
def _fetch():
    app.logger.debug("Got a fetch request")
    
    rt = flask.json.loads(json_util.dumps(brevet.find_one()))
    rt.pop('_id')
    
    app.logger.debug(f"brevet.find_one: {rt}")
    return flask.jsonify(rt)
    

#############

app.debug = CONFIG.DEBUG
if app.debug:
    app.logger.setLevel(logging.DEBUG)

if __name__ == "__main__":
    print("Opening for global access on port {}".format(CONFIG.PORT))
    app.run(port=CONFIG.PORT, host="0.0.0.0")
