import requests
from bs4 import BeautifulSoup
import csv

def scrape_page(soup, quotes):
    quote_elements = soup.find_all('div', class_='quote')

    for quote_element in quote_elements:
        text = quote_element.find('span', class_='text').text
        author = quote_element.find('small', class_='author').text
        tag_elements = quote_element.find('div', class_='tags').find_all('a', class_='tag')

        tags = []
        for tag_element in tag_elements:
            tags.append(tag_element.text)

        quotes.append(
            {
                'text': text,
                'author': author,
                'tags': ', '.join(tags)  # merging the tags into a "A, B, ..., Z" string
            }
        )

base_url = 'https://quotes.toscrape.com'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
}

page = requests.get(base_url, headers=headers)

soup = BeautifulSoup(page.text, 'html.parser')

quotes = []

scrape_page(soup, quotes)

next_li_element = soup.find('li', class_='next')

while next_li_element is not None:
    next_page_relative_url = next_li_element.find('a', href=True)['href']

    page = requests.get(base_url + next_page_relative_url, headers=headers)

    soup = BeautifulSoup(page.text, 'html.parser')

    scrape_page(soup, quotes)

    next_li_element = soup.find('li', class_='next')

csv_file = open('quotes.csv', 'w', encoding='utf-8', newline='')

writer = csv.writer(csv_file)

writer.writerow(['Text', 'Author', 'Tags'])

for quote in quotes:
    writer.writerow(quote.values())

csv_file.close()