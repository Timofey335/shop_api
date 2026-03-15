import time
import json
import redis
import requests
import re
from bs4 import BeautifulSoup
from .logger_config import setup_logger

logger = setup_logger('worker')

try:
    redis_client = redis.Redis(host='redis', port=6379, db=1, decode_responses=True)
    redis_client.ping()
    logger.info('Worker connected to Redis')
except Exception as e:
    logger.error(f'Worker failed to connect to Redis: {e}')
    raise


SHOPS = {
    'СИЗО 1': '218999',
    'СИЗО 3': '219013',
    'СИЗО 4': '221918',
    'ЛИУ 15': '221917'
}

UPDATE_INTERVAL = 1800

# Получить список все доступных продуктов на сайте
def fetch_products(shop_id):
    # print("[Pyhton] Starting parse...")

    shop_id = str(shop_id)

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
        'FSIN_AGENCY': shop_id,
        f'FSIN_OFERTA_HAS_SHOP_{shop_id}': 'Y'
    }

    url = 'https://kaluzhskoe.shop/catalog/'
    all_cards = []
# В цикле получаем все продукты переключая пагинацию 
# до тех пор пока не пропадет символ пагинации - стрелка
    while url:
        response = requests.get(url, headers=headers, cookies=cookies)
        soup = BeautifulSoup(response.text, 'lxml')
        block = soup.select_one('div#catalog')

        if block:
            all_cards.extend(block.select('div[itemprop="itemListElement"]'))
        next_a = soup.select_one('li.last > a')
        url = None

        if next_a and next_a.get('href') :
            url = requests.compat.urljoin(response.url, next_a['href'])
            logger.info(url)

        time.sleep(0.7)

    # print('All cards:', len(all_cards))

    products = []
    for item in all_cards:
        try:
            name = item.find('span', itemprop='name').text.strip()
            url = item.find('a', itemprop='url')['href']
            in_stock = item.find('div', class_='quantity-available').get_text(strip=True)
            stock_match = re.search(r'В наличии:\s*(\d+)', in_stock)
            stock_quantity = int(stock_match.group(1)) if stock_match else 0

            products.append({
                'name': name,
                'url': 'https://kaluzhskoe.shop' + url,
                'availability': stock_quantity,
            })

        except AttributeError:
            continue

    return products

def update_shop(shop_name, shop_id):
    logger.info(f'Starting update for {shop_name} (ID: {shop_id})')
    
    try:
        start_time = time.time()
        products = fetch_products(shop_id)
        duration = time.time() - start_time
        
        if not products:
            logger.warning(f'No products fetched for {shop_name}')
            return False
        
        data_key = f'shop:{shop_id}'
        ts_key = f'shop:{shop_id}:ts'
        
        redis_client.set(data_key, json.dumps(products))
        redis_client.set(ts_key, int(time.time()))
        
        logger.info(f'{shop_name} updated: {len(products)} products in {duration:.1f}s')
        return True
            
    except Exception as e:
        logger.error(f'Failed to update {shop_name}: {e}')
        return False
    
def main():
    logger.info('Worker starting...')
    logger.info(f'Shops to update: {list(SHOPS.keys())}')
    logger.info(f'Update interval: {UPDATE_INTERVAL} seconds ({UPDATE_INTERVAL//60} minutes)')
            
    while True:
        try:
            logger.info(f'Starting update cycle at {time.strftime("%Y-%m-%d %H:%M:%S")}')
            
            for shop_name, shop_id in SHOPS.items():
                update_shop(shop_name, shop_id)
                time.sleep(5)
                
            logger.info(f'Cycle complete, sleeping {UPDATE_INTERVAL} seconds')
            time.sleep(UPDATE_INTERVAL)
        except Exception as error:
            logger.error(f"Error in cycle: {error}")
            time.sleep(60)
            
            
if __name__ == '__main__':
    main()