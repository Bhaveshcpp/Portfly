# AI Real Estate Portfolio Analyst — Dataset

## Users

| user_id   | name         | city      | preferences         | preferred_locations          | portfolio_value_preference_inr   |
|:----------|:-------------|:----------|:--------------------|:-----------------------------|:---------------------------------|
| U001      | Rahul Mehta  | Mumbai    | Commercial / Retail | Mumbai                       | 50000000                         |
| U002      | Priya Shah   | Mumbai    | Residential         | Bandra / Worli / Lower Parel | 30000000-80000000                |
| U003      | Arjun Kapoor | Delhi NCR | Commercial / Office | Gurugram / Noida             | 100000000                        |
| U004      | Neha Jain    | Bengaluru | Retail / Office     | Bengaluru                    | 20000000-60000000                |

## Properties

| property_id   | user_id   | property_type     | sub_type             | location                   |   area_sqft |   current_estimated_value_inr | purchase_price_inr   |   annual_rent_inr | occupancy_status   | tenant_status   |   ownership_percent | status   |
|:--------------|:----------|:------------------|:---------------------|:---------------------------|------------:|------------------------------:|:---------------------|------------------:|:-------------------|:----------------|--------------------:|:---------|
| P001          | U001      | Retail            | High-street retail   | Bandra West, Mumbai        |        5200 |                     120000000 |                      |           7200000 | Tenanted           | Yes             |                 100 | Active   |
| P002          | U001      | Commercial Office | Office               | Andheri East, Mumbai       |        7800 |                      85000000 |                      |                 0 | Vacant             | No              |                 100 | Active   |
| P003          | U001      | Retail            | Shopping centre unit | Lower Parel, Mumbai        |        3100 |                      92000000 |                      |           6000000 | Tenanted           | Yes             |                 100 | Active   |
| P004          | U002      | Residential       | Apartment            | Bandra West, Mumbai        |        2100 |                      64000000 |                      |                 0 | Self-occupied      | No              |                 100 | Active   |
| P005          | U002      | Residential       | Apartment            | Worli, Mumbai              |        1800 |                      51000000 |                      |           2400000 | Tenanted           | Yes             |                 100 | Active   |
| P006          | U002      | Residential       | Villa                | Alibaug, Maharashtra       |        4200 |                      78000000 |                      |                 0 | Vacant             | No              |                 100 | Active   |
| P007          | U003      | Commercial Office | Office               | Golf Course Road, Gurugram |       18500 |                     240000000 |                      |          16800000 | Tenanted           | Yes             |                 100 | Active   |
| P008          | U003      | Commercial Office | Office               | Noida Sector 62, Noida     |       12000 |                     115000000 |                      |                 0 | Vacant             | No              |                 100 | Active   |
| P009          | U003      | Retail            | High-street retail   | Sector 29, Gurugram        |        4600 |                     132000000 |                      |           9600000 | Tenanted           | Yes             |                 100 | Active   |
| P010          | U004      | Retail            | Mall retail          | Whitefield, Bengaluru      |        2800 |                      48000000 |                      |           3600000 | Tenanted           | Yes             |                 100 | Active   |
| P011          | U004      | Office            | Office floor         | Koramangala, Bengaluru     |        3900 |                      56000000 |                      |           4200000 | Tenanted           | Yes             |                 100 | Active   |
| P012          | U004      | Residential       | Apartment            | Indiranagar, Bengaluru     |        2200 |                      34000000 |                      |                 0 | Self-occupied      | No              |                 100 | Active   |

## Sample Requests

| request_id   | user_id   | user_request                                                     | expected_capability   | expected_interpretation                                               |
|:-------------|:----------|:-----------------------------------------------------------------|:----------------------|:----------------------------------------------------------------------|
| R001         | U001      | Show me my retail properties                                     | search_properties     | owner=U001; property_type=Retail                                      |
| R002         | U001      | Which of my properties are above ₹10 crore?                      | search_properties     | owner=U001; current_estimated_value_inr>100000000                     |
| R003         | U002      | Show me my properties in Mumbai                                  | search_properties     | owner=U002; location contains Mumbai                                  |
| R004         | U003      | Which property gives me the highest annual rent?                 | portfolio_analysis    | max annual_rent_inr                                                   |
| R005         | U004      | Add a 3000 sq ft retail property in Indiranagar worth ₹4.2 crore | create_property       | area=3000; property_type=Retail; location=Indiranagar; value=42000000 |
| R006         | U001      | Change my Bandra retail property value to ₹12.5 crore            | update_property       | identify P001 from context; current_estimated_value_inr=125000000     |

## Notes

- All records are synthetic.
- Monetary values are INR.
- No private or authenticated data source is required.
- `purchase_price_inr` is mostly blank intentionally.
- Candidates may choose their own persistence/retrieval architecture.
