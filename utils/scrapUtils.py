import json
import requests
from bs4 import BeautifulSoup
import re



class ScrapUtils():

    def __init__(self, basic_url, num_pages):
        self.basic_url = basic_url
        self.num_pages = num_pages

    #fonction de scraping pour aramisauto pour une page
    def scrape_page_aramis(soup):

        vehiculecards = soup.find_all(class_='vehicle-container')
        data_to_write = []

        for vehiculecard in vehiculecards:
            #TITRE
            try:
                title = vehiculecard.find(class_='vehicle-model').text
                title = title.replace("é", "e")
                title = title.replace("è", "e")
                title = title.replace("ê", "e")
                title = title.replace("ë", "e")
                title = title.replace("ë", "e")
                title = title.replace("É", "E")
                title = title.replace("Ë", "E")
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
                price = price.replace(" ", "")
                price = price.replace("U+00a0", "")
                price = price.replace(" ", "")
            except:
                price=''
            #MOTORISATION & CARBURANT
            try:
                moto_carbu = vehiculecard.find(class_='vehicle-transmission').text.strip()
                motorisation = moto_carbu.split(' - ')[1]
                carburant = moto_carbu.split(' - ')[0]
            except:
                motorisation = ''
                carburant = ''
            #ANNEE & KILOMETRAGE
            try:
                year_km = vehiculecard.find(class_='vehicle-zero-km').text.strip()
                year=year_km[0:4]
                kms=year_km[8:-3]
                kms = kms.replace(" ", "")
            except:
                year=''
                kms=''
            #LISTE D'OPTION
            try:
                option_list = []
                equipment_contents = vehiculecard.find_all(class_="equipment-tooltip-content")
                if equipment_contents:
                    for option in equipment_contents:
                        option_txt = option.get_text(strip=True)
                        option_txt = option_txt.replace("é", "e")
                        option_txt = option_txt.replace("è", "e")
                        option_txt = option_txt.replace("ê", "e")
                        option_txt = option_txt.replace("ë", "e")
                        option_txt = option_txt.replace("É", "E")
                        option_txt = option_txt.replace("Ë", "E")
                        option_list.append(option_txt)
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
                        critair = critair.replace("Crit'Air ", "")
            except:
                critair = ''
                
            car_data = {
                "Titre": title,
                "Sous-titre": subtitle,
                "Image": image_url,
                "Prix": price,
                "Motorisation": motorisation,
                "Carburant": carburant,
                "Annee": year,
                "Kms": kms,
                "Options": option_list,
                "Lien": link,
                "Crit'air": critair
            }
            data_to_write.append(car_data)
        with open("exports/car_data.json", "w") as json_file:
            json.dump(data_to_write, json_file, ensure_ascii=False, indent=4)
    
    #fonction de scraping pour capcar pour une page
    def scrape_page_capcar(soup):
        vehiculecards = soup.find_all(class_="flex flex-col bg-white transitionAllCubic cursor-pointer hover:shadow-card rounded overflow-hidden shadow-cardXs")
        data_to_write = []
        for vehiculecard in vehiculecards:
            #TITRE
            try:
                brand = vehiculecard.find(itemprop="brand").text
                model = vehiculecard.find(itemprop="model").text
                title = brand+" "+model
                title = title.replace("é", "e")
                title = title.replace("è", "e")
                title = title.replace("ê", "e")
                title = title.replace("ë", "e")
                title = title.replace("É", "E")
                title = title.replace("Ë", "E")
                print(title)
            except:
                title=''
            #SOUS-TITRE
            try:
                subtitle = vehiculecard.find(class_="max-w-full overflow-hidden self-center truncate leading-tight").text
            except:
                subtitle=''
            #IMAGE
            try:
                image_id = vehiculecard.find(class_='rounded-t transitionAllEaseOut object-cover bg-lightBlue-400 bg-no-repeat bg-center w-full h-56 tablet:h-48')
                image_url = image_id.get('src')
                """img_link = soup.find('img', {'data-picture': img_id})
                image_url = img_link.get('data-original')"""
            except:
                image_url=''
            #PRIX
            try:
                priceContainer = vehiculecard.find(itemprop='price')
                price = priceContainer.get('content')
            except:
                price=''
            #MOTORISATION
            try:
                motorisation = vehiculecard.find(itemprop="vehicleTransmission").text
            except:
                motorisation=''
            #CARBURANT
            try:
                carburant = vehiculecard.find(itemprop="fuelType").text
                carburant = carburant.replace("É", "E")
            except:
                carburant=''
            #KILOMETRAGE
            try:
                kms = vehiculecard.find(itemprop="mileageFromOdometer").text
                kms = kms.replace(" ", "")
                kms=kms[:-3]
            except:
                kms=''
            #ANNEE
            try:
                year = vehiculecard.find(class_="text-left").text
            except:
                year=''
            #LIEN
            try:
                link_container = vehiculecard.find(itemprop="url")
                link = link_container.get('content')
                link = "https://www.capcar.fr" + link
            except:
                link = ''
            #LISTE D'OPTION
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
                }
                response_article = requests.get(link, headers=headers)
                soup_article = BeautifulSoup(response_article.content, "html.parser")
                option_list = []
                equipment_contents = soup_article.find_all(class_="inline-flex m-3 text-center leading-5")
                for option in equipment_contents:
                    option_txt = option.get_text(strip=True)
                    option_txt = option_txt.replace("é", "e")
                    option_txt = option_txt.replace("è", "e")
                    option_txt = option_txt.replace("ê", "e")
                    option_txt = option_txt.replace("ë", "e")
                    option_txt = option_txt.replace("É", "E")
                    option_txt = option_txt.replace("Ë", "E")
                    option_list.append(option_txt)
            except:
                option_list = []
            #CRIT'AIR
            try:
                critair_container = soup_article.find(class_="inline-block w-6 h-6 mb-1")
                critair = critair_container.get('alt')
                critair = critair.replace("Crit'air ", "")
            except:
                critair = ''
                
            car_data_heycar = {
                "Titre": title,
                "Sous-titre": subtitle,
                "Image": image_url,
                "Prix": price,
                "Motorisation": motorisation,
                "Carburant": carburant,
                "Annee": year,
                "Kms": kms,
                "Options": option_list,
                "Lien": link,
                "Crit'air": critair
            }
            data_to_write.append(car_data_heycar)
        with open("exports/car_data.json", "w", encoding='utf-8') as json_file:
            json.dump(data_to_write, json_file, ensure_ascii=False, indent=4)

    #scrape le nombre de pages voulu grâce à la fonction scrape_page
    def scrape_multiple_pages_aramis(self):
        print("------------------------SCRAPPING & BASE INSERTION-----------------------")
        url = f'{self.basic_url}?p={self.num_pages}'
        print('URL complet : '+url)
        num = str(self.num_pages)
        print('Nombre de pages scrappées : '+num)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.text, 'html.parser')
        #Appel de la fonction de scraping pour chaque page
        ScrapUtils.scrape_page_aramis(soup)

    #scrape le nombre de pages voulu grâce à la fonction scrape_page
    def scrape_multiple_pages_capcar(self):
        print("------------------------SCRAPPING & BASE INSERTION-----------------------")
        url = str(self.basic_url)
        print('URL du site : '+url)
        num = str(self.num_pages)
        print('Nombre de pages scrappées : '+num)

        #Appel de la fonction de scraping pour chaque page
        for i in (1,self.num_pages):
            url_page = f'{self.basic_url}?page={i}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
            }
            page = requests.get(url_page, headers=headers)
            soup = BeautifulSoup(page.text, 'html.parser')
            print('URL complet : '+url_page)
            ScrapUtils.scrape_page_capcar(soup)

    def global_scrap(self):
        if re.search('aramis', self.basic_url):
            ScrapUtils.scrape_multiple_pages_aramis(self)
        elif re.search('capcar', self.basic_url):
            ScrapUtils.scrape_multiple_pages_capcar(self)
        else:
            print('Algorithme de scrap non trouvé')
