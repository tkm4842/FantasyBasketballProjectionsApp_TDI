
from bs4 import BeautifulSoup
from collections import OrderedDict
import cPickle as pickle
import csv
import datetime as dt
from datetime import timedelta as td
import dill
import os
import pandas as pd
import re
import requests
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestRegressor
from string import ascii_lowercase

pd.options.mode.chained_assignment = None
def getPlayerURLdict(new=False):
    player_base_url = 'https://www.basketball-reference.com/players/'
    if new==True:
        all_names = dict()
        for letter in ascii_lowercase:
            letter_url = player_base_url+letter
            page = requests.get(letter_url)
            soup = BeautifulSoup(page.content, 'html.parser')
            current_names = soup.findAll('strong')
            names = []
            for _, n in enumerate(current_names):
                name_data = n.children.next()
                try:
                    names.append((name_data.contents[0], 'http://www.basketball-reference.com' + name_data.attrs['href']))
                except Exception as e:
                    pass
            player_dict = dict(names)

            all_names.update(player_dict)
        w = csv.writer(open("playerURL.csv", "w"))
        for key, val in all_names.items():
            w.writerow([key, val])
        return all_names
        
    else:
        reader=  csv.reader(open('playerURL.csv', 'r'))
        d = {}
        for row in reader:
            k, v = row
            d[k] = v
        return d



def getTeamURLdict(new=False):  
    if new==True:
        all_names = dict()
        team_base_url = 'https://www.basketball-reference.com/teams/'
        page = requests.get(team_base_url)
        soup = BeautifulSoup(page.content, 'html.parser')
        divs = soup.findAll('div', attrs={'class': 'overthrow table_container', 'id': 'div_teams_active'})
        all_teams = [ [{team.get_text():team['href']} for team in div.findAll('a',href=True)] for div in  divs  ]
        exception_teams={'Charlotte Hornets':'CHO','Brooklyn Nets':'BRK','New Orleans Pelicans':'NOP'}
        with open('teamURL.csv', 'wb') as output:
            writer = csv.writer(output)
            for each in all_teams[0]:
                for key, value in each.iteritems():
                    if key in exception_teams:
                        value='/teams/'+exception_teams[key]+'/'
                    full_link=value
                    writer.writerow([key, full_link])

    else:
        reader=  csv.reader(open('teamURL.csv', 'r'))
        d = {}
        for row in reader:
            k, v = row
            d[k] = v
        return d



def getURL(playerName):
    lastnameletter = playerName.split(' ')[1][0].lower()
    url = player_base_url+lastnameletter
    return url

def addhomeaway(df):
    df['Away']=0
    if 'Home/Away' in df.columns:
        df['Away'][df['Home/Away'] == '@'] = 1
    else:
        df['Away'][df['Unnamed: 5']=='@']=1
    return df

def addDaysRest(df):
    df=df.reset_index()
    for i, row in df.iterrows():
        if i==0:
            df.loc[i,'daysRest']=99
        else:
            date = pd.to_datetime(df.loc[i,'Date'])
            prevdate = pd.to_datetime(df.loc[i-1,'Date'])
            df.loc[i, 'daysRest'] = (date-prevdate).total_seconds()/(24*3600.)
    return df

def addTeamGameLog(df,season):
    # 3 letter team code
    team=str(df['Tm'].unique()[0])
    team_dict=getTeamURLdict()

    # convert to full team name to access pkl
    fullteam_name=[k for k,v in team_dict.iteritems() if team in v][0]
    teampkl_source = 'pkl_obj/' +fullteam_name.replace(" ", "") + '.dill'
    team_obj=dill.load(open(teampkl_source, 'r'))

    # get team game log
    teamlog=team_obj.game_log[season]

    # rename pts to be consistent with other columns
    team_log=teamlog.rename(columns={'Pts':'PTS'})
    cols = ['Rk','PTS','FG','FGA','3P','3PA','FT','FTA','TRB','AST','STL','BLK','TOV']

    # cats distinguised by _x for player, _y for team
    new_player_log=pd.merge(df, team_log[cols], on=['Rk'], how='left')

    # rename player cols to original i.e. drop _x
    new_player_log.columns=[col.replace('_x','') if '_x' in col else col for col in new_player_log.columns ]
    return new_player_log

def getTeamSchedule(team,season):
    teamscheduleURL='https://www.basketball-reference.com/teams/'+team+'/'+str(season)+'_games.html'
    page = requests.get(teamscheduleURL)
    soup = BeautifulSoup(page.content, 'html.parser')
    table = soup.find('div', class_="overthrow table_container", id="div_games")
    df = pd.read_html(table.prettify())[0]
    df = df[df.G != 'G']
    filename= 'TeamSchedules/'+str(season)+'/'+team+'.csv'
    df.to_csv(filename)
    return df


def getPlayerPosition(soup):
    line=[x.get_text() for x in soup.findAll('p') if 'Position' in x.get_text()][0]
    pos_dict = OrderedDict()
    pos_dict['Point Guard']='PG'
    pos_dict['Shooting Guard']='SG'
    pos_dict['Small Forward']='SF'
    pos_dict['Power Forward']='PF'
    pos_dict['Center']='C'

    p=''
    for pos in pos_dict:
        if pos in line:
            if p=='':
                p=pos_dict[pos]
            else:
                p+=', '+pos_dict[pos]
    return p        

