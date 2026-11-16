# Which columns did the hotel know on the day of booking?

**Owner:** Data Lead. **Closes:** part of ladder stage 1. **Used by:** `src/features.py`, the PRD and slide 4.

Put every column in exactly one bin, by when the hotel learns its value:

1. **Fixed at booking**: known on the day the booking is made, and it does not change.
2. **Amendable**: known at booking but it can change before arrival, or it is only partly known at booking.
3. **After the fact**: written at check-in, during the stay, or when the outcome is already known.

The project rubric requires the chosen rule to use only the first bin. A second-bin column may be tried as a caveated experiment; a third-bin column must not feed a booking-time method.

**Important dataset limitation:** Antonio et al. (2019) explain that, to avoid target leakage, values were extracted from the booking change log using a timestamp relative to the day before arrival (for bookings created before arrival). Therefore, the published dataset is not a complete point-in-time snapshot of what was first entered on the booking date. Where the paper describes amendments or a value derived from later events, this register uses a conservative bin. A Bin 1 classification means the field is treated as booking-time information for this project; it should not be interpreted as proof that the CSV preserves its original unamended value.

## Column timing register

| Column | Bin (1, 2 or 3) | Why | Evidence |
|---|---:|---|---|
| `hotel` | 1 | The hotel receiving the reservation is identified when the booking is made. | Core booking attribute; the dataset contains separate City Hotel and Resort Hotel records. |
| `is_canceled` | 3 | This is the outcome being predicted; it is not available as a booking-time input. | Article defines whether the booking was cancelled. Keep only as target. |
| `lead_time` | 2 | It is the interval between booking entry and arrival. If the arrival date is amended, the interval can change; the dataset does not preserve a separate original value. | Article, Table 1: number of days between booking entry and arrival. Arrival date can be amended. |
| `arrival_date_year` | 2 | Part of the scheduled arrival date, which can be amended before arrival. | Article explains booking amendments can change the arrival date; Table 1 describes arrival-date fields. |
| `arrival_date_month` | 2 | Part of the scheduled arrival date, which can be amended before arrival. | Same evidence as `arrival_date_year`; article's booking-change definition includes arrival-date changes. |
| `arrival_date_week_number` | 2 | Derived from the scheduled arrival date, which can be amended before arrival. | Same evidence as `arrival_date_year`; article's booking-change definition includes arrival-date changes. |
| `arrival_date_day_of_month` | 2 | Part of the scheduled arrival date, which can be amended before arrival. | Same evidence as `arrival_date_year`; article's booking-change definition includes arrival-date changes. |
| `stays_in_weekend_nights` | 2 | The length of stay can be amended before arrival. | Article, Table 1 and booking-change definition: changes can include nights. |
| `stays_in_week_nights` | 2 | The length of stay can be amended before arrival. | Article, Table 1 and booking-change definition: changes can include nights. |
| `adults` | 2 | The number of guests can be amended before arrival. | Article's operational discussion identifies changes to the number of persons. |
| `children` | 2 | The number of guests can be amended before arrival; the dataset also has four missing values in this field. | Article's operational discussion identifies changes to the number of persons; project EDA found 4 missing values. |
| `babies` | 2 | The number of guests can be amended before arrival. | Article's operational discussion identifies changes to the number of persons. |
| `meal` | 2 | Meal selection can be changed as part of booking amendments. | Article's booking-change definition includes changes to meal. |
| `country` | 3 | The article warns that nationality/country may only be known at check-in; it is therefore unsafe as a booking-time feature. | Article, discussion of country/nationality information; Table 1 lists BO, BL and NT as sources. |
| `market_segment` | 1 | Describes the market segment associated with the booking and is treated as booking-channel metadata. | Article, Table 1: market-segment designation; sourced from booking records. |
| `distribution_channel` | 1 | Describes the channel through which the booking was distributed and is treated as booking-time metadata. | Article, Table 1: distribution channel; sourced from booking records. |
| `is_repeated_guest` | 1 | Based on whether the guest had a profile/booking history before the current booking. | Article, Table 1: repeated guest indicator based on customer history before the current booking. |
| `previous_cancellations` | 1 | Counts cancellations from the guest's bookings before the current booking. | Article, Table 1: previous bookings cancelled before the current booking. |
| `previous_bookings_not_canceled` | 1 | Counts the guest's previous bookings that were not cancelled before the current booking. | Article, Table 1: previous bookings not cancelled before the current booking. |
| `reserved_room_type` | 2 | The reserved room type can be amended before arrival. | Article's booking-change definition includes changes to reserved room type. |
| `assigned_room_type` | 3 | The actual assigned room can differ from the reserved room due to hotel operations or customer requests; it is not a reliable booking-time value. | Article, Table 1: assigned room can differ from reserved room because of hotel operations (including overbooking) or customer request. |
| `booking_changes` | 3 | It is a cumulative count of amendments from booking entry until check-in or cancellation; the final count is not known on booking day. | Article, Table 1: changes counted from booking entry until check-in or cancellation. |
| `deposit_type` | 2 | The recorded deposit category is derived from payment transactions before arrival or cancellation; the article does not establish that the final recorded value is fixed at initial booking. | Article, Table 1: deposit type is determined from transactions before arrival or cancellation. |
| `agent` | 1 | Identifies the travel agency associated with making the booking; treated as booking-time metadata. | Article, Table 1: ID of the travel agency that made the booking; source BO and BL. |
| `company` | 1 | Identifies the company/entity associated with making or paying for the booking; treated as booking-time metadata. | Article, Table 1: company/entity associated with making or paying for the booking; source BO and BL. |
| `days_in_waiting_list` | 2 | The final waiting duration is only known once the booking is confirmed; at initial entry it is not yet fully known. | Article, Table 1: number of days between booking entry and confirmation. |
| `customer_type` | 1 | Describes the booking's contract/group/transient type and is treated as booking-time classification. | Article, Table 1: booking type; source BO and BL. |
| `adr` | 3 | Calculated using lodging transactions and the total number of staying nights; the final value depends on later stay/transaction information. | Article, Table 1: ADR is calculated from lodging transactions divided by total staying nights. |
| `required_car_parking_spaces` | 2 | Parking requirements may be amended before arrival; the final recorded number is not guaranteed to be the original booking-day value. | Article, Table 1: number of car parking spaces required by the customer; conservative timing classification. |
| `total_of_special_requests` | 2 | Special requests can be added or amended after the initial booking. | Article, Table 1: sum of special requests; conservative timing classification because requests can be updated. |
| `reservation_status` | 3 | Represents the final reservation outcome/status, such as cancelled, checked-out or no-show. | Article, Table 1: last reservation status. |
| `reservation_status_date` | 3 | Date on which the last reservation status was set; only known when that status event occurs. | Article, Table 1: date associated with the last reservation status. |

