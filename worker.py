import time
import json
import redis
from api import fetch_products
from logger_config import setup_logger

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
        logger.info(f'Starting update cycle at {time.strftime("%Y-%m-%d %H:%M:%S")}')
        
        for shop_name, shop_id in SHOPS.items():
            update_shop(shop_name, shop_id)
            time.sleep(5)
            
        logger.info(f'Cycle complete, sleeping {UPDATE_INTERVAL} seconds')
        time.sleep(UPDATE_INTERVAL)
            
            
if __name__ == '__main__':
    main()