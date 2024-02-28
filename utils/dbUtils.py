import json
import pymongo
from pymongo import MongoClient




class DbUtils():

    
    def __init__(self, db, collection, file):
        self.db = db
        self.collection = collection
        self.file = file

    def get_database():
        MONGO_CONNEXION = "mongodb+srv://axel_toussenel:AxelAdmin92@car-thesiendb.sey3qsk.mongodb.net/"
        client = MongoClient(MONGO_CONNEXION)
        return(client)
    
    def db_connexion(db, collection):
        print("-----------------------------MONGO INSERTION-----------------------------")
        client=DbUtils.get_database()
        database = client[db]
        collection = database[collection]

        return collection

    def db_insert(self):
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