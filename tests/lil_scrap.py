import requests
from bs4 import BeautifulSoup

basic_url = 'https://www.aramisauto.com/achat/occasion?p='
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'}

page_number = 1
nombre_de_pages = 5

for page_number in range(1, nombre_de_pages + 1):
    url = f"{basic_url}{page_number}"

    response = requests.get(url)
    #print(f"Page {page_number} - Titre: {soup.title.text}")

    if response.status_code == 200:
        while True:
            soup = BeautifulSoup(page.text, 'html.parser')
            page = requests.get(url, headers=headers)
            vehiculecards = soup.find_all(class_='vehicle-container')

            for vehiculecard in vehiculecards:
                try:
                    title = vehiculecard.find(class_='vehicle-model').text
                except:
                    title = ''
                # Utiliser BeautifulSoup pour analyser le contenu HTML de la page
                soup = BeautifulSoup(response.text, 'html.parser')
                print("Title:", title)
            else:
                print(f"Échec de la requête pour la page {page_number}")