## Current approved model feature list (supersedes the earlier 17-column list)

The team decision recorded in `docs/DECISIONS.md` supersedes the earlier 17-column experimental list. The current model and MVP use only these nine Bin 1 features:

```python
MODEL_FEATURES = [
    "hotel",
    "market_segment",
    "distribution_channel",
    "is_repeated_guest",
    "previous_cancellations",
    "previous_bookings_not_canceled",
    "agent",
    "company",
    "customer_type",
]
```

`arrival_date`, `is_canceled`, `adr`, and `nights` remain scoring/splitting fields and are not model inputs. `is_canceled` is the target; `arrival_date`, `adr`, and `nights` are required by the client scoring contract.

**Remaining point-in-time limitation:** The timing register classifies the nine fields as Bin 1, but the published CSV is not a guaranteed snapshot of values as first recorded on booking day. Antonio et al. describe extraction relative to the day before arrival. The feature restriction aligns the model with the timing register; operational deployment still needs original booking-time snapshots or equivalent point-in-time evidence.

The earlier 17-column choice, which included seven Bin 2 fields and `country` (Bin 3), is retained as historical context in `docs/DECISIONS.md`; it is no longer the final model feature set.

## What happens to a method when the late columns go in?

The Model Lead owns these experiments. Do not fill in AUC values until the runs have been completed and the evaluation outputs have been supplied.

| Run | Columns | Split | AUC on the proof period |
|---|---|---|---|
| A | First bin only | Time | Pending — Model Lead |
| B | All three bins | Time | Pending — Model Lead |
| C | First bin only | Random | Pending — Model Lead |

**Which result should the client believe?** Run A is the relevant result for the intended booking-time decision, provided the temporal split and feature timestamps are valid. Run B is a leakage diagnostic, not a deployable result, because it includes information unavailable at booking. Run C is a random-split diagnostic and may overstate future performance by mixing time periods. The Model Lead should report the actual AUCs and explain the gap; no values are assumed here.

## Reference

Antonio, N., de Almeida, A., & Nunes, L. (2019). *Hotel booking demand datasets*. Data in Brief, 22, 41–49. https://doi.org/10.1016/j.dib.2018.11.126

### What the paper supports about feature timing

- The paper's experimental-design section (pp. 42–43) says the data point is the day before arrival and that booking values were taken from the booking change log relative to that date when a change existed. This is not a snapshot of the original booking-day values, so it does not establish that amendable fields kept their initial values.
- The operations caveat (p. 45) says booking attributes such as guest count, stay duration, and room preference can change at check-in or during the stay. It also says hotels may not know a guest's nationality until check-in. This supports the Bin 2 classifications for amendable fields and Bin 3 for `country`.
- The paper does not provide evidence to move `country` into a booking-time bin. Therefore the team's 17-column set can remain the agreed experimental feature set, but a rule using all 17 cannot be represented as using only booking-time information or as meeting the rubric's no-late-column condition. The AUC comparison should identify the timing-safe result separately from experiments that use Bin 2 or Bin 3 fields.

Page references above are to the cited article's printed pages (pp. 42–45).