class playerScraper():
    def __init__(self,playerName):
        self.playerName=playerName
        self.getPlayerData()

    def getPlayerData(self):
        playerURLdict = getPlayerURLdict()
        playerURL = playerURLdict[self.playerName]
        url = playerURL
        url = re.sub('\.html$', '', url)

        seasons=[str(i) for i in xrange(2018,2019,1)]
        game_log = dict()
        models = dict()
              
        for season in seasons:
            # Beautiful Soup on player gamelog html page
            playerGameLogURL = url+'/gamelog/'+season+'/'
            page = requests.get(playerGameLogURL)
            soup = BeautifulSoup(page.content, 'html.parser')    
            table = soup.find('div', class_="overthrow table_container", id="div_pgl_basic")
            
            # Game Logs
            df = pd.read_html(table.prettify())[0]
            df = df[ (pd.notnull(df['G'])) & (df['G']!='G') ]

            # Add attributes: home/away, days rest, team game log (cat allowed by opponent)
            df = addhomeaway(df)
            df = addDaysRest(df)
            df = addTeamGameLog(df, season)
            game_log[season]=df
            
            # Regression Models
            models[season] = addRegressionModels(df)

        self.game_log=game_log
        self.models=models
        
        # Player profile pic
        pic = soup.find('img', itemscope="image")
        self.pic_url = str(pic['src'])

        # Team
        self.team = str(df['Tm'].unique()[0])
        
        # Height, Weight, Age, position
        height=soup.find("span", itemprop="height")
        self.height=str(height.get_text())
        
        weight=soup.find("span", itemprop="weight")
        self.weight=str(weight.get_text())
        
        bdate=soup.find("span", itemprop="birthDate")['data-birth']
        self.age=str(int((dt.datetime.now()-dt.datetime.strptime(bdate,'%Y-%m-%d')).days/365.0))
        
        self.position=getPlayerPosition(soup)
        
        
        # Close driver
        #driver.close()
        


def addRegressionModels(data):
    cats= ['FG','FGA','3P','3PA','FT','FTA','TRB','AST','STL','BLK','TOV','PTS']
    features=['G','Away','daysRest'] # will include opponent rating by category when iterating through cats
    
    # Regression Models
    models=dict()
    models['dummyReg']=dict()
    models['RFG']=dict()
    for cat in cats:
        # add opponent rating per category
        temp_features=[] # clear everytime
        temp_features+=features
        temp_features.append(cat+'_y')

        # convert to numeric objects
        X=data[temp_features].apply(pd.to_numeric)
        yi=data[cat].apply(pd.to_numeric)

        ## Dummy Regressor to return season averages regardless of predictions
        dummyreg=DummyRegressor(strategy='mean')
        dummyreg.fit(X,yi)
        models['dummyReg'][cat]=dummyreg
        
        ## Random Forest Regressor
        ### may need to use grid search to optimize/tune hyperparameters
        RFG=RandomForestRegressor(min_samples_leaf=9)
        RFG.fit(X,yi)
        models['RFG'][cat]=RFG
    
    return models
    

class teamScraper():
    def __init__(self,teamName):
        self.teamName=teamName
        self.game_log, self.pic, self.roster= self.getTeamData()

    def getTeamData(self):
        #filename = 'PlayerGameLogs/'+self.playerName.replace(" ", "") + '_' + str(self.season) + 'GameLog.csv'

        teamURLdict = getTeamURLdict()
        teamURL = teamURLdict[self.teamName]
        url = 'https://www.basketball-reference.com'+teamURL
        #url = re.sub('\.html$', '', url)

        seasons=[str(i) for i in xrange(2013,2019,1)]
        seasons=['2018']
        game_log = dict()
        cols=['Rk',	'G'	,'Date'	, 'Home/Away', 'Opp','W/L','Pts','OppPts',
              'FG','FGA','FG%','3P','3PA','3P%','FT','FTA','FT%',
              'ORB','TRB','AST','STL','BLK','TOV','PF',
              'OppFG','OppFGA','OppFG%','Opp3P','Opp3PA','Opp3P%','OppFT','OppFTA','OppFT%',
              'OppORB','OppTRB',	'OppAST',	'OppSTL',	'OppBLK',	'OppTOV',	'OppPF']

        for season in seasons:
            teamGameLogURL = url+season+'/gamelog'
            print teamGameLogURL
            page = requests.get(teamGameLogURL)
            soup = BeautifulSoup(page.content, 'html.parser')    
            

            #soup = BeautifulSoup(htmlSource, 'html.parser')

            # Game Logs
            table = soup.find('div', class_="overthrow table_container", id="div_tgl_basic")
            
            df = pd.read_html(table.prettify())[0]
            df = df.dropna(axis=1, how='all')
            df.columns=cols
            df = df[ (pd.notnull(df['G'])) & (df['G']!='G') ]

            df = addhomeaway(df)
            df = addDaysRest(df)
            
            game_log[season]=df
            

        # Team profile pic
        pic = soup.find('img', class_="teamlogo")
        pic_url = str(pic['src'])


        # Roster
        roster=None

        #driver.close()
        return game_log, pic_url, roster


if __name__=="__main__":


    '''
    getTeamURLdict(True)
    new=True
    
    team_list = ['Brooklyn Nets']
    for team in team_list:
        teampkl_source = 'pkl_obj/' + team.replace(" ", "") + '.dill'
        if new==True:
            obj = teamScraper(team)
            dill.dump(obj, open(teampkl_source, 'w'))
        else:
            obj = dill.load(open(teampkl_source, 'r'))

    
    playerName='Damian Lillard'

    pkl_source = 'pkl_obj/'+playerName.replace(" ","") + '.dill'
    if new==True:
        obj = playerScraper(playerName)
        dill.dump(obj, open(pkl_source, 'w'))
    else:
        obj = dill.load(open(pkl_source, 'r'))
    
    print obj.height, obj.weight
    '''

    #df = addDaysRest(obj.df)
    #print addhomeaway(df)

    #getTeamSchedule(team,season)




