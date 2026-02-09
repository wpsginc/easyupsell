# Product Guidelines - EasyUpsell Optimization

## 1. Design Philosophy
- **Human-in-the-Loop (HITL):** This system is an **assistive tool** for merchandising teams, not an autonomous agent. Its goal is to drastically reduce research time, not to replace human decision-making.
- **KISS (Keep It Simple, Stupid):** Prioritize clear, auditable logic over complex "black box" automation. The primary output is actionable data (CSV) for human review.
- **Specificity = Priority:** We adhere to a strict hierarchy where the specificity of the relationship determines the weight of the recommendation.

## 2. Tone and Voice
- **Clinical and Precise:** Communication should be objective and data-focused.
- **Terminology:**
    - Use **"Confidence Score"** and **"Data Density"** when describing AI outputs.
    - Refer to invalid pairings as **"Rejections"** or **"Low Confidence"** rather than "Hallucinations."
    - Focus on **Weight** as the primary metric for sorting recommendations.

## 3. Weighting Standards (SOP)
All recommendations must adhere to the following 1-10 scale. Higher weight indicates higher priority.

| Weight | Scope | Description | Example |
| :--- | :--- | :--- | :--- |
| **10** | **Event/Promo** | **Overrides everything.** Use sparingly. | "Weekend Flash Sale – Add X to get 50% off Y" |
| **8-9** | **Product-Specific** | Highly specific, manual or strong data pairings. | "Buy Helmet A, get Helmet A flashlight" |
| **7** | **Deep Category** | Depth 4. Specific sub-sub-categories. | "Buy Model X radio, get matching carry case" |
| **5** | **Mid Category** | Depth 3. | "Buy tactical boots, get 15% off socks" |
| **3** | **High Category** | Depth 2. | "Buy outerwear, get 20% off gloves" |
| **2** | **Top Category** | Top-level general pairings. | "Buy any helmet, get 10% off accessories" |
| **1** | **Global** | **Fallback.** Site-wide defaults. | "Free shipping on orders over $50" |

## 4. Operational Interfaces
- **CLI Output:**
    - Primary format: **Tabular** (using `rich` library).
    - Critical columns: `Weight`, `Confidence`, `Source` (Rule vs. AI), `Reasoning`.
- **Data Export:**
    - All analysis must be exportable to **CSV** for easy ingestion by merchandising teams.
    - Files should be structured to allow for direct "copy-paste" validation into the Peasisoft configuration if approved by a human.

## 5. Error Handling & Validation
- **Fail Safe:** If data is ambiguous, simply assign a lower weight. The human operator is the final validator.
- **Transparency:** Every recommendation must have a traceable source (e.g., "Matched via Rule #42" or "AI Association Score: 0.95").
