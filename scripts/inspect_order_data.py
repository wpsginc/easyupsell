
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from bigcommerce import BigCommerceClient

def inspect_order_products():
    try:
        client = BigCommerceClient.from_env()
        print("Connected to BigCommerce.")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # Fetch one recent completed order
    orders = client.get_orders(status_id=11, limit=1)
    if not orders:
        print("No completed orders found.")
        return

    order = orders[0]
    print(f"Inspecting Order ID: {order['id']}")

    products = client.get_order_products(order['id'])
    if products:
        print("First product data keys:", products[0].keys())
        print("First product sample:", json.dumps(products[0], indent=2))
    else:
        print("No products in this order.")

if __name__ == "__main__":
    inspect_order_products()
