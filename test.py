import flask
import requests, json
from fpl import FPL


session = requests.session()

url = 'https://users.premierleague.com/accounts/login/'
payload = {
 'password': "",
 'login': "jackculpan@me.com",
 'redirect_uri': 'https://fantasy.premierleague.com/a/login',
 'app': 'plfpl-web'
}
session.post(url, data=payload)

team_info = session.get(f'https://fantasy.premierleague.com/api/my-team/502162/').json()

print(team_info)
