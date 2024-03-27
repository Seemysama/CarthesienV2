from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient

app = Flask(__name__)
CORS(app)

# Connect to MongoDB
client = MongoClient('mongodb+srv://axel_toussenel:AxelAdmin92@car-thesiendb.sey3qsk.mongodb.net/Projet_Ydays?retryWrites=true&w=majority&appName=Car-thesienDB')
db = client['Projet_Ydays']
collection = db['scrap_2024']

@app.route('/api/data', methods=['GET'])
def get_data():
    data = list(collection.find({}, {'_id': False}))  # Replace 'data' with your collection name
    return jsonify(data)

@app.route("/api/formulaire", methods=["POST"])
def formulaire():
    data = request.get_json()
    marque = data["marque"]
    modele = data["modele"]
    prix = data["prix"]
    motorisation = data["motorisation"]
    carburant = data["carburant"]
    annee = data["annee"]
    kms = data["kms"]
    options = data["options"]
    print(marque, modele, prix, motorisation, carburant, annee, kms, options)
    return {"success": True}

@app.route("/api/classification", methods=["POST"])
def classification():
    data = request.get_json()
    classification = 0
    return classification

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3030)
