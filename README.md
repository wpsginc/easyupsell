# EasyUpsell

NetSuite + BigCommerce upsell integration for WPSG.

## Overview

EasyUpsell connects NetSuite product data with BigCommerce's related products feature to power upsell and cross-sell functionality on storefronts.

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.template .env
# Fill in your NetSuite TBA and BigCommerce API credentials

# Test connections
python scripts/test_ns_auth.py
python scripts/test_bc_auth.py
```

## Configuration

Copy `.env.template` to `.env` and configure:

### NetSuite TBA Credentials
- `NETSUITE_ACCOUNT_ID`: Account ID (e.g., `5001161_SB1`)
- `NETSUITE_CONSUMER_KEY`: Integration consumer key
- `NETSUITE_CONSUMER_SECRET`: Integration consumer secret
- `NETSUITE_TOKEN_ID`: TBA token ID
- `NETSUITE_TOKEN_SECRET`: TBA token secret

### BigCommerce API
- `BC_STORE_HASH`: Your store's hash
- `BC_ACCESS_TOKEN`: API access token with Products scope

## Project Structure

```
easyupsell/
├── src/
│   ├── netsuite/       # NetSuite OAuth 1.0a TBA client
│   │   ├── auth.py     # Authentication helpers
│   │   └── client.py   # REST API client
│   └── bigcommerce/    # BigCommerce V3 client
│       └── client.py   # Product & related products API
├── scripts/            # CLI utilities
│   ├── test_ns_auth.py
│   └── test_bc_auth.py
├── tests/              # Unit tests
├── DOCS/               # Documentation
└── requirements.txt
```

## Related Projects

- **pim-sync**: NetSuite → LibrePIM → SalesLayer sync (auth patterns ported from here)

## License

Internal WPSG project.
