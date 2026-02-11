# Initial Concept
Tools for optimizing [Peasisoft Native Upsell](https://welcome.peasisoft.com/native-upsell/) recommendations on WPSG BigCommerce storefronts.

# Product Definition - EasyUpsell Optimization

## Product Vision
To solve the issue of sparse and noisy co-purchase data in e-commerce by implementing a hybrid, category-first recommendation strategy. The system intelligently pairs products based on logical category relationships and explicit accessory mappings, validated by LLMs to ensure high-quality, relevant upsell suggestions.

## Target Users
- **E-commerce Managers:** Seeking to increase Average Order Value (AOV) through more effective cross-selling.
- **Data Analysts/Operations:** Managing product catalogs and recommendation logic for BigCommerce stores.

## Core Features
- **Category-First Recommendations:** Mapping relationships at the child and parent category levels.
- **LLM Validation:** Automated filtering of nonsensical category pairings using large language models.
- **Explicit Product Accessories:** High-priority, manual overrides for direct product-to-accessory mappings.
- **Dark Horse Discovery:** Generative analysis to find hidden inventory and catalog gaps using "Concept-First" brainstorming.
- **Integration Pipelines:** Scripts for exporting BigCommerce categories, fetching BigQuery enrichment data, and exporting recommendations to Peasisoft.
- **Analysis Tools:** Identifying cross-sell gaps and analyzing order co-occurrence.
