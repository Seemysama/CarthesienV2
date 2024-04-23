import pandas as pd
from pymongo import MongoClient
import pandas as pd
from fuzzywuzzy import fuzz
from sklearn.preprocessing import OrdinalEncoder, LabelEncoder
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import numpy as np
from joblib import load


class MlUtils():

    def __init__(self, db_name):
        self.db_name = db_name

    # Function to fetch data from MongoDB collection and convert to DataFrame
    def buildDataset(self, collection_name):
        # Establish a connection to the MongoDB server
        MONGO_CONNEXION = "mongodb+srv://axel_toussenel:AxelAdmin92@car-thesiendb.sey3qsk.mongodb.net/"
        client = MongoClient(MONGO_CONNEXION)

        # Access the specified database and collection
        db = client[self.db_name]
        collection = db[collection_name]

        # Fetch data from MongoDB collection
        cursor = collection.find({})

        # Convert data to DataFrame
        df = pd.DataFrame(list(cursor))

        # Close the MongoDB connection
        client.close()
        return df

    def merge_dataframes(self, df1, df2):
        # Nettoyage des colonnes Title_name et Title_Note du dataset note
        df1['Title_name'] = df1['Title_name'].str.replace('AVIS', '')
        df1['Title_Note'] = df1['Title_Note'].str.replace('/20', '')

        # Création des colonnes marque et modèle sur à partir de la colonne Title_name du dataset note
        df1['Marque'] = df1['Title_name'].str.split().str[0]
        df1['Modele'] = df1['Title_name'].str.split().str[1:].apply(' '.join)

        # Restructuration du dataset Note
        df1 = df1[['Marque', 'Modele', 'Title_Note']]

        # Définition des seuils de similarité
        threshold_model = 50
        threshold_brand = 100

        # Fonction pour trouver les correspondances entre les deux DataFrames
        def find_matches(row1, df):
            for index, row2 in df.iterrows():
                similarity_model = fuzz.ratio(row1['Modele'].lower(), row2['Modele'].lower())
                similarity_brand = fuzz.ratio(row1['Marque'].lower(), row2['Marque'].lower())
                if similarity_model >= threshold_model and similarity_brand == threshold_brand:
                    return row2['Title_Note']
            return None

        # Ajouter la colonne "note" de df2 à df1
        df2['Note'] = df2.apply(find_matches, args=(df1,), axis=1)

        # Filtrer les lignes avec des valeurs nulles dans la colonne "note" de df2 et les déplacer dans un autre Dataset pour constituer un stock de données pour la validation
        df_test = df2[df2['Note'].isnull()].copy()
        df_test = df_test.drop(columns="Note", axis=1)

        # Suppression des lignes avec des valeurs nulles dans la colonne "note" de df2
        df2.dropna(subset=['Note'], inplace=True)

        # Nettoyage des colonnes Crit'air et Options et suppression des lignes vides
        df2["Crit'air"] =  df2["Crit'air"].replace('', '0')
        df2["Options"] =  df2["Options"].replace('', '0')
        df2 = df2.replace('', pd.NA).dropna()

        # Nettoyage des colonnes Crit'air et Options et suppression des lignes vides
        df_test["Crit'air"] =  df_test["Crit'air"].replace('', '0')
        df_test["Options"] =  df_test["Options"].replace('', '0')
        df_test = df_test.replace('', pd.NA).dropna()

        # Establish a connection to the MongoDB server
        MONGO_CONNEXION = "mongodb+srv://axel_toussenel:AxelAdmin92@car-thesiendb.sey3qsk.mongodb.net/"
        client = MongoClient(MONGO_CONNEXION)

        # Access the specified database and collection
        db = client["Projet_Ydays"]
        collection = db["collection_name"]

        # Ajouter le dataset df2 avec les notes rajoutés au database
        db["Voiture_noté"].insert_many(df2.to_dict('records'))

        client.close()
        return df1, df2, df_test


    def preprocess_data(self, dfX):
        # Encoder la marque et le modèle séparément
        X = pd.json_normalize(dfX)
        X.rename(columns={'Sous_titre': 'Sous-titre'}, inplace=True)
        X.rename(columns={'Crit_air': 'Crit\'air'}, inplace=True)
        ordinal_encoder = OrdinalEncoder()
        if not X.empty:
            X[['Marque']] = ordinal_encoder.fit_transform(X[['Marque']])
            X[['Modele']] = ordinal_encoder.fit_transform(X[['Modele']])
            X[['Sous-titre']] = ordinal_encoder.fit_transform(X[['Sous-titre']])

        
        # Map options to their corresponding numeric values
        def map_options(item):
            options_mapping = {
                '7 places': 3,
                'Radar arriere': 3,
                'Attelage': 2,
                'Essuie-glaces automatiques': 1,
                'Apple Car Play': 3,
                'Regulateur': 3,
                'Sieges chauffants': 4,
                'Radar de recul': 2,
                'Radar avant': 3,
                'Toit ouvrant/panoramique': 5,
                'Phares automatiques': 2,
                'Prise audio USB': 1,
                'Interieur cuir': 3,
                'Android Auto': 3,
                '4 roues motrices (4x4)': 4,
                'Camera de recul': 2,
                'Affichage tete haute': 5,
                'GPS': 2,
                'Regulateur de vitesse': 2,
                'Jantes alliage': 3,
                'Climatisation': 1,
                'Bluetooth': 2,
                'Toit ouvrant': 5
            }
            return options_mapping.get(item, 0)  # Default to 0 if item not found in mapping

        # Apply mapping function to the 'Options' column
        X['Options'] = X['Options'].apply(lambda x: [map_options(item) for item in x])

        # Convert the 'Options' column to a single list without commas
        X['Options'] = X['Options'].apply(lambda x: ''.join(map(str, x)))

        # Convert the values in the 'Options' column to floating point numbers
        X['Options'] = pd.to_numeric(X['Options'], errors='coerce')

        # Replace NaN values with 0
        X['Options'].fillna(0, inplace=True)

        # Remove the 'Lien' and 'Image' columns if present
        X.drop(['Lien', 'Image'], axis=1, inplace=True, errors='ignore')

        # Convert 'Prix', 'Annee', 'Crit\'air', 'Kms', 'Options' columns to float and int types
        X['Prix'] = X['Prix'].str.replace(',', '.').astype(float)
        X['Annee'] = X['Annee'].astype(float)
        X['Crit\'air'] = X['Crit\'air'].fillna(0)
        X['Crit\'air'] = X['Crit\'air'].astype(int)
        X['Kms'] = X['Kms'].str.replace(',', '.').astype(float)
        X['Options'] = X['Options'].astype(int)

        # Apply LabelEncoder to 'Motorisation' and 'Carburant' columns
        object_cols = X.select_dtypes(include='object').columns
        label_encoder = LabelEncoder()
        X[object_cols] = X[object_cols].apply(label_encoder.fit_transform)

        # Replace NaN values with the mean of numerical columns
        X.fillna(X.mean(), inplace=True)

        # Remove rows containing NaN values
        X.dropna(axis=0, inplace=True)

        return X  




    def train_test_rf(self, X, y):


        # Séparation des données en ensemble d'entraînement et ensemble de test
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Définir les hyperparamètres à tester dans GridSearchCV
        param_des_grid = {
            'n_estimators': [100, 200, 300],
            'max_depth': [None, 10, 20],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        }

        # Instancier le modèle RandomForestRegressor
        rf_model = RandomForestRegressor(random_state=42)

        # Instancier l'objet GridSearchCV
        grid_search = GridSearchCV(estimator=rf_model, param_grid=param_des_grid, cv=5, scoring='neg_mean_squared_error')

        # Exécuter la recherche sur grille pour trouver les meilleurs hyperparamètres
        grid_search.fit(X_train, y_train)

        # Utiliser le modèle avec les meilleurs hyperparamètres pour faire des prédictions sur l'ensemble de test
        best_rf_model = grid_search.best_estimator_

        # Prédire la classe test pour évaluer le modèle
        y_pred = best_rf_model.predict(X_test)

        # Évaluer les performances du modèle sur l'ensemble de test
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        print("Mean Squared Error (MSE) sur l'ensemble de test:", mse)
        print("Root Mean Squared Error (RMSE):", rmse)
        print("Mean Absolute Error (MAE):", mae)
        print("Coefficient de détermination (R²):", r2)

        # Plot des vraies valeurs vs prédictions
        plt.figure(figsize=(10, 6))
        plt.scatter(y_test, y_pred, color='blue', label='Vraies valeurs vs Prédictions')
        plt.plot([min(y_test), max(y_test)], [min(y_test), max(y_test)], color='red', linestyle='--', label='Ligne d\'égalité')
        plt.title('Scatter Plot des Vraies Valeurs vs Prédictions (Random Forest)')
        plt.xlabel('Vraies Valeurs')
        plt.ylabel('Prédictions')
        plt.legend()
        plt.grid(True)
        plt.show()

        return best_rf_model, (mse, rmse, mae, r2)

    def predict_notes(self, df, model_name):
        dfTest = pd.DataFrame(df)
        # Appliquer le prétraitement à df
        mlu = MlUtils(self.db_name)
        df_preprocessed = mlu.preprocess_data(df)
        df_preprocessed = df_preprocessed.reset_index()
        df_preprocessed = df_preprocessed.rename(columns={'index': '_id'})

        model_tuple = load(model_name)
        model = model_tuple[0]

        df_dict = dfTest.to_dict(orient='records')
        # Prédire les notes sur df_preprocessed
        print(type(model))
        print(model)
        notes_predites = model.predict(df_preprocessed)

        # Ajouter les notes prédites au df original
        dfTest['Note_predite'] = notes_predites.round(2)
        
        return dfTest
