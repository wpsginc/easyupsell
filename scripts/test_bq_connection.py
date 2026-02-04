
from google.cloud import bigquery
import argparse

def test_connection(project_id):
    print(f"Connecting to {project_id}...")
    try:
        client = bigquery.Client(project=project_id)
        print("Client created.")
        
        query = "SELECT 1"
        query_job = client.query(query)
        print("Query sent.")
        
        results = query_job.result()
        for row in results:
            print(f"Result: {row[0]}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    test_connection(args.project)
