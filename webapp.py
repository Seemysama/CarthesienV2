from utils.__init__ import __init__
from utils.scrapUtils import ScrapUtils
from utils.dbUtils import DbUtils




#VARIABLES GLOBALES
URL = 'https://www.aramisauto.com/achat/occasion'
DB_PROJET = "Projet_Ydays"
CAR_DATA_COLLECTION = "scrap_2024"
CAR_DATA_FILE = "car_data.json"

scrap = ScrapUtils(URL)
dbu = DbUtils(DB_PROJET,CAR_DATA_COLLECTION,CAR_DATA_FILE)

#EXECUTION GLOBALE
scrap.main_scrap(25)
dbu.db_insert()