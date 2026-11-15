# AI benchmark result

Command: `python ai_benchmark/run.py`

Source population: 119,390; train/choose/proof: 49,157/29,546/40,687.

Branch note: the repository's first commit contains only README.md, so the benchmark branch is based on the project snapshot d146ae7; this follows the available project code and is a documented deviation from docs/AI_WORKFLOW.md.

The benchmark uses the original source population per the approved plan. This differs from our filtered scoring population (827 rows removed). The benchmark uses 18 features: 9 Bin 1 and 9 Bin 2, with no Bin 3 country. It is not booking-time-only under our timing audit. Our team's approved 17-column rule differs and includes 7 Bin 2 fields plus country (Bin 3).

```text
             method   cost_eur  empty_rooms  walked_guests  walks_per_1000  ceiling_met  nights  buffer  proof_auc
   Client flat rate 3882929.54         8050            167            6.70         True     486      16     0.5542
             Lookup 4656391.62        10133            154            6.17         True     486      23     0.6896
Logistic regression 5407602.46        12110              1            0.04         True     486       0     0.7250
      Random forest 3510962.91         7222            105            4.21         True     486      23     0.7799
```

Selected nightly output method: Random forest; frozen buffer: 23.
