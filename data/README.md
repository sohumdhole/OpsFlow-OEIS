# Data

| File | Source | In this repo? |
|---|---|---|
| `raw/4tu_production_data.zip` | Levy, D. (2014). *Production Analysis with Process Mining Technology*. 4TU.ResearchData. https://doi.org/10.4121/uuid:68726926-5ac5-4fab-b873-ee76ea412399 | No. Download `data.zip` from the dataset page and save it here as `4tu_production_data.zip`. The pipeline checks its MD5 (`46174bf470258f9895dd153c78bc8b61`) before running. |
| `raw/rasff_meat_poultry_notifications.csv` | European Commission, RASFF Window (https://webgate.ec.europa.eu/rasff-window/screen/search), product categories "meat and meat products (other than poultry)" and "poultry meat and poultry meat products", CSV export of 17 November 2026 | Yes |
| `raw/fsai_allergen_alerts_listing.csv` | Food Safety Authority of Ireland allergen alerts listing (https://www.fsai.ie/news-alerts/allergens), every page, collected 17 November 2026 | Yes |

The SHA-256 of each file is recorded in `outputs/audit/audit.json` under `provenance`.
