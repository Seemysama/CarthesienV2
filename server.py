from flask import Flask, jsonify
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3030)
