#!/usr/bin/python
#
# Copyright 2017 Google, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Pricer: Generates a daily price for each prediction."""

import webapp2

import logging
import datetime

from models import Prediction, Trade, LedgerRecords, Profile, Price
from google.appengine.ext import ndb


def price():
  # {1/20/2017: [{pred_id: 1, price: $200}}
  predictions = Prediction.query(
      ndb.AND(Prediction.outcome == None, Prediction.resolved == None)).fetch()
  input_date = datetime.datetime.now()

  for p in predictions:
    price = Price(prediction_id=p.key,
                  date=input_date,
                  value=p.GetPriceByPredictionId())
    price.put()


class PriceHandler(webapp2.RequestHandler):

  def get(self):
    audit = price()
    logging.info(str(audit))
    self.response.status = 204


app = webapp2.WSGIApplication([('/.*', PriceHandler),], debug=True)
