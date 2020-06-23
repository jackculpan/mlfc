import requests
from flask import Flask, request, Response
import requests, json, random, os, schedule, time
import pymongo
from pymongo import MongoClient

app = Flask(__name__)

# env_variables
MONGODB = os.getenv('MONGODB', None)
RAPIDAPIKEY = os.getenv('RAPIDAPIKEY', None)
RAPIDAPIKEY = "b49dab746amsh92ab31faa3e490dp105183jsncd7a70b49a7e"

MONGODB = "mlfc"

cluster = MongoClient("mongodb+srv://jackculpan:{}@cluster0-vamzb.gcp.mongodb.net/mlfc".format(MONGODB))
db = cluster["mlfc"]
#collection = db["upcoming_fixtures"]

def rapid_api_call(url):
  querystring = {"timezone":"Europe/London"}
  headers = {
      'x-rapidapi-host': "api-football-v1.p.rapidapi.com",
      'x-rapidapi-key': RAPIDAPIKEY
      }
  response = requests.request("GET", url, headers=headers, params=querystring).json()
  return response

@app.route('/', methods=['GET'])
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
    fixture['teams']['home']['code'], fixture['teams']['home']['logo'] = get_fpl_team_data(fixture['teams']['home']['team_id'])
    fixture['teams']['away']['code'], fixture['teams']['away']['logo'] = get_fpl_team_data(fixture['teams']['away']['team_id'])

    fixture['fixture_id'] = fixture_id
    if collection.find_one({"fixture_id":fixture_id}) == None:
      collection.insert_one(fixture)
    else:
      collection.find_one_and_update({"fixture_id":fixture['fixture_id']}, {"$set": fixture})

  return "fixture updated"

@app.route('/save_teams', methods=['GET'])
def save_teams():
  url = "https://api-football-v1.p.rapidapi.com/v2/teams/league/524"
  response = rapid_api_call(url)
  collection = db["teams"]
  #print(response)
  for team in response['api']['teams']:
    if collection.find_one({"team_id":team['team_id']}) == None:
      collection.insert_one(team)
    else:
      collection.find_one_and_update({"team_id":team['team_id']}, {"$set": team})
  return "Done"

@app.route('/save_team', methods=['GET'])
def save_team():
  collection = db["teams"]
  for team_collection in collection.find():
    team_id = team_collection['team_id']
    url = f"https://api-football-v1.p.rapidapi.com/v2/teams/team/{team_id}"
    response = rapid_api_call(url)
    for team in response['api']['teams']:
        collection.find_one_and_update({"team_id":team_id}, {"$set": team})
  return "done"

## Issue is that most of the teams don't have a code via rapidapi.. Need to manually create a dict

def get_fpl_team_data(team_id):
  collection = db["teams"]
  if collection.find_one({"team_id":int(team_id)}):
    team = collection.find_one({"team_id":team_id})
    return team['code'], team['logo']

if __name__ == '__main__':
    app.run()
