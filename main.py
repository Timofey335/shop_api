import requests
from bs4 import BeautifulSoup
import re
import time
import requests.compat


def main():
    print('start')

    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
    }

    cookies = {
    'FSIN_AGENCY': '219013',
    'FSIN_OFERTA_HAS_SHOP_219013': 'Y'
}

    url = 'https://kaluzhskoe.shop/catalog/'

    # часть для работы с пагинацией
    all_cards = []

    while url:
        response = requests.get(url, headers=headers, cookies=cookies)
        print(response.status_code)
        soup = BeautifulSoup(response.text, 'lxml')
        block = soup.select_one('div#catalog')

        if block:
            all_cards.extend(block.select('div[itemprop="itemListElement"]'))
        next_a = soup.select_one('li.last > a')
        url = None

        if next_a and next_a.get('href') :
            url = requests.compat.urljoin(response.url, next_a['href'])
            print(url)

        time.sleep(0.7)

    products = []
    for item in all_cards:
        # Извлекаем данные (защита от отсутствующих элементов)
        try:
            name = item.find('span', itemprop='name').text.strip()
            url = item.find('a', itemprop='url')['href']
            price_text = item.find('span', class_='catalog-item-price').get_text(strip=True)
            in_stock = item.find('div', class_='quantity-available').get_text(strip=True)
            stock_match = re.search(r'В наличии:\s*(\d+)', in_stock)
            stock_quantity = int(stock_match.group(1)) if stock_match else 0
            
            products.append({
                'name': name,
                'url': 'https://site.com' + url,
                'price': price_text,
                'availability': stock_quantity,
                'image': 'https://site.com' + item.find('meta', itemprop='image')['content']
            })

        except AttributeError:
            continue  # Пропускаем товары с неполными данными

    # Выводим результат
    for p in products:
        # print(f"{p['name']} — {p['price']} - {p['availability']}")
        print(f"{p['name']} — {p['availability']}")

        with open('./page.txt', 'w') as f:
            # f.write(f"{p['name']} — {p['price']} - {p['availability']}")
            f.write(f"{p['name']} — {p['availability']}")


    print('stop')

if __name__ == "__main__":
    main()