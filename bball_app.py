from flask import Flask, render_template, request, redirect
from nba_stats import player_scraper, team_scraper
import numpy as np
import pandas as pd
import datetime as dt
import dill

app = Flask(__name__)

cats = [u'FG', u'FGA',  u'3P',
       u'3PA',  u'FT', u'FTA', u'TRB', u'AST',
       u'STL', u'BLK', u'TOV', u'PTS']

sorted_cats = [u'FG', u'FGA',  'FG%', u'3P',
       u'3PA',  u'FT', u'FTA', 'FT%',u'TRB', u'AST',
       u'STL', u'BLK', u'TOV', u'PTS']

features = ['G', #game number
			'daysRest',
			'Away', #1=away, 0=home
			#'oppdaysRest','oppAway',
			#'oppRating',
			#'injTeammates',
			#'injOpp'
			]

def get_data(playerName):
	try:
		pkl_source = 'pkl_obj/' + playerName.replace(" ", "") + '.dill'
		a = dill.load(open(pkl_source, 'r'))
	except:
		a=player_scraper(playerName)
	return a

def get_teamdata(teamName):
	try:
		pkl_source = 'pkl_obj/' + teamName.replace(" ", "") + '.dill'
		a = dill.load(open(pkl_source, 'r'))
	except:
		a=team_scraper(teamName)
	return a

def getOpponent(team, date_input,season=2018):

	filename = 'TeamSchedules/'+str(season)+'/'+team+'.csv'
	df = pd.read_csv(filename,index_col='Date',infer_datetime_format=True)
	#pr dt.datetime.strptime(df['Date'],
	df.index = [dt.datetime.strptime(date, '%a, %b %d, %Y') for date in df.index]

	if df.loc[date_input,'Unnamed: 5']=='@':
		away=1
	else:
		away=0

	oppteam = df.loc[date_input,'Opponent']

	oppobj = get_teamdata(oppteam)
	pic_opp=oppobj.pic

	return df.loc[date_input,'Opponent'], away, pic_opp


def analyzer(data, date):
	A = make_Amatrix(data) # machine learning output / crux of project, will A be different for every player?
	b = get_bvector(data) # some combination of averages (season-long, past 14 days...)
	x = get_xvector(date)#  e.g. days rest, game number, home/away

	return b

def make_Amatrix(data):
	return np.matrix( np.zeros(( len(cats),len(features)  )))

def get_bvector(data):
	s=pd.Series(index=cats)


	s[cats]=[data[cat].astype('float64').mean() for cat in cats]


	s['FG%'] = s['FG']/s['FGA']*100.
	s['FT%'] = s['FT'] / s['FTA']*100.

	for cat in s.index:
		s[cat] = float("{0:.1f}".format(s[cat]))

	return s[sorted_cats]

def get_xvector(date):


	return np.matrix( np.zeros(( len(features),1  )))



@app.route('/')
def hello():
    return redirect('/index')

@app.route('/index', methods=['GET','POST'])
def index():
	if request.method == 'GET':
		return render_template('index.html')
	else:
		playerName=request.form['playername']
		date=request.form['date']

		obj=get_data(playerName)
		playerpicURL=obj.pic
		data=obj.game_log['2018']
		team = obj.team
		opponent, away, oppPic = getOpponent(team,date)
		results = analyzer(data, date)



		return render_template('results.html', results=results,playerName=playerName,
							   date=date,opponent=opponent, away=away, playerpicURL=playerpicURL,oppPic=oppPic)


@app.route('/about', methods=['GET','POST'])
def about():
	if request.method == 'GET':
		return render_template('about.html')



if __name__ == '__main__':
	app.run(port=5003,debug=True)
	playerName='Damian Lillard'
	obj=get_data(playerName)
	data=obj.game_log['2018']

	team=obj.team
	date='4/7/18'
