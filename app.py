import flask
#from flask_talisman import Talisman
import pickle
import numpy as np
import pandas as pd
import requests, json, random, os, schedule, time
from fpl import FPL
import pymongo
from pymongo import MongoClient
from datetime import datetime

app = flask.Flask(__name__, template_folder='templates')
#Talisman(app)

# env_variables
# MONGODB = os.getenv('MONGODB', None)
# RAPIDAPIKEY = os.getenv('RAPIDAPIKEY', None)
RAPIDAPIKEY = "b49dab746amsh92ab31faa3e490dp105183jsncd7a70b49a7e"
MONGODB = "mlfc"

cluster = MongoClient("mongodb+srv://jackculpan:{}@cluster0-vamzb.gcp.mongodb.net/mlfc".format(MONGODB))
db = cluster["mlfc"]
players_df = pd.read_csv("https://raw.githubusercontent.com/jackculpan/mlfc/master/2016-2020_extra_gw_stats.csv")
latest_teams = players_df[players_df['season'] == 19]
latest_teams = latest_teams[latest_teams['round']==max(latest_teams['round'])]

data = json.loads((requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')).content)
players_raw = pd.DataFrame(data['elements'])
players_raw['chance_of_playing_next_round'].replace("None", 100, inplace=True)
players_raw['chance_of_playing_next_round'] = pd.to_numeric(players_raw['chance_of_playing_next_round'])

@app.route('/', methods=['GET', 'POST'])
def main():
  session = requests.session()
  if flask.request.method == 'GET':
    return(flask.render_template('main.html'))

  if flask.request.method == 'POST':
    email = flask.request.form['email']
    password = flask.request.form['password']
    user_id = flask.request.form['user_id']
    gameweek = int(flask.request.form['gameweek'])
    session = authenticate(session, email, password)

    team_info = get_team(session, user_id)
    chips = [{"name":team_info['chips'][i]['name'], "value":team_info['chips'][i]['status_for_entry']} for i in range(len(team_info['chips']))]

    players = [latest_teams[latest_teams['id']==team_info['picks'][i]['element']] for i in range(len(team_info['picks']))]
    players = pd.concat(players)
    players = pd.merge(players, players_raw, on='id')

    if len(players) > 1:
      collection = db["lstm_predictions_total"]
      players['prediction'] = np.zeros(len(players))
      players['opponent_short_team_name']= ""
      for i in range(len(players)):
        if collection.find_one({"id":str(players['id'].iloc[i]), "event":gameweek}) != None:
          player = collection.find_one({"id":str(players['id'].iloc[i]), "event":gameweek})
          players['prediction'].iloc[i] = float(player['prediction'])
          players['opponent_short_team_name'].iloc[i] = player['opponent_short_team_name']

      #gw_players = [gw_players[gw_players['id'] == players['id'].iloc[i]] for i in range(len(players))]
      #gw_players = pd.concat(gw_players)
      #print(gw_players)
      #players = pd.merge(players, gw_players[['id','was_home', 'team_short_name', 'opponent_short_team_name','prediction']], on='id', )

      #players['prediction'] = pd.to_numeric(players['prediction'])

      #players['prediction'] = [float(return_prediction(players['id'].iloc[i], gameweek)['prediction']) for i in range(len(players))]
      #players['team_short_name'] = [return_prediction(players['id'].iloc[i],gameweek)['team_short_name'] for i in range(len(players))]
      #players['opponent_short_team_name'] = [return_prediction(players['id'].iloc[i],gameweek)['opponent_short_team_name'] for i in range(len(players))]
      #players['was_home'] = [return_prediction(players['id'].iloc[i],gameweek)['was_home'] for i in range(len(players))]

      for i in range(len(players)):
        if players['chance_of_playing_next_round'].iloc[i] > 50:
          players['prediction'].iloc[i] = 0.0
        if players['was_home'].iloc[i] == True:
          players['team_short_name'].iloc[i]=str(players['team_short_name'].iloc[i]) + " (H)"
        if players['was_home'].iloc[i] == False:
          players['opponent_short_team_name'].iloc[i]=str(players['opponent_short_team_name'].iloc[i]) + " (H)"
        if team_info['picks'][i]['is_captain'] == True:
          element = team_info['picks'][i]['element']
          captain = players[players['id']==element].name.values[0]
          # print(players[players['id']==element].name.values[0]+ " (C)")
          # players[players['id']==element].name = players[players['id']==element].name.values[0] + " (C)"
        elif team_info['picks'][i]['is_vice_captain'] == True:
          element = team_info['picks'][i]['element']
          players[players['id']==element].prediction = players[players['id']==element].prediction * 2
          vice_captain = players[players['id']==element].name.values[0]
          # players[players['id']==element]['name'] = str(players[players['id']==element].name.values[0] + " (VC)")

    subs = players.iloc[-4:].copy()
    cond = players['id'].isin(subs['id'])
    players.drop(players[cond].index, inplace = True)


    strikers = players[players.player_position==4]
    midfielders = players[players.player_position==3]
    defenders = players[players.player_position==2]
    goalkeepers = players[players.player_position==1]

    team_points = int(sum(players.prediction))
    sub_points = int(sum(subs.prediction))
    team_cost = sum(players.now_cost)/10
    sub_cost = sum(subs.now_cost)/10

    return flask.render_template('main.html',
                                 gameweek=(gameweek),
                                 original_input={'user_id':int(user_id), 'email':str(email),'password':str(password)},
                                 strikers=(zip(strikers['name'], strikers['team_short_name'], strikers['opponent_short_team_name'], strikers['prediction'].round())),\
                                 midfielders=(zip(midfielders['name'],midfielders['team_short_name'], midfielders['opponent_short_team_name'], midfielders['prediction'].round())), \
                                 defenders=(zip(defenders['name'], defenders['team_short_name'], defenders['opponent_short_team_name'], defenders['prediction'].round())), \
                                 goalkeepers=(zip(goalkeepers['name'], goalkeepers['team_short_name'], goalkeepers['opponent_short_team_name'],  goalkeepers['prediction'].round())),\
                                 subs=(zip(subs['name'], subs['team_short_name'],subs['opponent_short_team_name'], subs['prediction'].round())),\
                                 stats=(team_points, sub_points, team_cost, sub_cost),\
                                 captain=(captain, vice_captain),
                                 chips=(chips)
                                 )


@app.route('/dreamteam', methods=['GET', 'POST'])
def dreamteam():
  if flask.request.method == 'GET':
    gameweek = get_recent_gameweek_id()
  if flask.request.method == 'POST':
    gameweek = int(flask.request.form['gameweek'])
  return return_dreamteam(gameweek)


def return_dreamteam(gameweek):
    dreamteam_players = pd.merge(latest_teams, players_raw, on='id')

    #players = players[['id', 'prediction', 'opponent_short_team_name', 'team_code', 'web_name', 'team_short_name', '']]

    #print(players[['team_code', 'team_id']])

    # if len(players) > 1:
    #   collection = db["lstm_predictions_total"]
    #   players['prediction'] = np.zeros(len(players))
    #   players['opponent_short_team_name']= ""
    #   for i in range(len(players)):
    #     if collection.find_one({"id":str(players['id'].iloc[i]), "event":gameweek}) != None:
    #       player = collection.find_one({"id":str(players['id'].iloc[i]), "event":gameweek})
    #       players['prediction'].iloc[i] = float(player['prediction'])
    #       players['opponent_short_team_name'].iloc[i] = player['opponent_short_team_name']

    # players = players[players['prediction'] > 0]


    #     ids.append(latest_teams['id'].iloc[i])

    # cond = latest_teams['id'].isin(ids)
    # latest_teams.drop(latest_teams[cond].index, inplace = True)
    # players = latest_teams

    # print(latest_teams)
    collection = db["lstm_predictions_total"]
    top_20 = pd.DataFrame(collection.find({"event":gameweek}))
    top_20['id']=top_20['id'].astype(int)
    dreamteam_players['id']=dreamteam_players['id'].astype(int)
    top_20 = top_20[['id', 'event', 'opponent_short_team_name', 'prediction']]


    dreamteam_players = [dreamteam_players[dreamteam_players['id'] == top_20['id'].iloc[i]] for i in range(len(top_20))]
    dreamteam_players = pd.concat(dreamteam_players)


    dreamteam_players = pd.merge(top_20, dreamteam_players, on='id')
    dreamteam_players['prediction'] = pd.to_numeric(dreamteam_players['prediction'])

    # print(f"gameweek ={gameweek}=")
    #print(players)

    dreamteam_players = dreamteam_players[dreamteam_players['minutes_x'].values>0]
    dreamteam_players = dreamteam_players[dreamteam_players['chance_of_playing_next_round'].values > 50]
    dreamteam_players= dreamteam_players.reset_index()
    # print(dreamteam_players)

    names = dreamteam_players.web_name
    prices = dreamteam_players['now_cost']/10
    captain_selection=[]
    selection,sub_selection = [],[]

    decisions, captain_decisions, sub_decisions = select_team(dreamteam_players.prediction, prices, dreamteam_players.element_type, dreamteam_players.team_id)

    for i in range(dreamteam_players.shape[0]):
      if decisions[i].value() != 0:
          #print("**{}** Points = {}, Price = {}".format(names[i], players.prediction[i], prices[i]))
          selection.append(names[i])
      if captain_decisions[i].value() == 1:
          #print("**CAPTAIN: {}** Points = {}, Price = {}".format(names[i], players.prediction[i], prices[i]))
          captain_selection.append(names[i])
      if sub_decisions[i].value() == 1:
          #print("**SUBS: {}** Points = {}, Price = {}".format(names[i], players.prediction[i], prices[i]))
          sub_selection.append(names[i])

    subs = [dreamteam_players[dreamteam_players.web_name == sub_selection[i]] for i in range(len(sub_selection))]
    subs = pd.concat(subs)

    dreamteam_players = [dreamteam_players[dreamteam_players.web_name == selection[i]] for i in range(len(selection))]
    dreamteam_players = pd.concat(dreamteam_players)

    for i in range(len(dreamteam_players)):
      if dreamteam_players['was_home'].iloc[i] == "True":
        dreamteam_players['team_short_name'].iloc[i]=str(dreamteam_players['team_short_name'].iloc[i]) + " (H)"
      if dreamteam_players['was_home'].iloc[i] == "False":
        dreamteam_players['opponent_short_team_name'].iloc[i]=str(dreamteam_players['opponent_short_team_name'].iloc[i]) + " (H)"
      if dreamteam_players['web_name'].iloc[i] == captain_selection[0]:
        dreamteam_players['prediction'].iloc[i] = dreamteam_players['prediction'].iloc[i] * 2

    for i in range(len(subs)):
      if subs['was_home'].iloc[i] == "True":
        subs['team_short_name'].iloc[i]=str(subs['team_short_name'].iloc[i]) + " (H)"
      elif subs['was_home'].iloc[i] == "False":
        subs['opponent_short_team_name'].iloc[i]=str(subs['opponent_short_team_name'].iloc[i]) + " (H)"

    subs.sort_values(by=['element_type'], inplace=True)

    captains = [dreamteam_players[dreamteam_players.web_name == captain_selection[i]] for i in range(len(captain_selection))]
    captains = pd.concat(captains)

    strikers = dreamteam_players[dreamteam_players.element_type==4]
    midfielders = dreamteam_players[dreamteam_players.element_type==3]
    defenders = dreamteam_players[dreamteam_players.element_type==2]
    goalkeepers = dreamteam_players[dreamteam_players.element_type==1]

    team_points = int(sum(dreamteam_players.prediction))
    sub_points = int(sum(subs.prediction))
    team_cost = sum(dreamteam_players.now_cost)/10
    sub_cost = sum(subs.now_cost)/10

    return flask.render_template('dreamteam.html',
                                 gameweek=(gameweek),
                                 strikers=(zip(strikers['web_name'], strikers['team_short_name'], strikers['opponent_short_team_name'], strikers['prediction'].round())),\
                                 midfielders=(zip(midfielders['web_name'],midfielders['team_short_name'], midfielders['opponent_short_team_name'], midfielders['prediction'].round())), \
                                 defenders=(zip(defenders['web_name'], defenders['team_short_name'], defenders['opponent_short_team_name'], defenders['prediction'].round())), \
                                 goalkeepers=(zip(goalkeepers['web_name'], goalkeepers['team_short_name'], goalkeepers['opponent_short_team_name'],  goalkeepers['prediction'].round())),\
                                 subs=(zip(subs['web_name'], subs['team_short_name'],subs['opponent_short_team_name'], subs['prediction'].round())),\
                                 stats=(team_points, sub_points, team_cost, sub_cost),\
                                 captain=(captains['web_name'].iloc[0], captains['web_name'].iloc[1]),
                                 )

@app.route('/team', methods=['GET'])
def team():
  if flask.request.method == 'GET':
    return(flask.render_template('team.html'))

def authenticate(session, email, password):
  url = 'https://users.premierleague.com/accounts/login/'
  payload = {
   'password': str(password),
   'login': str(email),
   'redirect_uri': 'https://fantasy.premierleague.com/a/login',
   'app': 'plfpl-web'
  }
  session.post(url, data=payload)
  return session


def get_team(session, user_id):
  team_info = session.get(f'https://fantasy.premierleague.com/api/my-team/{user_id}/').json()
  store_team(user_id, team_info, session)
  return team_info

def return_name(player):
  return player.first_name + " " + player.second_name

from pulp import *

def select_team(expected_scores, prices, positions, clubs, total_budget=100, sub_factor=0.2):
    num_players = len(expected_scores)
    model = LpProblem("Constrained value maximisation", LpMaximize)
    decisions = [
        LpVariable("x{}".format(i), lowBound=0, upBound=1, cat='Integer')
        for i in range(num_players)
    ]
    captain_decisions = [
        LpVariable("y{}".format(i), lowBound=0, upBound=1, cat='Integer')
        for i in range(num_players)
    ]
    sub_decisions = [
        LpVariable("z{}".format(i), lowBound=0, upBound=1, cat='Integer')
        for i in range(num_players)
    ]


    # objective function:
    model += sum((captain_decisions[i] + decisions[i] + sub_decisions[i]*sub_factor) * expected_scores[i]
                 for i in range(num_players)), "Objective"

    # cost constraint
    model += sum((decisions[i] + sub_decisions[i]) * prices[i] for i in range(num_players)) <= total_budget  # total cost

    # position constraints
    # 1 starting goalkeeper
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 1) == 1
    # 2 total goalkeepers
    model += sum(decisions[i] + sub_decisions[i] for i in range(num_players) if positions[i] == 1) == 2

    # 3-5 starting defenders
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 2) >= 3
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 2) <= 5
    # 5 total defenders
    model += sum(decisions[i] + sub_decisions[i] for i in range(num_players) if positions[i] == 2) == 5

    # 3-5 starting midfielders
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 3) >= 3
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 3) <= 5
    # 5 total midfielders
    model += sum(decisions[i] + sub_decisions[i] for i in range(num_players) if positions[i] == 3) == 5

    # 1-3 starting attackers
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 4) >= 1
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 4) <= 3
    # 3 total attackers
    model += sum(decisions[i] + sub_decisions[i] for i in range(num_players) if positions[i] == 4) == 3

    # club constraint
    for club_id in np.unique(clubs):
        model += sum(decisions[i] + sub_decisions[i] for i in range(num_players) if clubs[i] == club_id) <= 3  # max 3 players

    model += sum(decisions) == 11  # total team size
    model += sum(captain_decisions) == 2  # 1 captain

    for i in range(num_players):
        model += (decisions[i] - captain_decisions[i]) >= 0  # captain must also be on team
        model += (decisions[i] + sub_decisions[i]) <= 1  # subs must not be on team

    model.solve()
    print("Total expected score = {}".format(model.objective.value()))

    return decisions, captain_decisions, sub_decisions


