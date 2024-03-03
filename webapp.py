from utils.__init__ import __init__
from utils.scrapUtils import ScrapUtils
from utils.dbUtils import DbUtils
from utils.jsonUtils import JsonUtils



#VARIABLES GLOBALES
URL = 'https://www.aramisauto.com/achat/occasion'
DB_PROJET = "Projet_Ydays"
CAR_DATA_COLLECTION = "scrap_2024"
CAR_DATA_FILE = "car_data.json"

scrap = ScrapUtils(URL)
dbu = DbUtils(DB_PROJET,CAR_DATA_COLLECTION,CAR_DATA_FILE)
jsonfile = JsonUtils(CAR_DATA_FILE)

#EXECUTION GLOBALE
scrap.scrape_multiple_pages(25)
jsonfile.remove_empty_objects()
jsonfile.clean_json()
dbu.db_insert()