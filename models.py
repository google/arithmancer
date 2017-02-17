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

"""Models and shared functions."""

import math

from google.appengine.api import users
from google.appengine.ext import ndb


class Prediction(ndb.Model):
  """Prediction model."""
  info = ndb.TextProperty()
  statement = ndb.StringProperty()
  creation_time = ndb.DateTimeProperty(auto_now_add=True)
  end_time = ndb.DateTimeProperty()
  contract_one = ndb.FloatProperty()
  contract_two = ndb.FloatProperty()
  liquidity = ndb.FloatProperty()
  org = ndb.StringProperty()
  outcome = ndb.StringProperty()
  resolved = ndb.BooleanProperty()
  access_group = ndb.StringProperty()

  def GetPriceByPredictionId(self):
    price = math.pow(math.e, (self.contract_one / self.liquidity)) / (
        math.pow(math.e, (self.contract_two / self.liquidity)) + math.pow(
            math.e, (self.contract_two / self.liquidity)))
    return float(price)

class LedgerRecords(ndb.Model):
  """Ledger model - for tracking ownership of shares by a user."""
  prediction_id = ndb.StringProperty()
  user_id = ndb.StringProperty()
  contract_one = ndb.FloatProperty()
  contract_two = ndb.FloatProperty()
  updated_time = ndb.DateTimeProperty()


class Profile(ndb.Model):
  """Profile model - user model."""
  user_id = ndb.StringProperty()
  user_email = ndb.StringProperty()
  balance = ndb.FloatProperty()
  # TODO(goldhaber): Change from structured property or properly configure hook
  user_ledger = ndb.StructuredProperty(LedgerRecords, repeated=True)


class Trade(ndb.Model):
  """Trade model - each trade that is made."""
  prediction_id = ndb.KeyProperty(kind=Prediction)
  user_id = ndb.KeyProperty(kind=Profile)
  direction = ndb.StringProperty()
  contract = ndb.StringProperty()
  quantity = ndb.FloatProperty()
  creation_time = ndb.DateTimeProperty(auto_now_add=True)

class Price(ndb.Model):
  prediction_id = ndb.KeyProperty(kind=Prediction)
  date = ndb.DateTimeProperty()
  value = ndb.FloatProperty()

# TODO(goldhaber): move into Trade Class
def get_price_for_trade(prediction, trade):
  """Returns the price of a trade for a prediction."""
  if trade.contract == 'CONTRACT_ONE':
    old_quantity = prediction.contract_one
    old_quantity_other = prediction.contract_two
  else:
    old_quantity = prediction.contract_two
    old_quantity_other = prediction.contract_one
  if trade.direction == 'BUY':
    new_quantity = old_quantity + trade.quantity
  else:
    new_quantity = old_quantity - trade.quantity
  price = (prediction.liquidity * math.log(
      math.pow(math.e, (new_quantity / prediction.liquidity)) +
      math.pow(math.e, (old_quantity_other / prediction.liquidity)))) - (
          prediction.liquidity * math.log(
              math.pow(math.e, (old_quantity / prediction.liquidity)) +
              math.pow(math.e, (old_quantity_other / prediction.liquidity))))
  return price


def check_if_user_profile(user_id):
  """Check if User has a profile, if not create a Profile."""
  profile_query = Profile.query(Profile.user_id == user_id).fetch()
  if len(profile_query) > 0:
    return True
  else:
    profile = Profile(
        user_id=users.get_current_user().user_id(),
        balance=100.00,
        user_email=users.get_current_user().email())
    profile.key = ndb.Key('Profile', users.get_current_user().user_id())
    profile_key = profile.put()
    return profile


def verification_of_trade(trade):
  # TODO(goldhaber): add form checks
  # trades should only be positive amounts. No shorting.
  return trade


def GetPriceByPredictionId(prediction_id):
  """Get current price by Prediction Id"""
  prediction_key = ndb.Key(urlsafe=prediction_id)
  pred = prediction_key.get()
  price = math.pow(math.e, (pred.contract_one / pred.liquidity)) / (
      math.pow(math.e, (pred.contract_two / pred.liquidity)) + math.pow(
          math.e, (pred.contract_two / pred.liquidity)))
  return float(price)


def calculate_trade_from_likelihood(probability, prediction, profile):
  """Calculate the trade using the Kelly Criterion"""
  probability = probability / 100.00
  print probability
  price = GetPriceByPredictionId(prediction.key.urlsafe())
  print price
  bankroll = (profile.balance) / 5
  bet = (bankroll * (((
      (1 - price) / price) * (probability) - (1 - probability)) / (
          (1 - price) / price)))
  current_user_portfolio = [
      i for i in profile.user_ledger
      if i.prediction_id == prediction.key.urlsafe()
  ]
  print current_user_portfolio
  if probability > price:
    contract = 'CONTRACT_ONE'
    primary = prediction.contract_one
    secondary = prediction.contract_two
    if len(current_user_portfolio) > 0:
      if current_user_portfolio[0].contract_two != 0:
        quantity = current_user_portfolio[0].contract_two
        direction = 'SELL'
        contract = 'CONTRACT_TWO'
        return Trade(
            prediction_id=prediction.key,
            user_id=profile.key,
            quantity=quantity,
            direction=direction,
            contract=contract)
  elif probability < price:
    contract = 'CONTRACT_TWO'
    primary = prediction.contract_two
    secondary = prediction.contract_one
    if len(current_user_portfolio) > 0:
      if current_user_portfolio[0].contract_one != 0:
        quantity = current_user_portfolio[0].contract_one
        direction = 'SELL'
        contract = 'CONTRACT_ONE'
        return Trade(
            prediction_id=prediction.key,
            user_id=profile.key,
            quantity=quantity,
            direction=direction,
            contract=contract)
  else:
    return 'No bet if its the same'
  direction = 'BUY'
  quantity = math.fabs(prediction.liquidity * math.log(
      math.pow(math.e, ((primary / prediction.liquidity) + (
          bet / prediction.liquidity))) + math.pow(math.e, ((
              secondary / prediction.liquidity) + (bet / prediction.liquidity)))
      - math.pow(math.e, (secondary / prediction.liquidity))) - primary)
  return Trade(
      prediction_id=prediction.key,
      user_id=profile.key,
      quantity=quantity,
      direction=direction,
      contract=contract)