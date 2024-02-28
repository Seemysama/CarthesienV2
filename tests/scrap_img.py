from bs4 import BeautifulSoup
import requests

# Récupérer le contenu HTML de la page
url = "https://www.aramisauto.com/achat/occasion?types%5B0%5D=VO"
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

# Trouver l'image en utilisant son attribut "data-picture"
image = soup.find('img', {'data-picture': 'rv774197'})

# Extraire l'adresse de l'image
image_url = image.get('data-original')

# Afficher l'adresse de l'image
print(image_url)