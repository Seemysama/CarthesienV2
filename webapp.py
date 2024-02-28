import json
import requests
from pymongo import MongoClient
import pymongo
import sys
from utils.__init__ import __init__
from utils.scrapUtils import ScrapUtils



def get_database():
    MONGO_CONNEXION = "mongodb+srv://axel_toussenel:AxelAdmin92@car-thesiendb.sey3qsk.mongodb.net/"
    client = MongoClient(MONGO_CONNEXION)
    return(client)


#EXECUTION GLOBALE
URL = 'https://www.aramisauto.com/achat/occasion?types%5B0%5D=VO'
scrap = ScrapUtils(URL)

print("-----------------------------MONGO CONNEXION-----------------------------")
client=get_database()
database = client["Projet_Ydays"]
collection = database["scrap_2024"]

print("------------------------SCRAPPING & BASE INSERTION-----------------------")
#scrap.main_scrap()
try:
    with open('exports/car_data.json', 'r') as jsonfile :
        car_data = json.load(jsonfile)
    collection.insert_many(car_data)
    print('Insertion effectuée')
    count = collection.count_documents({})
    print('Nombre de documents en base:')
    print(count)
except pymongo.errors.ConnectionFailure as e:
    print('Insertion échouée.  --> ', e)
