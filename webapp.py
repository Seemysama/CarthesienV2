import json
import requests
from pymongo import MongoClient
import sys
from .utils.scrapUtils import ScrapUtils





scrap = ScrapUtils('https://www.aramisauto.com/achat/occasion?types%5B0%5D=VO')

client = MongoClient("localhost", 27017, "scrap_2024")
collection = client.Projet_Ydays.scrap_2024

scrap.main_scrap()

collection.insert_many('exports/car_data.json')

count = collection.count_documents({})
print('Nombre de documents en base : '+count)