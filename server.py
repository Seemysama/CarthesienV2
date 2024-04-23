from joblib import load
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from utils.dbUtils import DbUtils
from utils.mlUtils import MlUtils
from bson.objectid import ObjectId
from sklearn.pipeline import Pipeline
from joblib import dump



app = Flask(__name__)
CORS(app)

DB_PROJET = "Projet_Ydays"
CAR_DATA_COLLECTION_NOTE = "Voiture_noté"
CAR_DATA_COLLECTION_SCRAP = "scrap_2024"
CAR_DATA_FILE = ""


dbu = DbUtils(DB_PROJET,CAR_DATA_COLLECTION_NOTE,CAR_DATA_FILE)
dbu2 = DbUtils(DB_PROJET,CAR_DATA_COLLECTION_SCRAP,CAR_DATA_FILE)
mlu = MlUtils(DB_PROJET)

#GET toutes les voitures de la collection
@app.route('/api/data', methods=['GET'])
def get_data():
    collection = dbu.db_connexion()
    data = list(collection.find({}))
    for item in data:
        item['_id'] = str(item['_id'])
    return jsonify(data)

#POST une voiture dans l'algorithme de classification
@app.route("/carform", methods=["POST"])
def formulaire():
    data = request.get_json()

    print("prediction des notes")
    notes_predites = mlu.predict_notes(data, 'model.joblib')
    notes_predites_dict = notes_predites.to_dict(orient='records')
    print(notes_predites_dict)
    note_predite = notes_predites_dict[0]['Note_predite']
    note_predite_dict = {'Note_predite': note_predite}
    return jsonify(note_predite_dict)

#GET une voiture par son id
@app.route('/cars/<id>', methods=['GET'])
def get_car(id):
    print('get')
    collection = dbu.db_connexion()
    car = collection.find_one({'_id': ObjectId(id)})
    if car:
        car['_id'] = str(car['_id']) # Convertie ObjectId en string
        print(car)
        return jsonify(car)
    else:
        return jsonify({'error': 'Car not found'}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3030)
