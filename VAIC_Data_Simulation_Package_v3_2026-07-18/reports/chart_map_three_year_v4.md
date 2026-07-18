# Chart map — three-year synthetic report

| Report segment | Analytical question | Family / variant | Fields | Supported claim | Palette | Artifact |
|---|---|---|---|---|---|---|
| Temporal trend and seasonality | Dữ liệu có tăng nhẹ và giữ chu kỳ tháng mà không deterministic không? | Two-panel line: 36-month total + overlaid normalized month-of-year profiles | `month`, `total_weight_tons`, rolling 3m, year-normalized index | Trend tăng nhẹ; mùa vụ lặp lại nhưng khác nhau giữa seed/year | Blue single-root plus gold rolling comparator; line style and marker distinguish years | `figures/three_year_monthly_trend.png` |

The y-axis of the absolute tonnage panel starts at zero. The normalized seasonal panel uses an explicit 100 reference line and does not imply observed production statistics.

