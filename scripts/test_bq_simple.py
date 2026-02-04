
from google.cloud import bigquery

def test_adc():
    print("Initializing BigQuery Client with ADC...")
    try:
        # User said: client = bigquery.Client() # Uses ADC automatically
        client = bigquery.Client()
        print(f"Client created. Project: {client.project}")
        
        print("Listing datasets...")
        datasets = list(client.list_datasets())
        if datasets:
            print(f"Found {len(datasets)} datasets.")
            for ds in datasets[:3]:
                print(f" - {ds.dataset_id}")
        else:
            print("No datasets found (but connection working).")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_adc()
