import flask
import pickle
import numpy as np
import pandas as pd
import requests, json, random, os, schedule, time
from fpl import FPL
import pymongo
from pymongo import MongoClient

app = flask.Flask(__name__, template_folder='templates')

# env_variables
MONGODB = os.getenv('MONGODB', None)
RAPIDAPIKEY = os.getenv('RAPIDAPIKEY', None)
RAPIDAPIKEY = "b49dab746amsh92ab31faa3e490dp105183jsncd7a70b49a7e"
MONGODB = "mlfc"

cluster = MongoClient("mongodb+srv://jackculpan:{}@cluster0-vamzb.gcp.mongodb.net/mlfc".format(MONGODB))
db = cluster["mlfc"]

with open(f'model/rfr.pkl', 'rb') as f:
    model = pickle.load(f)

@app.route('/', methods=['GET', 'POST'])
def main():
  session = requests.session()
  #players_df = pd.read_csv("https://raw.githubusercontent.com/jackculpan/Fantasy-Premier-League/master/data/2019-20/players_raw.csv",encoding = "ISO-8859-1")
  players_df = pd.read_csv("https://raw.githubusercontent.com/jackculpan/mlfc/master/2016-2020_extra_gw_stats.csv")
  if flask.request.method == 'GET':
    return(flask.render_template('main.html'))

  if flask.request.method == 'POST':
    email = flask.request.form['email']
    password = flask.request.form['password']
    user_id = flask.request.form['user_id']
    session = authenticate(session, email, password)
    team_info = get_team(session, user_id)
    latest_teams = players_df[players_df['season'] == 19]
    latest_teams = latest_teams[latest_teams['round']==1]
    players = [latest_teams[latest_teams['id']==team_info['picks'][i]['element']] for i in range(len(team_info['picks']))]
    players = pd.concat(players)


    # strikers = return_name(strikers)
    # midfielders = return_name(midfielders)
    # defenders = return_name(defenders)
    # goalkeepers = return_name(goalkeepers)
    players['prediction']=np.zeros(len(players))
    for i in range(len(players)):
      y_pred=model.predict([players[['team_a_score', 'team_h_score','minutes', 'was_home', 'opponent_team']].iloc[i]])
      players['prediction'].iloc[i]=y_pred.round()

    strikers = players[players.player_position==4]
    midfielders = players[players.player_position==3]
    defenders = players[players.player_position==2]
    goalkeepers = players[players.player_position==1]

    return flask.render_template('main.html',
                                 original_input={'user_id':int(user_id), 'email':str(email),'password':str(password)},
                                 strikers=(strikers.name), midfielders=(midfielders.name), defenders=(defenders.name), goalkeepers=(goalkeepers.name),\
                                 predictions=(zip(players['name'], players['prediction'])),result=(team_info['picks']),
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


if __name__ == '__main__':
    app.run(debug=True)
    #asyncio.run(main())
