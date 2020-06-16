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
    fixture['fixture_id'] = fixture_id
    if collection.find_one({"fixture_id":fixture_id}) == None:
      collection.insert_one(fixture)
    else:
      collection.find_one_and_update({"fixture_id":fixture['fixture_id']}, {"$set": fixture})

  return "fixture updated"


if __name__ == '__main__':
    app.run()
