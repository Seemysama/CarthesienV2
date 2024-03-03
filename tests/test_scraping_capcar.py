import json
import requests
from bs4 import BeautifulSoup




#fonction de scraping pour une page
def scrape_page(soup):
    vehiculecards = soup.find_all(class_="flex flex-col bg-white transitionAllCubic cursor-pointer hover:shadow-card rounded overflow-hidden shadow-cardXs")
    data_to_write = []
    for vehiculecard in vehiculecards:
        #TITRE
        try:
            brand = vehiculecard.find(itemprop="brand").text
            model = vehiculecard.find(itemprop="model").text
            title = brand+" "+model
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
            price = vehiculecard.find(class_='text-2xl tablet:text-xl font-bold text-center block leading-none text-blue-275').text.strip()
            price = price.replace("€", "")
        except:
            price=''
        #MOTORISATION
        try:
            motorisation = vehiculecard.find(itemprop="vehicleTransmission").text
        except:
            motorisation=''
        #KILOMETRAGE
        try:
            kms = vehiculecard.find(itemprop="mileageFromOdometer").text
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
            link = "https://www.capcar.fr/voiture-occasion" + link
        except:
            link = ''
        #CRIT'AIR & LISTE D'OPTION
        try:
            response_article = requests.get(link)
            soup_article = BeautifulSoup(response_article.content, "html.parser")
            try:
                labels_bodies = soup_article.find(class_='md:font-bold text-base text-darkBlue-980 leading-3')
                for labels_body in labels_bodies:
                    if "Crit'Air" in labels_body.get_text():
                        critair = labels_body.text.strip()
                    else:
                        critair = ''
            except:
                critair = ''
            try:
                option_list = []
                equipment_contents = soup_article.find_all(class_="inline-flex m-3 text-center leading-5")
                if equipment_contents:
                    for option in equipment_contents:
                        option_list.append(option.get_text(strip=True))
                    else:
                        option_list = []
            except:
                option_list = []
        except:
            critair = ''
            option_list = []
            
        car_data_heycar = {
            "Titre": title,
            "Sous-titre": subtitle,
            "Image": image_url,
            "Prix": price,
            "Motorisation": motorisation,
            "Annee": year,
            "Kms": kms,
            "Options": option_list,
            "Lien": link,
            "Crit'air": critair
        }
        data_to_write.append(car_data_heycar)
    with open("exports/car_data_heycar.json", "w", encoding='utf-8') as json_file:
        json.dump(data_to_write, json_file, ensure_ascii=False, indent=4)


#scrape le nombre de pages voulu grâce à la fonction scrape_page
def scrape_multiple_pages(num_pages):
    print("------------------------SCRAPPING & BASE INSERTION-----------------------")
    url = 'https://www.capcar.fr/voiture-occasion'
    print('URL du site : '+url)
    num = str(num_pages)
    print('Nombre de pages scrappées : '+num)

    #Appel de la fonction de scraping pour chaque page
    for i in (1,num_pages+1):
        url_page = url + '?page='+str(i)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.text, 'html.parser')
        print('URL complet : '+url_page) 
        scrape_page(soup)


scrape_multiple_pages(2)