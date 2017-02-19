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
"""Tests for App."""

import unittest



if __name__ == '__main__':
  os.environ["SECRET_KEY"] = "TEST_SECRET"
  unittest.main()
# [START imports]

import unittest
import datetime

from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from models import Trade
from models import Prediction
from models import Profile
from models import LedgerRecords
from models import get_price_for_trade
from models import calculate_trade_from_likelihood
from main import CreateTrade
from main import GetPriceByPredictionId
from scorer import scoring

# [END imports]


# [START datastore_example_1]
class TestModel(ndb.Model):
  """A model class used for testing."""
  number = ndb.IntegerProperty(default=42)
  text = ndb.StringProperty()


class TestEntityGroupRoot(ndb.Model):
  """Entity group root"""
  pass


def GetEntityViaMemcache(entity_key):
  """Get entity from memcache if available, from datastore if not."""
  entity = memcache.get(entity_key)
  if entity is not None:
    return entity
  key = ndb.Key(urlsafe=entity_key)
  entity = key.get()
  if entity is not None:
    memcache.set(entity_key, entity)
  return entity



class PriceTestCase(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    ndb.get_context().clear_cache()

  def tearDown(self):
    self.testbed.deactivate()

  def testPriceForBuyTrade(self):
    prediction_key = Prediction(
        contract_one=0.00, contract_two=0.00,
        liquidity=100, statement="Test", end_time=datetime.datetime.now()).put()
    user_key = Profile().put()
    trade = Trade(
        prediction_id=prediction_key,
        user_id=user_key,
        direction='BUY',
        contract='CONTRACT_ONE',
        quantity=10.00)
    priceBuy = get_price_for_trade(prediction_key.get(), trade)
    self.assertEqual(5.124947951362557, priceBuy)
    prediction_key = Prediction(
        contract_one=10.00,
        contract_two=0.00,
        liquidity=100,
        statement="Test",
        end_time=datetime.datetime.now()).put()
    trade = Trade(
        prediction_id=prediction_key,
        user_id=user_key,
        direction='SELL',
        contract='CONTRACT_ONE',
        quantity=10.00)
    priceSale = get_price_for_trade(prediction_key.get(), trade)
    self.assertEqual(-5.124947951362557, priceSale)


class TradeTestCase(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    ndb.get_context().clear_cache()

  def tearDown(self):
    self.testbed.deactivate()

  def testBuyTradeLikelihood(self):
    prediction_key = Prediction(
        contract_one=0.00, contract_two=0.00, liquidity=100, statement="Test", end_time=datetime.datetime.now()).put()
    user_key = Profile(balance=100).put()
    profile = user_key.get()
    prediction = prediction_key.get()
    probability = 90
    trade_likeliness = calculate_trade_from_likelihood(probability, prediction,
                                                       profile)
    self.assertEqual(29.789603833999628, trade_likeliness.quantity)


class ScoringTestCase(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()

    ndb.get_context().clear_cache()

  def tearDown(self):
    self.testbed.deactivate()

  def testScoringCase(self):
    prediction_key = Prediction(
        contract_one=0.00,
        contract_two=0.00,
        liquidity=100,
        resolved=False,
        outcome='CONTRACT_ONE',
        statement='Test',
        end_time=datetime.datetime.now()).put()
    user_key = Profile(
        balance=100,
        user_ledger=[
            LedgerRecords(
                prediction_id=prediction_key.urlsafe(),
                contract_one=10.00,
                contract_two=0.00)
        ]).put()
    trade_key = Trade(
        prediction_id=prediction_key,
        user_id=user_key,
        direction='BUY',
        contract='CONTRACT_ONE',
        quantity=10).put()
    user = user_key.get()
    audit = scoring()
    self.assertEqual(10, audit[0]['earned'])


# [START main]
if __name__ == '__main__':
  unittest.main()
# [END main]
