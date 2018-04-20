from flask import Flask, render_template, request, redirect, jsonify
from nba_stats import player_scraper, team_scraper, getTeamURLdict
import numpy as np
import pandas as pd
import datetime as dt
import dill


from bokeh.embed import components
from bokeh.models.widgets import DataTable, DateFormatter, TableColumn
from bokeh.transform import factor_cmap
from bokeh.io import show, output_notebook, curdoc
from bokeh.models import ColumnDataSource, Whisker
from bokeh.plotting import figure
import bokeh.layouts as layouts
import bokeh.models.widgets as widgets
from bokeh.resources import INLINE


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


def analyzer(obj, date, season='2018'):
    data=obj.game_log[season]
    inputdate_datetime=dt.datetime.strptime(date,'%m/%d/%y')
    formatted_date=dt.datetime.strptime(date, '%m/%d/%y').strftime('%Y-%m-%d')

    
    feature_inputs = data[features][data['Date']==formatted_date].values #  e.g. days rest, game number, home/away
    
    
    cols=['Season Average','Predictions']
    
    
    results=pd.DataFrame(index=cats, columns=cols)
    if inputdate_datetime<dt.datetime.now():
        
        actual_results=data[cats][data['Date']==formatted_date].squeeze() 
        results['Actual'] = actual_results.astype('float')
        
    dummyReg=obj.models['2018']['dummyReg']
    RFG=obj.models['2018']['RFG']
    for cat in cats:
        results.loc[cat,'Season Average']= dummyReg[cat].predict(feature_inputs)[0]
        results.loc[cat,'Predictions']= RFG[cat].predict(feature_inputs)[0]
    
    

    # Calculate percentages
    results.loc['FG%',:]=results.loc['FG',:].divide(results.loc['FGA',:])*100.
    results.loc['FT%',:]=results.loc['FT',:].divide(results.loc['FTA',:])*100.

    
    # data formatting - sig figs
    results=results.applymap(lambda x: '{:.1f}'.format(x))

    if 'Actual' in results:
        results['Actual']=results['Actual'].astype('float').map(lambda x: '{:.0f}'.format(x))


    
    # sort results by desired category order
    results=results.reindex(sorted_cats)
    #[tuple(i) for i in results.itertuples()]
    
    return results, feature_inputs


def create_bokehtable(results):
    results.index.name='Category'
    results=results.reset_index()

    data = dict(results[results.columns])
    source=ColumnDataSource(data)

    columns = [TableColumn(field=col, title=col) for col in results.columns]

    data_table = DataTable(source=source,columns=columns,width=400, height=280,selectable=True)
    data_table.row_headers = False
    return data_table


    

def create_featureimp_plot(obj, cat='PTS'):

    RFG=obj.models['2018']['RFG'][cat]
    features=['Game Number','Days Rest','Home/Away']
    groups= features
    counts = RFG.feature_importances_

    chart_data = ColumnDataSource(data=dict(groups=groups, counts=counts))

    p = figure(x_range=groups, plot_height=500, toolbar_location=None, title="Feature Importance - "+cat, y_range=(0,1.1))
    
    p.vbar(x='groups', top='counts', width=0.9, source=chart_data, 
           line_color='white', fill_color=factor_cmap('groups', palette=["#962980","#295f96","#29966c"],
                                                      factors=groups))

    
    p.xgrid.grid_line_color = None
    p.title.text_font_size = '18pt'
    p.xaxis.major_label_text_font_size = '15pt'
    p.yaxis.major_label_text_font_size = '15pt'
    
    return p

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
		playerpicURL=obj.pic_url
		data=obj.game_log['2018']
		team = obj.team
		opponent, away, oppPic = getOpponent(team,date)
        
		results, feature_inputs = analyzer(obj, date)
        
        
        
        # Create feature importance plot with Bokeh
        feature_imp_plot = create_featureimp_plot(obj)
        
        # get bokeh components 
        #script, div_dict = components({"plot": feature_imp_plot})

        # import js, css resources to properly format and render bokeh elements
        #js_resources = INLINE.render_js()
        #css_resources = INLINE.render_css()
        teamURLdict = getTeamURLdict()
        fullteamName=[k for k, v in teamURLdict.iteritems() if team in v][0]
        
        div_dict={'opponent':opponent, 'playerName':playerName, 'date':date, 'playerpicURL':playerpicURL, 'oppPic':oppPic, 
                 'teamName':fullteamName,'age':obj.age,'position':obj.position, 'weight':obj.weight, 'height':obj.height}
        
        
        #return render_template('results.html', data_table=results.to_html(classes='table-hover'), 
        #                       features=feature_inputs,playerName=playerName,date=date,opponent=opponent, 
        #                       away=away, playerpicURL=playerpicURL, oppPic=oppPic,div_dict=div_dict)
    
    
        return render_template('results.html', data_table=results.to_html(classes='table-hover'), 
                               features=feature_inputs, div_dict=div_dict)


@app.route('/plot',methods=['POST'])
def plot():
    params= request.form.to_dict()
    playerName=params['playername']
    date=params['date']
    cat=params['cat']

    obj=get_data(playerName)
    
    feature_imp_plot = create_featureimp_plot(obj,cat)
    script, div = components(feature_imp_plot)
    
    
    return jsonify({'script':script,'div': div})
    

    
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
