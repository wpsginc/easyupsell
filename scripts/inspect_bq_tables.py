from google.cloud import bigquery

def list_tables():
    client = bigquery.Client()
    datasets = list(client.list_datasets())
    
    for ds in datasets:
        print("")
        print(f"Dataset: {ds.dataset_id}")
        try:
            tables = list(client.list_tables(ds.dataset_id))
            for t in tables:
                print(f"  - {t.table_id}")
        except Exception as e:
            print(f"  Error listing tables: {e}")

if __name__ == "__main__":
    list_tables()