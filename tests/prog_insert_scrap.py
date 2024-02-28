import pandas as pd
import csv 
from dateutil import parser
import json 
from pymongo import MongoClient 

#csvfile = open('data.tsv', 'r')
#reader = csv.DictReader( csvfile )

def get_database():
    CONNECTION_STRING="mongodb://127.0.0.1:27017/?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+1.6.1"
    client = MongoClient(CONNECTION_STRING)
    return(client)

def create_db_collection(client):
    db=client['Projet_Ydays']
    collection_name=db["all_caract_voiture"]
    return(collection_name)
client=get_database()
collection_name=create_db_collection(client)

csvfile = pd.read_csv("scrape_centrale.csv", sep=";", encoding = "ANSI")
reader = csv.DictReader( csvfile )

csvfile.replace('\\N', None, inplace = True)

#csvfile["Region"]= csvfile["Region"].str.split(";", expand = False)
#csvfile["PIB (milliards d'euros)"]= csvfile["PIB (milliards d'euros)"].str.split(";", expand = False)


header= [ "id","PRIX","Marque","MODELE","MOTEUR","ANNEE","CARBURANT","KILOMETRAGE","NoteConsommation","Fiabilite","DureeGarantie","Performance","CoteAttendue","Habitabilite"]
collection_name.create_index('id')
db=client['Projet_Ydays']
csvfile = csvfile.head(30000)
output=csvfile.to_dict('records')

#for each in reader:
    #row={}
    #for field in header:
        #row[field]=each[field]
    #output.append(row)

#firstline=output[0]

collection_name.insert_many(output)
print("Les données sont ajoutées !")