import json
import pymongo
from pymongo import MongoClient


class DbUtils():

    def __init__(self, db, collection, file):
        self.db = db
        self.collection = collection
        self.file = file

    #récupération de la base de données
    def get_database():
        MONGO_CONNEXION = "mongodb+srv://axel_toussenel:AxelAdmin92@car-thesiendb.sey3qsk.mongodb.net/"
        client = MongoClient(MONGO_CONNEXION)
        return(client)
    
    #récupération de la collection
    def db_connexion(self):
        client=DbUtils.get_database()
        database = client[self.db]
        collection = database[self.collection]

        return collection

    #insertion de masse
    def db_insert_masse(self):
        collection = DbUtils.db_connexion(self.db, self.collection)
        file_to_insert = 'exports/'+self.file
        try:
            with open(file_to_insert, 'r') as jsonfile :
                car_data = json.load(jsonfile)
            collection.insert_many(car_data)
            print('Insertion effectuée')
            count = collection.count_documents({})
            print('Nombre de documents en base:')
            print(count)
        except pymongo.errors.ConnectionFailure as e:
            print('Insertion échouée.  --> ', e)

    #insertion d'un document
    def db_insert_detail(self, item):
        print("-----------------------------MONGO INSERTION-----------------------------")
        collection = DbUtils.db_connexion(self.db, self.collection)
        collection.insert_one(item)