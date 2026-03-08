from os import times
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
import re
from difflib import SequenceMatcher
import redis
import json

from logger_config import setup_logger

logger = setup_logger('api')

app = Flask(__name__)
CORS(app)

logger.info('Starting API server...')

try:
    # Подключение к Redis
    redis_client = redis.Redis(host='redis', port=6379, db=1, decode_responses=True)
    redis_client.ping()
    logger.info('Connected to Redis')
except Exception as e:
    logger.error(f'Failed to connect to Redis: {e}')
    raise
    
CACHE_TTL = 3600 # максимальный срок жизни данных один час

def get_cached_products(shop_id):
    shop_id = str(shop_id)
    data_key = f'shop:{shop_id}'
    ts_key = f'shop:{shop_id}:ts'
    
    logger.info(f'Fetching products for shop {shop_id}')
    
    data = redis_client.get(data_key)
    timestamp = redis_client.get(ts_key)
    
    if not data or not timestamp:
        logger.warning(f'No data found for shop {shop_id}')
        return None, None
    
    timestamp = int(timestamp)
    now = int(time.time())
    age = now - timestamp
    
    logger.info(f'Data for shop {shop_id} is {age} seconds old')
    
    if age > CACHE_TTL:
        logger.warning(f'Data stale for shop {shop_id}: {age}s > {CACHE_TTL}s')
        return None, timestamp
    
    products = json.loads(data)
    logger.info(f'Data fresh for shop {shop_id}, {len(products)} products')
    return products, timestamp    

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

def normalize_text(text):
    if not text:
        return ""
    # В нижний регистр, удаляем лишние пробелы и пунктуацию
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)  # Удаляем знаки препинания
    return text

#Считаем схожесть двух строк (0.0 - 1.0)
def calculate_similarity(query, text):
    query = normalize_text(query)
    text = normalize_text(text)
    
    # Если точное вхождение — максимальный скор
    if query in text:
        return 1.0
    
    # Ищем совпадение по словам (если запрос "молоко 3.2", а в товаре "молоко 3.2% жирности")
    query_words = set(query.split())
    text_words = set(text.split())
    
    if query_words and query_words.issubset(text_words):
        return 0.9
    
    # Если хотя бы одно слово совпадает
    if any(word in text for word in query_words):
        return 0.7
    
    # Нечеткое сравнение (на случай опечаток: "малако" вместо "молоко")
    return SequenceMatcher(None, query, text).ratio()

def smart_search(products, query, threshold=0.6):
    results = []
    query = normalize_text(query)
    
    for product in products:
        name = product['name']
        score = calculate_similarity(query, name)
        
        if score >= threshold:
            results.append({
                'product': product,
                'score': score,
                'matches_all_words': score >= 0.9
            })
    
    # Сортируем по убыванию релевантности
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # Возвращаем только товары (без скоров)
    return [r['product'] for r in results]

@app.route('/products', methods=['GET'])
def get_products():
    shop_id = request.args.get('shop_id', '221918')
    logger.info(f'Request /products for shop_id={shop_id}')

    try:
        shop_id = int(shop_id)
    except ValueError:
        logger.error(f'Invalid shop_id: {shop_id}')
        return jsonify({'error': 'shop_id must be a number'}), 400
    
    products, timestamp = get_cached_products(shop_id)
    
    if products is None and timestamp is None:
        logger.error(f'No data available for shop {shop_id}')
        return jsonify({
            'error': 'No data',
            'shop_id': shop_id
        }), 404
    
    if products is None:
        logger.error(f'Stale data rejected for shop {shop_id}')
        return jsonify({
            'error': 'Data stale',
            'shop_id': shop_id,
            'last_update': timestamp
        }), 503
        
    logger.info(f'Returning {len(products)} products for shop {shop_id}')   
    return jsonify({
        'shop_id': shop_id,
        'count': len(products),
        'fresh': True,
        'products': products
    })

@app.route('/search', methods=['GET'])
def search_products():
    shop_id = request.args.get('shop_id', '221918')
    query = request.args.get('q', '').strip()
    
    logger.info(f'Request /search shop_id={shop_id} query="{query}"')

    if len(query) < 2:
        logger.warning(f'Query too short: "{query}"')
        return jsonify({'error': 'Query is short (min 2 characters)', 'query': query}), 400
    
    try:
        shop_id = int(shop_id)
    except ValueError:
        logger.error(f'Invalid shop_id: {shop_id}')
        return jsonify({'error': 'shop_id must be a number'}), 400
    
    products, timestamp = get_cached_products(shop_id)
    
    if products is None and timestamp is None:
        logger.error(f'No data for search in shop {shop_id}')
        return jsonify({
            'error': 'No data',
            'shop_id': shop_id
        }), 404
        
    if products is None:
        logger.error(f'Stale data for search in shop {shop_id}')
        return jsonify({
            'error': 'Data stale',
            'shop_id': shop_id,
            'last_update': timestamp
        }), 503

    results = smart_search(products, query, threshold=0.5)
    logger.info(f'Search "{query}" found {len(results)} results in shop {shop_id}')

    return jsonify({
        'shop_id': shop_id,
        'query': query,
        'count': len(results),
        'fresh': True,
        'products': results
    })

@app.route('/shops', methods=['GET'])
def get_shops():
    return jsonify({
        'СИЗО 1':  '218999',
        'СИЗО 3':  '219013',
        'СИЗО 4':  '221918',
        'ЛИУ 15': '221917'
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)