import flask
import pickle
import numpy as np
import pandas as pd
import requests, json, random, os, schedule, time
from fpl import FPL
import pymongo
from pymongo import MongoClient
import difflib

app = flask.Flask(__name__, template_folder='templates')

# env_variables
# MONGODB = os.getenv('MONGODB', None)
# RAPIDAPIKEY = os.getenv('RAPIDAPIKEY', None)
RAPIDAPIKEY = "b49dab746amsh92ab31faa3e490dp105183jsncd7a70b49a7e"
MONGODB = "mlfc"

cluster = MongoClient("mongodb+srv://jackculpan:{}@cluster0-vamzb.gcp.mongodb.net/mlfc".format(MONGODB))
db = cluster["mlfc"]
players_df = pd.read_csv("https://raw.githubusercontent.com/jackculpan/mlfc/master/2016-2020_extra_gw_stats.csv")

# with open(f'model/rfr.pkl', 'rb') as f:
#     model = pickle.load(f)

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
    latest_teams = players_df[players_df['season'] == 19]
    #latest_teams = latest_teams[latest_teams['round']==max(latest_teams['round'])]
    latest_teams = latest_teams[latest_teams['round']==gameweek]
    players = [latest_teams[latest_teams['id']==team_info['picks'][i]['element']] for i in range(len(team_info['picks']))]
    players = pd.concat(players)

    if len(players) > 1:
      #gameweek=39
      #players_db = [return_prediction(players['id'].iloc[i]) for i in range(len(players))]
      #print(players_db)
      #players['prediction'] = [(float(players_db[i]['prediction']) for i in range(len(players)))]
      #players['team_short_name'] = [players_db[i]['team_short_name'] for i in range(len(players))]
      #players['opponent_short_team_name'] = [players_db[i]['opponent_short_team_name'] for i in range(len(players))]
      players['prediction'] = [float(return_prediction(players['id'].iloc[i], gameweek)['prediction']) for i in range(len(players))]
      #players['prediction'] = predictions
      players['team_short_name'] = [return_prediction(players['id'].iloc[i],gameweek)['team_short_name'] for i in range(len(players))]
      players['opponent_short_team_name'] = [return_prediction(players['id'].iloc[i],gameweek)['opponent_short_team_name'] for i in range(len(players))]
      players['was_home'] = [return_prediction(players['id'].iloc[i],gameweek)['was_home'] for i in range(len(players))]

      for i in range(len(players)):
        if players['was_home'].iloc[i] == "True":
          players['team_short_name'].iloc[i]=str(players['team_short_name'].iloc[i]) + " (H)"
        elif players['was_home'].iloc[i] == "False":
          players['opponent_short_team_name'].iloc[i]=str(players['opponent_short_team_name'].iloc[i]) + " (H)"
        if team_info['picks'][i]['is_captain'] == True:
          element = team_info['picks'][i]['element']
          captain = players[players['id']==element].name.values[0]
          # print(players[players['id']==element].name.values[0]+ " (C)")
          # players[players['id']==element].name = players[players['id']==element].name.values[0] + " (C)"
        elif team_info['picks'][i]['is_vice_captain'] == True:
          element = team_info['picks'][i]['element']
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

    return flask.render_template('main.html',
                                 original_input={'user_id':int(user_id), 'email':str(email),'password':str(password)},
                                 strikers=(zip(strikers['name'], strikers['team_short_name'], strikers['opponent_short_team_name'], strikers['prediction'].round())),\
                                 midfielders=(zip(midfielders['name'],midfielders['team_short_name'], midfielders['opponent_short_team_name'], midfielders['prediction'].round())), \
                                 defenders=(zip(defenders['name'], defenders['team_short_name'], defenders['opponent_short_team_name'], defenders['prediction'].round())), \
                                 goalkeepers=(zip(goalkeepers['name'], goalkeepers['team_short_name'], goalkeepers['opponent_short_team_name'],  goalkeepers['prediction'].round())),\
                                 subs=(zip(subs['name'], subs['team_short_name'],subs['opponent_short_team_name'], subs['prediction'].round())),\
                                 stats=(team_points, sub_points),\
                                 captain=(captain, vice_captain),
                                 chips=(chips)
                                 )


