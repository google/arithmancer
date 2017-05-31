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
"""Main: Provides the routes and application logic"""

from flask import Flask
from google.appengine.ext import ndb
from google.appengine.api import users

import datetime
import math
import logging
import os
from flask import render_template
from flask import redirect
from flask import request
from flask import jsonify
from flask import flash

from models import Prediction
from models import Trade
from models import LedgerRecords
from models import Profile
from models import Price
from models import get_price_for_trade
from models import verification_of_trade
from models import check_if_user_profile
from models import calculate_trade_from_likelihood

app = Flask(__name__)
app.config['DEBUG'] = True
app.secret_key = os.environ['SECRET_KEY']


@app.route('/')
def CheckSignIn():
  user = users.get_current_user()
  if not user:
    login_url = users.create_login_url('/')
    greeting = '<a href="{}">Sign in</a>'.format(login_url)
    return render_template('splash.html', login=login_url)
  else:
    profile = check_if_user_profile(user.user_id())
    return redirect('/predictions')


@app.route('/predictions', methods=['GET'])
def GetPredictions():
  """Returns all of the predictions (and can filter by org)."""
  org_filter = request.args.get('org', False)
  if org_filter:
    predictions = Prediction.query(Prediction.org == org_filter).fetch()
  else:
    predictions = Prediction.query().fetch()
  for prediction in predictions:
    # TODO(goldhaber): add these to the datastore
    prediction.url = 'predictions/' + prediction.key.urlsafe()
    prediction.price = GetPriceByPredictionId(prediction.key.urlsafe()) * 100
  return render_template('predictions.html', predictions=predictions)


@app.route('/predictions/<string:prediction_id>/price', methods=['GET'])
def GetPriceByPredictionId(prediction_id):
  """Returns the current market price of contract one for a prediction_id."""
  prediction_key = ndb.Key(urlsafe=prediction_id)
  pred = prediction_key.get()
  price = math.pow(math.e, (pred.contract_one / pred.liquidity)) / (
      math.pow(math.e, (pred.contract_two / pred.liquidity)) + math.pow(
          math.e, (pred.contract_two / pred.liquidity)))
  return float(price)

@app.route('/predictions/<string:prediction_id>/pricelist', methods=['GET'])
def GetPrices(prediction_id):
    prices = Price.query(Price.prediction_id == ndb.Key(urlsafe=prediction_id)).order(-Price.date).fetch(30)
    print(str(prices))
    prices = [{'price': p.value, 'date': {'year': p.date.year, 'month': p.date.month, 'day': p.date.day}} for p in prices]
    return prices

@app.route('/predictions/<string:prediction_id>', methods=['GET'])
def GetPredictionById(prediction_id):
  """Returns a prediction by prediction_id."""
  try:
    prediction_key = ndb.Key(urlsafe=prediction_id)
    prediction = prediction_key.get()
    portfolio = GetUserPortfolioByAuth(prediction_id)
  except:
    return render_template('404.html')
  return render_template(
      'prediction.html',
      prediction=prediction,
      price=GetPriceByPredictionId(prediction_id),
      pricelist=GetPrices(prediction_id),
      prediction_id=prediction_id,
      portfolio=portfolio)

@app.route('/predictions/create', methods=['GET'])
def CreatePrediction():
  return render_template('prediction_create.html')

@app.route('/predictions/create/new', methods=['POST'])
def NewPrediction():
  try:
    prediction = Prediction(liquidity=float(request.form['liquidity']),
     info=request.form['info'],
     statement=request.form['statement'],
     end_time=datetime.datetime.strptime(request.form['endtime'], "%Y-%m-%d"),
     org=request.form['org'])
    prediction_id = prediction.put()
    flash('You created a new prediction!')
    return redirect('/predictions/' + prediction_id.urlsafe())
  except:
    flash('error')
    return redirect('/predictions/create')

@app.route('/users/create', methods=['GET'])
def CreateUser():
  """Route for checking if user exists."""
  profile = check_if_user_profile(users.get_current_user().user_id())
  return str(profile)


@app.route('/users/me', methods=['GET'])
def GetUserByAuth():
  """Returns current users profile."""
  user_key = users.get_current_user().user_id()
  user_key = ndb.Key('Profile', user_key)
  profile = user_key.get()
  for ledger in profile.user_ledger:
    try:
      price = GetPriceByPredictionId(ledger.prediction_id)
      ledger.value = math.fabs((price * ledger.contract_one) - (
          price * ledger.contract_two))
      ledger.prediction_statement = ndb.Key(
          urlsafe=ledger.prediction_id).get().statement
    except:
      ledger.value = 404
      ledger.prediction_statement = 'ERROR'
  return render_template('profile.html', profile=profile)


@app.route('/users/me/balance', methods=['GET'])
def GetUserBalanceByAuth():
  """Returns current users balance."""
  user_key = ndb.Key('Profile', users.get_current_user().user_id())
  profile = user_key.get()
  return str(profile.balance)

# TODO(goldhaber): change to GetUserPortfolioByAuth By Prediction ID
@app.route('/users/me/portfolio', methods=['GET'])
def GetUserPortfolioByAuth(prediction_id):
  """Returns current users porfolio by prediction_id."""
  user_key = ndb.Key('Profile', users.get_current_user().user_id())
  profile = user_key.get()
  portfolio = []
  if prediction_id:
    portfolio = [
        i for i in profile.user_ledger if i.prediction_id == prediction_id
    ]
  return portfolio

