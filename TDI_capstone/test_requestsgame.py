import requests
from bs4 import BeautifulSoup
import pandas as pd
file_path='https://www.basketball-reference.com/players/l/lillada01/gamelog/2018'

page = requests.get(file_path)
soup = BeautifulSoup(page.content, 'html.parser')    

table = soup.find('div', class_="overthrow table_container", id="div_pgl_basic")
df = pd.read_html(table.prettify())[0]
print df