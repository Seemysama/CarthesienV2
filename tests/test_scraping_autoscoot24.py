import json
import requests
from bs4 import BeautifulSoup
import csv
import requests
from urllib.parse import unquote


def scrape_page(soup):

    vehiculecards = soup.find_all(class_='list-entry')

    for vehiculecard in vehiculecards:
        try:
            title = vehiculecard.find(class_='vehicle-title').text
        except:
            title=''
        try:
            price = vehiculecard.find(class_='seller-currency').text.strip()
            price = price.replace("€ (TTC)", "")
        except:
            price=''
        try:
            image_element = vehiculecard.find('img', {'class': 'img-lazy'})
            image = image_element.get('src')
        except:
            image=''
            
        #print('{"Titre": "'+title+'", "Sous-titre" : "'+price+'", "Prix" : "'+price+'", "Motorisation" : "'+motorisation+'", "Année/Kms" : "'+kms'"},')
        car_data = {
            "Titre": title,
            "Image": image,
            "Prix": price
        }
        print(json.dumps(car_data, ensure_ascii=False))

def scrape_multiple_pages(num_pages):
    for page_num in range(1, num_pages + 1):
        numero = "Numéro : "+str(page_num)
        print(numero)
        url = f'https://www.automobile.fr/cat%C3%A9gorie/voiture/vhc:car,pgn:{page_num},pgs:10,dmg:false'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.text, 'html.parser')
        next_li_element = soup.find('li', class_='next')
        print()
        scrape_page(soup)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
}

scrape_multiple_pages(5)