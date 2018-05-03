#from nba_py import player
from selenium import webdriver
from bs4 import BeautifulSoup
import pandas as pd
import os
from string import ascii_lowercase
import cPickle as pickle
import csv
import re
from datetime import timedelta as td
import dill


player_base_url = 'https://www.basketball-reference.com/players/'


def getPlayerURLdict(new=False):
    if new==True:
        all_names = dict()
        chromedriver = os.path.expanduser('~/Downloads/chromedriver')
        driver = webdriver.Chrome(chromedriver)

        for letter in ascii_lowercase:
            letter_url = player_base_url+letter

            driver.get(letter_url)
            htmlSource = driver.page_source
            soup = BeautifulSoup(htmlSource, 'html.parser')
            current_names = soup.findAll('strong')
            names = []
            for i, n in enumerate(current_names):
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
        driver.close()
    else:
        reader=  csv.reader(open('playerURL.csv', 'r'))
        d = {}
        for row in reader:
            k, v = row
            d[k] = v
        return d




team_base_url = 'https://www.basketball-reference.com/teams/'


def getTeamURLdict(new=False):
    if new==True:
        all_names = dict()
        chromedriver = os.path.expanduser('~/Downloads/chromedriver')
        driver = webdriver.Chrome(chromedriver)

        driver.get(team_base_url)
        htmlSource = driver.page_source
        soup = BeautifulSoup(htmlSource, 'html.parser')

        divs = soup.findAll('div', attrs={'class': 'overthrow table_container', 'id': 'div_teams_active'})
        all_teams = [ [{team.get_text():team['href']} for team in div.findAll('a',href=True)] for div in  divs  ]


        with open('teamURL.csv', 'wb') as output:
            writer = csv.writer(output)
            for each in all_teams[0]:
                for key, value in each.iteritems():
                    full_link='http://www.basketball-reference.com'+value
                    writer.writerow([key, full_link])

        driver.close()
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

def getTeamSchedule(team,season):
    teamscheduleURL='https://www.basketball-reference.com/teams/'+team+'/'+str(season)+'_games.html'
    chromedriver = os.path.expanduser('~/Downloads/chromedriver')
    driver = webdriver.Chrome(chromedriver)
    driver.get(teamscheduleURL)
    htmlSource = driver.page_source
    soup = BeautifulSoup(htmlSource, 'html.parser')
    table = soup.find('div', class_="overthrow table_container", id="div_games")
    df = pd.read_html(table.prettify())[0]
    df = df[df.G != 'G']

    filename= 'TeamSchedules/'+str(season)+'/'+team+'.csv'
    df.to_csv(filename)
    driver.close()
    return df


class player_scraper():
    def __init__(self,playerName):
        self.playerName=playerName
        self.game_log, self.pic, self.team = self.getPlayerData()

    def getPlayerData(self):
        #filename = 'PlayerGameLogs/'+self.playerName.replace(" ", "") + '_' + str(self.season) + 'GameLog.csv'

        playerURLdict = getPlayerURLdict()
        playerURL = playerURLdict[self.playerName]
        chromedriver = os.path.expanduser('~/Downloads/chromedriver')
        driver = webdriver.Chrome(chromedriver)
        url = playerURL
        url = re.sub('\.html$', '', url)

        seasons=[str(i) for i in xrange(2018,2019,1)]
        game_log = dict()
        for season in seasons:

            playerGameLogURL = url+'/gamelog/'+season+'/'
            driver.get(playerGameLogURL)
            htmlSource = driver.page_source
            soup = BeautifulSoup(htmlSource, 'html.parser')

            # Game Logs
            table = soup.find('div', class_="overthrow table_container", id="div_pgl_basic")
            df = pd.read_html(table.prettify())[0]
            df = df[ (pd.notnull(df['G'])) & (df['G']!='G') ]

            df = addhomeaway(df)
            df = addDaysRest(df)

            game_log[season]=df

        # Player profile pic
        pic = soup.find('img', itemscope="image")
        pic_url = str(pic['src'])

        # Team
        team = str(df['Tm'].unique()[0])

        driver.close()

        return game_log, pic_url, team



class team_scraper():
    def __init__(self,teamName):
        self.teamName=teamName
        self.game_log, self.pic, self.roster= self.getTeamData()

    def getTeamData(self):
        #filename = 'PlayerGameLogs/'+self.playerName.replace(" ", "") + '_' + str(self.season) + 'GameLog.csv'

        teamURLdict = getTeamURLdict()
        teamURL = teamURLdict[self.teamName]
        chromedriver = os.path.expanduser('~/Downloads/chromedriver')
        driver = webdriver.Chrome(chromedriver)
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

            driver.get(teamGameLogURL)
            htmlSource = driver.page_source
            soup = BeautifulSoup(htmlSource, 'html.parser')

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

        driver.close()
        return game_log, pic_url, roster


if __name__=="__main__":
    new=True

    team = 'Utah Jazz'
    teampkl_source = 'pkl_obj/' + team.replace(" ", "") + '.dill'
    if new==True:
        obj = team_scraper(team)
        dill.dump(obj, open(teampkl_source, 'w'))
    else:
        obj = dill.load(open(teampkl_source, 'r'))

    '''
    playerName='Damian Lillard'

    pkl_source = 'pkl_obj/'+playerName.replace(" ","") + '.dill'
    if new==True:

        obj = player_scraper(playerName)
        dill.dump(obj, open(pkl_source, 'w'))
    else:
        obj = dill.load(open(pkl_source, 'r'))
    '''

    #df = addDaysRest(obj.df)
    #print addhomeaway(df)

    #getTeamSchedule(team,season)