@app.route('/dreamteam', methods=['GET'])
def dream_team():
  latest_teams = pd.read_csv('https://raw.githubusercontent.com/jackculpan/Fantasy-Premier-League/master/data/2019-20/players_raw.csv')
  gameweek = 41
  #gameround = 32
  #latest_teams = players_df[players_df['season'] == 19]
  #print(latest_teams)

  collection = db["lstm_predictions_total"]
  top_20 = pd.DataFrame(collection.find({"event":gameweek}))
  top_20 = top_20.sort_values('prediction', ascending=False)
  players = [latest_teams[latest_teams['id'] == top_20['id'].iloc[i]] for i in range(len(top_20))]

  players = pd.concat(players)
  # players['prediction'] = np.zeros(len(players))
  # for i in range(len(players)):
  #   for j in range(len(top_20)):
  #     if players['id'].iloc[i] == top_20['id'].iloc[j]:
  #       players['prediction'].iloc[i] = float(top_20['prediction'].iloc[j])

  players = pd.merge(players, top_20, on='id')
  players['prediction'] = pd.to_numeric(players['prediction'])

  names = players.web_name
  prices = players['now_cost']/10
  #dreamteam = return_dreamteam(players)
  selection,captain_selection = [],[]
  decisions, captain_decisions = select_team(players.prediction, prices, players.element_type, players.team_code)
  for i in range(players.shape[0]):
    if decisions[i].value() != 0:
        print("**{}** Points = {}, Price = {}".format(names[i], players.prediction[i], prices[i]))
        selection.append(names[i])
  for i in range(players.shape[0]):
    if captain_decisions[i].value() == 1:
        print("**CAPTAIN: {}** Points = {}, Price = {}".format(names[i], players.prediction[i], prices[i]))
        captain_selection.append(names[i])

  players = [players[players.web_name == selection[i]] for i in range(len(selection))]
  players = pd.concat(players)
  captain = players[players.web_name == captain_selection[0]]
  # subs = players.iloc[-4:].copy()
  # cond = players['id'].isin(subs['id'])
  # players.drop(players[cond].index, inplace = True)


  strikers = players[players.element_type==4]
  midfielders = players[players.element_type==3]
  defenders = players[players.element_type==2]
  goalkeepers = players[players.element_type==1]

  team_points = int(sum(players.prediction))
  print(team_points)
  # sub_points = int(sum(subs.prediction))

  return flask.render_template('dreamteam.html',
                               strikers=(zip(strikers['web_name'], strikers['team_short_name'], strikers['opponent_short_team_name'], strikers['prediction'].round())),\
                               midfielders=(zip(midfielders['web_name'],midfielders['team_short_name'], midfielders['opponent_short_team_name'], midfielders['prediction'].round())), \
                               defenders=(zip(defenders['web_name'], defenders['team_short_name'], defenders['opponent_short_team_name'], defenders['prediction'].round())), \
                               goalkeepers=(zip(goalkeepers['web_name'], goalkeepers['team_short_name'], goalkeepers['opponent_short_team_name'],  goalkeepers['prediction'].round())),\
                               # subs=(zip(subs['web_name'], subs['team_short_name'],subs['opponent_short_team_name'], subs['prediction'].round())),\
                               # stats=(team_points, sub_points),\
                               stats=(team_points),\
                               # captain=(captain, vice_captain),
                               captain=(captain['web_name']),
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

def select_team(expected_scores, prices, positions, clubs):
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

    # objective function:
    model += sum((captain_decisions[i] + decisions[i]) * expected_scores[i]
                 for i in range(num_players)), "Objective"

    # cost constraint
    model += sum(decisions[i] * prices[i] for i in range(num_players)) <= 100  # total cost
    model += sum(decisions) == 11  # total team size

    # position constraints
    # 1 goalkeeper
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 1) == 1
    # 3-5 defenders
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 2) >= 3
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 2) <= 5
    # 3-5 midfielders
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 3) >= 3
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 3) <= 5
    # 1-3 attackers
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 4) >= 1
    model += sum(decisions[i] for i in range(num_players) if positions[i] == 4) <= 3

    # club constraint
    for club_id in np.unique(clubs):
        model += sum(decisions[i] for i in range(num_players) if clubs[i] == club_id) <= 3  # max 3 players

    model += sum(captain_decisions) == 1  # 1 captain

    for i in range(num_players):  # captain must also be on team
        model += (decisions[i] - captain_decisions[i]) >= 0

    model.solve()
    return decisions, captain_decisions


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

if __name__ == '__main__':
    app.run(debug=True)
    #asyncio.run(main())
