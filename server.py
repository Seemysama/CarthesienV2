from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from utils.dbUtils import DbUtils
from utils.mlUtils import MLUtils
from bson.objectid import ObjectId

app = Flask(__name__)
CORS(app)

DB_PROJET = "Projet_Ydays"
CAR_DATA_COLLECTION = "Voiture_noté"
CAR_DATA_FILE = ""


dbu = DbUtils(DB_PROJET,CAR_DATA_COLLECTION,CAR_DATA_FILE)
mlu = MLUtils()

def classification(data):
    return data['Marque']

#GET toutes les voitures de la collection
@app.route('/api/data', methods=['GET'])
def get_data():
    collection = dbu.db_connexion()
    data = list(collection.find({}))
    for item in data:
        item['_id'] = str(item['_id'])
    return jsonify(data)

#POST une voiture dans l'algorithme de classification
@app.route("/car-form", methods=["POST"])
def formulaire():
    data = request.get_json()

    result = classification(data)
    print("Note estimée : ", result)
    return result

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
