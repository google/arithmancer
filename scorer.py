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
"""Scorer: Scores all completed predictions."""

import webapp2

import logging
import datetime

from models import Prediction, Trade, LedgerRecords, Profile
from google.appengine.ext import ndb


# TODO(goldhaber): this whole function is terrible; rewrite.
def scoring():
  #go through all predictions, check if should be scored
  predictions = Prediction.query(
      ndb.AND(Prediction.outcome != "UNKNOWN", Prediction.resolved == False)).fetch()
  audit = []
  # Get all trades by prediction_id
  for p in predictions:
    resolve = p.outcome
    trades = Trade.query(Trade.prediction_id == p.key).fetch()
    # Get user id from those trades
    users = [trade.user_id.get() for trade in trades]
    for u in users:
      # check user ledger, map outcome to 1 or 0 based on prediction outcome
      ledger = [i for i in u.user_ledger if i.prediction_id == p.key.urlsafe()]
      if resolve == 'CONTRACT_ONE':
        earned = ledger[0].contract_one
      else:
        earned = ledger[0].contract_two
      u.balance += earned
      audit.append({'user': u, 'earned': earned})
      u.put()
    p.resolved = True
    p.put()
  return audit


class ScorerHandler(webapp2.RequestHandler):

  def get(self):
    audit = scoring()
    logging.info(str(audit))
    self.response.status = 204


app = webapp2.WSGIApplication([('/.*', ScorerHandler),], debug=True)