def rapid_api_call(url):
  querystring = {"timezone":"Europe/London"}
  headers = {
      'x-rapidapi-host': "api-football-v1.p.rapidapi.com",
      'x-rapidapi-key': RAPIDAPIKEY
      }
  response = requests.request("GET", url, headers=headers, params=querystring).json()
  return response

#@app.route('/', methods=['GET'])
def get_fixtures():
  url = "https://api-football-v1.p.rapidapi.com/v2/fixtures/league/524/next/20"
  response = rapid_api_call(url)
  collection = db["upcoming_fixtures"]

  for fixture in response['api']['fixtures']:
    if collection.find_one({"fixture_id":fixture['fixture_id']}) == None:
      collection.insert_one(fixture)
    else:
      collection.find_one_and_update({"fixture_id":fixture['fixture_id']}, {"$set": fixture})
    get_predictions(fixture['fixture_id'])

  return "upcoming fixtures updated"


def get_predictions(fixture_id):
  url = f"https://api-football-v1.p.rapidapi.com/v2/predictions/{fixture_id}"
  response = rapid_api_call(url)
  collection = db["fixture_info"]

  for fixture in response['api']['predictions']:
    fixture['fixture_id'] = fixture_id
    if collection.find_one({"fixture_id":fixture_id}) == None:
      collection.insert_one(fixture)
    else:
      collection.find_one_and_update({"fixture_id":fixture['fixture_id']}, {"$set": fixture})

  return "fixture updated"

def store_team(user_id, team_info, session):
  collection = db["user_info"]
  team_info['user_id'] = user_id
  team_info['session'] = session.cookies.get_dict()
  if collection.find_one({"user_id":user_id}) == None:
    collection.insert_one(team_info)
  else:
    collection.find_one_and_update({"user_id":user_id}, {"$set": team_info})

def return_prediction(player_id, gameweek):
    collection = db["lstm_predictions_total"]
    player = collection.find_one({"id":int(player_id), "event":gameweek})
    return player

def return_upcoming_fixture(player_id):
    collection = db["lstm_predictions"]
    player = collection.find_one({"id":int(player_id)})
    return player['opponent_team_name']

def get_recent_gameweek_id():
    """
    Get's the most recent gameweek's ID.
    """

    data = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
    data = json.loads(data.content)

    gameweeks = data['events']
    now = datetime.utcnow()
    for gameweek in gameweeks:
        next_deadline_date = datetime.strptime(gameweek['deadline_time'], '%Y-%m-%dT%H:%M:%SZ')
        if next_deadline_date > now:
            return gameweek['id'] - 1

if __name__ == '__main__':
    app.run(debug=True)
    #asyncio.run(main())
