import json


class JsonUtils():

    def __init__(self, file):
        self.file = file

    #supprime les symboles étranges dans un objet json
    def remove_weird_symbols(text):
        return text.replace("�", "")

    #supprime les objets vides de l'export json
    def remove_empty_objects(self):
        export_path = 'exports/'+self.file
        print("Nettoyage des données ...")
        with open(export_path, 'r') as file:
            data = json.load(file)
        cleaned_data = [item for item in data if item.get("Titre") != ""]
        with open(export_path, 'w') as file:
            json.dump(cleaned_data, file, indent=4)

    #nettoie le fichier grâce à la fonction remove_weird_symbols
    def clean_json(self):
        export_path = 'exports/'+self.file
        with open(export_path, "r", encoding="latin-1") as json_file:
            data = json.load(json_file)
        for objet in data:
            for key, value in objet.items():
                if isinstance(value, str):
                    objet[key] = JsonUtils.remove_weird_symbols(value)
        with open(export_path, "w", encoding="utf-8") as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)