
from google.cloud import bigquery
import argparse

def test_connection(project_id, location=None):
    print(f"Connecting to {project_id} (Location: {location})...")
    try:
        client = bigquery.Client(project=project_id, location=location)
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
    parser.add_argument("--location", default="US")
    args = parser.parse_args()
    test_connection(args.project, args.location)
