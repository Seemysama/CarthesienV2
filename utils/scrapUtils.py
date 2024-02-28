import json
import requests
from bs4 import BeautifulSoup



class ScrapUtils():

    def __init__(self, basic_url):
        self.basic_url = basic_url

    #fonction de scraping pour une page
    def scrape_page(soup):

        vehiculecards = soup.find_all(class_='vehicle-container')
        data_to_write = []

        for vehiculecard in vehiculecards:
            #TITRE
            try:
                title = vehiculecard.find(class_='vehicle-model').text
                print(title)
            except:
                title=''
            #SOUS-TITRE
            try:
                subtitle = vehiculecard.find(class_='vehicle-motorisation').text.strip()
            except:
                subtitle=''
            #IMAGE
            try:
                image_id = vehiculecard.find(class_='lazyload')
                img_id = image_id.get('data-picture')
                img_link = soup.find('img', {'data-picture': img_id})
                image_url = img_link.get('data-original')
            except:
                image_url=''
            #PRIX
            try:
                price = vehiculecard.find(class_='vehicle-loa-offer').text.strip()
                price = price.replace("€", "")
            except:
                price=''
            #MOTORISATION
            try:
                motorisation = vehiculecard.find(class_='vehicle-transmission').text.strip()
            except:
                motorisation=''
            #ANNEE KILOMETRAGE
            try:
                year_km = vehiculecard.find(class_='vehicle-zero-km').text.strip()
            except:
                year_km=''
            #LISTE D'OPTION
            try:
                option_list = []
                equipment_contents = vehiculecard.find_all(class_="equipment-tooltip-content")
                if equipment_contents:
                    for option in equipment_contents:
                        option_list.append(option.get_text(strip=True))
            except:
                option_list = []
            #LIEN
            try:
                link_container = vehiculecard.find(class_='real-link vehicle-info-link')
                link = link_container.get('href')
                link = "https://www.aramisauto.com" + link
            except:
                link = ''
            #CRIT'AIR
            try:
                response_article = requests.get(link)
                soup_article = BeautifulSoup(response_article.content, "html.parser")
                labels_bodies = soup_article.find_all(class_='labels-body')
                for labels_body in labels_bodies:
                    if "Crit'Air" in labels_body.get_text():
                        critair = labels_body.text.strip()
            except:
                critair = ''
                
            car_data = {
                "Titre": title,
                "Sous-titre": subtitle,
                "Image": image_url,
                "Prix": price,
                "Motorisation": motorisation,
                "Année/Kms": year_km,
                "Options": option_list,
                "Lien": link,
                "Crit'air": critair
            }
            data_to_write.append(car_data)
        with open("exports/car_data.json", "w") as json_file:
            json.dump(data_to_write, json_file, ensure_ascii=False, indent=4)


    #supprime les symboles étranges dans un objet json
    def remove_weird_symbols(text):
        return text.replace("�", "")


    #supprime les objets vides de l'export json
    def remove_empty_objects():
        print("Nettoyage des données ...")
        with open('exports/car_data.json', 'r') as file:
            data = json.load(file)
        cleaned_data = [item for item in data if item.get("Titre") != ""]
        with open('exports/car_data.json', 'w') as file:
            json.dump(cleaned_data, file, indent=4)


    #nettoie le fichier grâce à la fonction remove_weird_symbols
    def clean_json():
        with open("exports/car_data.json", "r", encoding="latin-1") as json_file:
            data = json.load(json_file)
        for objet in data:
            for key, value in objet.items():
                if isinstance(value, str):
                    objet[key] = ScrapUtils.remove_weird_symbols(value)
        with open("exports/car_data.json", "w", encoding="utf-8") as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)
    

    #scrape le nombre de pages voulu grâce à la fonction scrape_page
    def scrape_multiple_pages(base_url, num_pages):
        for page_num in range(1, num_pages + 1):
            num = str(page_num)
            print('Page n°'+num+' en cours ...')
            url = f'{base_url}?p={page_num}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
            }
            page = requests.get(url, headers=headers)
            soup = BeautifulSoup(page.text, 'html.parser')
            #Appel de la fonction de scraping pour chaque page
            ScrapUtils.scrape_page(soup)


    #fonction exécution globale
    def main_scrap(self):
        print("------------------------SCRAPPING & BASE INSERTION-----------------------")
        ScrapUtils.scrape_multiple_pages(self.basic_url,3)
        ScrapUtils.remove_empty_objects()
        ScrapUtils.clean_json()




    """
    LINKS :
    'https://www.aramisauto.com/achat/occasion?types%5B0%5D=VO'
    """