@app.route('/trades/create', methods=['POST'])
def CreateTrade():
  """Creates a trade for the user."""
  user_id = users.get_current_user().user_id()
  user_key = ndb.Key('Profile', user_id)
  current_user = user_key.get()
  prediction_key = ndb.Key(urlsafe=request.form['prediction_id'])
  prediction = prediction_key.get()
  if request.form['is_likelihood'] == 'true':
    user_id = users.get_current_user().user_id()
    user_key = ndb.Key('Profile', user_id)
    current_user = user_key.get()
    trade = calculate_trade_from_likelihood(
        float(request.form['likelihood']), prediction, current_user)
    print trade
  else:
    trade = Trade(
        prediction_id=prediction_key,
        user_id=user_key,
        direction=request.form['direction'],
        contract=request.form['contract'],
        quantity=float(request.form['quantity']))
  err = CreateTradeAction(prediction, current_user, trade)
  #TODO replace with error
  if err != 'error':
      flash('You successfully predicted!')
  return redirect('/predictions/' + trade.prediction_id.urlsafe())

def CreateTradeAction(prediction, current_user, trade):
  verification_of_trade(trade)
  price = get_price_for_trade(prediction, trade)
  # TODO(goldhaber):replace flag
  new_ledger_record = False
  if trade.direction == 'BUY':
    if current_user.balance >= price:
      current_user.balance -= price
      # TODO(goldhaber): check results and/or better formatting
      current_user_portfolio = [
          i for i in current_user.user_ledger
          if i.prediction_id == trade.prediction_id.urlsafe()
      ]
      if len(current_user_portfolio) == 0:
        ledger_records = LedgerRecords()
        ledger_records.prediction_id = trade.prediction_id.urlsafe()
        ledger_records.user_id = current_user.user_id
        if trade.contract == 'CONTRACT_ONE':
          ledger_records.contract_one = trade.quantity
          ledger_records.contract_two = 0.00
        else:
          ledger_records.contract_two = trade.quantity
          ledger_records.contract_one = 0.00
        current_user.user_ledger.append(ledger_records)
        new_ledger_record = True
      else:
        ledger_record_to_update = current_user_portfolio[0]
        if trade.contract == 'CONTRACT_ONE':
          ledger_record_to_update.contract_one += trade.quantity
        else:
          ledger_record_to_update.contract_two += trade.quantity
      if trade.contract == 'CONTRACT_ONE':
        prediction.contract_one += trade.quantity
      else:
        prediction.contract_two += trade.quantity
    else:
      # TODO(goldhaber): throw error
      return 'error'
  else:
    current_user_portfolio = [
        i for i in current_user.user_ledger
        if i.prediction_id == trade.prediction_id.urlsafe()
    ]
    if (trade.contract == 'CONTRACT_ONE' and
        current_user_portfolio[0].contract_one >= trade.quantity) or (
            trade.contract == 'CONTRACT_TWO' and
            current_user_portfolio[0].contract_two >= trade.quantity):
      ledger_record_to_update = current_user_portfolio[0]
      if trade.contract == 'CONTRACT_ONE':
        ledger_record_to_update.contract_one -= trade.quantity
        prediction.contract_one -= trade.quantity
      else:
        ledger_record_to_update.contract_two -= trade.quantity
        prediction.contract_two -= trade.quantity
      current_user.balance -= price
    else:
      return 'error'
  trade.put()
  if new_ledger_record:
    ledger_records.put()
  current_user.put()
  prediction.put()


@app.route('/trades/sell', methods=['POST'])
def SellStake():
  user_id = users.get_current_user().user_id()
  user_key = ndb.Key('Profile', user_id)
  current_user = user_key.get()
  prediction_key = ndb.Key(urlsafe=request.form['prediction_id'])
  prediction = prediction_key.get()
  portfolio = GetUserPortfolioByAuth(request.form['prediction_id'])
  for ledger in portfolio:
      if ledger.contract_one > 0:
          contract = 'CONTRACT_ONE'
          quantity = ledger.contract_one
      else:
          contract = 'CONTRACT_TWO'
          quantity = ledger.contract_two
  trade = Trade(
      prediction_id=prediction_key,
      user_id=user_key,
      direction='SELL',
      contract=contract,
      quantity=float(quantity))
  err = CreateTradeAction(prediction, current_user, trade)
  if err != 'error':
      flash('You sold your stake!')
  return redirect('/users/me')

@app.route('/testtrade/<string:prediction_id>', methods=['GET'])
def GetTradesForPredictionId(prediction_id):
    user = users.get_current_user()
    trades = Trade.query(ndb.AND(Trade.prediction_id == ndb.Key(urlsafe=prediction_id),
                                 Trade.user_id == ndb.Key('Profile', user.user_id()))).fetch()
    return str(trades)

@app.route('/faq', methods=['GET'])
def GetFaq():
  return render_template('faq.html')


@app.errorhandler(404)
def page_not_found(e):
  """Return a custom 404 error."""
  return render_template('404.html'), 404

@app.context_processor
def inject_balance():
    user = users.get_current_user()
    if not user:
        return dict(balance=0)
    user_key = ndb.Key('Profile', user.user_id())
    profile = user_key.get()
    return dict(balance=profile.balance)
