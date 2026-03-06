import time
import json
import redis
from api import fetch_products

redis_client = redis.Redis(host='127.0.0.1', port=6379, db=1, decode_responses=True)

SHOPS = {
    'СИЗО 1': '218999',
    'СИЗО 3': '219013',
    'СИЗО 4': '221918',
    'ЛИУ 15': '221917'
}

UPDATE_INTERVAL = 1800

def update_shop(shop_name, shop_id):
    print(f'[Worker] Updating {shop_name} (ID: {shop_id})...')
    
    try:
        products = fetch_products(shop_id)
        
        if not products:
            print(f'[Worker] No products fetched for {shop_name}')
            return False
        
        data_key = f'shop:{shop_id}'
        ts_key = f'shop:{shop_id}:ts'
        
        redis_client.set(data_key, json.dumps(products))
        redis_client.set(ts_key, int(time.time()))
        
        print(f'[Worker] {shop_name} updated: {len(products)} products')
        return True
            
    except Exception as e:
        print(f'[Worker] Error updating {shop_name}: {e}')
        return False
    
def main():
    print('[Worker] starting...')
    
    while True:
        print(f'[Worker] Starting update cycle at {time.strftime("%Y-%m-%d %H:%M:%S")}')
        
        for shop_name, shop_id in SHOPS.items():
            update_shop(shop_name, shop_id)
            time.sleep(5)
            
        print(f'[Worker] Cycle complete. Sleeping {UPDATE_INTERVAL} seconds...')
        time.sleep(UPDATE_INTERVAL)
            
if __name__ == '__main__':
    main()